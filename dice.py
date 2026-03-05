# dice.py

import os
import random
import asyncio
import re
from datetime import datetime

from telegram import (
    Bot,
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from balance import get_balance, update_balance, add_wager
from models import get_connection, update_stats

# ─────────────────────────────────────────────────────────────────────────────
#                             Helper‐Bot Setup
# ─────────────────────────────────────────────────────────────────────────────

HELPER_BOT_TOKEN = os.getenv("HELPER_BOT_TOKEN")
if not HELPER_BOT_TOKEN:
    raise RuntimeError("HELPER_BOT_TOKEN not set in environment")
helper_bot = Bot(token=HELPER_BOT_TOKEN)

# ─────────────────────────────────────────────────────────────────────────────
#                          Dice Game Configuration
# ─────────────────────────────────────────────────────────────────────────────

BASE_PAYOUT = 1.92   # uniform payout multiplier for all modes

# In-memory game state
# games[user_id] = {
#    bet, mode, to_win, stage,
#    round_no, initial_first,
#    score: {user,bot},
#    bot_total (list), user_rolls,
#    chat_id, msg_id
# }
games = {}

# ─────────────────────────────────────────────────────────────────────────────
#                             Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def safe_parse_float(s: str) -> float:
    try:
        return float(s)
    except:
        return 0.0

def parse_bet(arg: str, balance: float) -> float:
    a = arg.lower().replace("$","").replace("₹","")
    if a == "half":
        return round(balance/2, 2)
    if a == "all":
        return round(balance, 2)
    return safe_parse_float(a)



def save_session(user_id: int, mode: str, bet: float, won: float, is_win: bool):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO game_sessions(user_id, mode, played_at, bet, won_amount, is_win)"
        " VALUES (?,?,?,?,?,?)",
        (user_id, mode, datetime.utcnow().isoformat(), bet, won, int(is_win))
    )
    conn.commit()
    conn.close()
    update_stats(user_id, is_win)

def mention(user):
    return f'<a href="tg://user?id={user.id}">{user.first_name}</a>'

# ─────────────────────────────────────────────────────────────────────────────
#                              Keyboards
# ─────────────────────────────────────────────────────────────────────────────

def build_mode_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Normal Mode",   callback_data="mode:normal")],
        [InlineKeyboardButton("Double Roll",   callback_data="mode:double")],
        [InlineKeyboardButton("Crazy Mode",    callback_data="mode:crazy")],
        [
            InlineKeyboardButton("ℹ Mode Guide", callback_data="mode:guide"),
            InlineKeyboardButton("❌ Cancel",     callback_data="cancel")
        ]
    ])

def build_points_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("First to 3 points", callback_data="points:3")],
        [InlineKeyboardButton("First to 2 points", callback_data="points:2")],
        [InlineKeyboardButton("First to 1 point",  callback_data="points:1")],
        [InlineKeyboardButton("❌ Cancel",         callback_data="cancel")]
    ])

def build_confirm_keyboard():
    return InlineKeyboardMarkup([[ 
        InlineKeyboardButton("✅ Confirm", callback_data="confirm:yes"),
        InlineKeyboardButton("❌ Cancel",  callback_data="cancel")
    ]])

def build_accept_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Accept Match",     callback_data="accept:yes"),
            InlineKeyboardButton("✅ Play against bot", callback_data="accept:bot")
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ])

def build_next_round_keyboard(us: int, bs: int, to_win: int):
    mult = cashout_multiplier(us, bs, to_win)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Next Round", callback_data="action:next")],
        [InlineKeyboardButton(f"💸 Cashout {mult}×", callback_data="action:cashout")]
    ])

def build_end_keyboard(bet: float, payout: float):
    return InlineKeyboardMarkup([[ 
        InlineKeyboardButton("🔄 Play Again", callback_data=f"replay:{bet}"),
        InlineKeyboardButton("✖ Double",      callback_data=f"double:{payout}")
    ]])

# ─────────────────────────────────────────────────────────────────────────────
#                            /dice Command
# ─────────────────────────────────────────────────────────────────────────────

async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    bal     = get_balance(user.id)
    args    = context.args
    chat_id = update.effective_chat.id

    # If no bet provided
    if not args:
        return await update.message.reply_text(
            "🎲 *Play Dice*\n\n"
            "To play, type the command /dice with the desired bet.\n\n"
            "Examples:\n"
            "/dice 5.50 - to play for $5.50\n"
            "/dice half - to play for half your balance\n"
            "/dice all - to play all-in",
            parse_mode="Markdown"
        )

    # Parse bet ONCE
    bet = parse_bet(args[0], bal)
    if bet <= 0 or bet > bal:
        return await update.message.reply_text(
            f"❗️ Insufficient balance: ${bal:.2f}"
        )

    # ✅ GAME STATE (OWNER ADDED)
    games[user.id] = {
        "owner":       user.id,      # 🔐 ONLY THIS USER CAN PRESS BUTTONS
        "bet":         bet,
        "mode":        None,
        "to_win":      None,
        "stage":       "mode",
        "round_no":    1,
        "initial_first":"user",
        "score":       {"user":0,"bot":0},
        "bot_total":   [],
        "user_rolls":  [],
        "chat_id":     chat_id,
        "msg_id":      None
    }

    sent = await update.message.reply_text(
        f"{mention(user)}\nPlease choose game mode:",
        parse_mode="HTML",
        reply_markup=build_mode_keyboard()
    )

    games[user.id]["msg_id"] = sent.message_id
async def check_owner(q, state):
    if q.from_user.id != state["owner"]:
        await q.answer("❌ This is not your game.", show_alert=True)
        return False
    return True

# ─────────────────────────────────────────────────────────────────────────────
#                           Mode Selection
# ─────────────────────────────────────────────────────────────────────────────
async def mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user  = q.from_user
    data  = q.data.split(":", 1)[1]
    state = games.get(user.id)

    if not state or state["stage"] != "mode":
        return await q.edit_message_text("⚠ No game in progress.")

    state = games.get(user.id)
    if not state or state["stage"] != "points":
        return await q.edit_message_text("⚠ No game in progress.")

    if not await check_owner(q, state):
        return

    if data == "guide":
        return await q.edit_message_text(
            "🎲 *Game Modes*\n\n"
            "*Normal Mode*\n"
            "Basic game mode. You take turns rolling the dice, and whoever has the highest digit wins the round.\n\n"
            "*Double Roll*\n"
            "Similar to Normal, but you are rolling 2 dice in a row. The winner of the round is the one who has the greater sum of the two dice’s digits.\n\n"
            "*Crazy Mode*\n"
            "Are you rolling low all night? Then this Crazy Mode is for you! In this gamemode it’s all about rolling low! All dice are inverted – 6 is 1 and 1 is 6. Will you be able to keep from going crazy?",
            parse_mode="Markdown"
        )

    if data == "cancel":
        del games[user.id]
        return await q.edit_message_text("❌ Game cancelled.")

    state["mode"]  = data
    state["stage"] = "points"

    await q.edit_message_text(
        "Select number of points to win:",
        reply_markup=build_points_keyboard()
    )

# ─────────────────────────────────────────────────────────────────────────────
#                          Points Selection
# ─────────────────────────────────────────────────────────────────────────────
async def points_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q     = update.callback_query; await q.answer()
    user  = q.from_user
    pts   = int(q.data.split(":",1)[1])
    state = games.get(user.id)
    if not state or state["stage"] != "points":
        return await q.edit_message_text("⚠ No game in progress.")
    if pts not in (1,2,3):
        del games[user.id]
        return await q.edit_message_text("❌ Game cancelled.")

    state["to_win"] = pts
    state["stage"]  = "confirm"

    await q.edit_message_text(
        "🎲 <b>Game confirmation</b>\n\n"
        "<b>Game: Dice 🎲</b>\n"
        f"<b>First to {pts} points</b>\n"
        f"<b>Mode: {state['mode'].title()}</b>\n"
        f"<b>Your bet: ${state['bet']:,.2f}</b>\n"
        "<b>Win multiplier: 1.92×</b>",
        parse_mode="HTML",
        reply_markup=build_confirm_keyboard()
    )


# ─────────────────────────────────────────────────────────────────────────────
#                        Confirmation Stage
# ─────────────────────────────────────────────────────────────────────────────
async def confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q      = update.callback_query; await q.answer()
    user   = q.from_user
    choice = q.data.split(":",1)[1]
    state  = games.get(user.id)
    if not state or state["stage"]!="confirm":
        return await q.edit_message_text("⚠ No game in progress.")

    if choice!="yes":
        del games[user.id]
        return await q.edit_message_text("❌ Game cancelled.")

    # mode description
    if state["mode"]=="normal":
        desc = (
            "*Normal Mode*\n"
            "Basic game mode. You take turns rolling the dice, and whoever has the highest digit wins the round.\n\n"
        )
    elif state["mode"]=="double":
        desc = (
            "*Double Roll*\n"
            "Similar to Normal, but you are rolling 2 dice in a row. "
            "The winner of the round is the one who has the greater sum of the two dice’s digits.\n\n"
        )
    else:
        desc = (
            "*Crazy Mode*\n"
            "Are you rolling low all night? Then this Crazy Mode is for you! "
            "In this gamemode it’s all about rolling low! All dice are inverted – 6 is 1 and 1 is 6. "
            "Will you be able to keep from going crazy?\n\n"
        )


        
    state["stage"] = "accept"
    username_text = f"<b>{user.first_name}</b>"

    await q.edit_message_text(
    f"🎲 {username_text} wants to play Dice!\n\n"
    f"Bet: <b>${state['bet']:,.2f}</b>\n"
    f"Win multiplier: <b>1.92×</b>\n"
    f"Mode: First to <b>{state['to_win']}</b> point{'s' if state['to_win']>1 else ''}\n\n"
    f"<b>{state['mode'].title()} Mode</b>\n"
    "Basic game mode. You take turns rolling the dice, and whoever has the highest digit wins the round.\n\n"
    "<i>If you want to play, click the \"Accept Match\" button</i>",
    parse_mode="HTML",
    reply_markup=build_accept_keyboard()
)



# ─────────────────────────────────────────────────────────────────────────────
#                     Accept Match / Play vs Bot
# ─────────────────────────────────────────────────────────────────────────────
async def accept_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q      = update.callback_query
    await q.answer()
    user   = q.from_user
    choice = q.data.split(":",1)[1]
    state  = games.get(user.id)
    if not state or state["stage"]!="accept":
        return await q.edit_message_text("⚠ No game in progress.", parse_mode="HTML")

    state["player1"]   = user.id
    state["player2"]   = user.id if choice=="yes" else "bot"
    state["stage"]     = "playing"
    state["round_no"]  = 1

    # only bold the first name now
    username_text = f"<b>{user.first_name}</b>"

    await q.edit_message_text(
        "🎲 Match accepted!\n\n"
        f"Player 1: {username_text}\n"
        "Player 2: Bot\n\n"
        f"{username_text}, your turn! To start, send this emoji: 🎲",
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────────────────────────────────────
#                            Round Starter Helper
# ─────────────────────────────────────────────────────────────────────────────

async def start_round(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    state   = games[user_id]
    chat_id = state["chat_id"]
    rn      = state["round_no"]
    init    = state["initial_first"]

    # Who rolls first this round?
    roller = init if (rn % 2) == 1 else ("bot" if init == "user" else "user")

    if roller == "bot":
        # Bot rolls first
        dice_ct = 2 if state["mode"] == "double" else 1
        rolls = []
        for _ in range(dice_ct):
            dmsg = await helper_bot.send_dice(chat_id=chat_id, emoji="🎲")
            await asyncio.sleep(1)
            rolls.append(dmsg.dice.value)
        state["bot_total"] = rolls if dice_ct > 1 else rolls[0]
        state["bot_has_rolled"] = True

        # Now ping the user to roll — reply to their last dice, use full name
        member = await context.bot.get_chat_member(chat_id, user_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{member.user.full_name}, your turn!",
            reply_to_message_id=state.get("last_user_dice_msg_id"),
            parse_mode="HTML"
        )
    else:
        # User rolls first
        member = await context.bot.get_chat_member(chat_id, user_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{member.user.full_name}, your turn! Send 🎲",
            parse_mode="HTML"
        )


# ─────────────────────────────────────────────────────────────────────────────
#                       Handle User’s Dice Emojis (UPDATED)
# ─────────────────────────────────────────────────────────────────────────────
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def cashout_multiplier(us: int, bs: int, to_win: int) -> float:
    """
    Fixed cashout tables.

    to_win == 3:
      - Ties -> 0.92x
      - Anchors from your spec:
          (0,2)->0.23, (0,1)->0.58, (1,2)->0.46, (2,0)->1.61
      - Symmetry: M(us,bs) = 0.92 + (0.92 - M(bs,us))

    to_win == 2:
      - Ties -> 0.92x
      - Opponent on game point (0,1) is harsher (map like 1–2 in first-to-3): 0.46x
      - Symmetry gives (1,0) = 1.38x
    """
    if to_win == 3:
        if us == bs:
            return 0.92
        table = {
            (0, 2): 0.23,
            (0, 1): 0.58,
            (1, 2): 0.46,
            (2, 0): 1.61,
            (1, 0): 0.92 + (0.92 - 0.58),  # 1.26
            (2, 1): 0.92 + (0.92 - 0.46),  # 1.38
        }
        return round(table.get((us, bs), 0.92), 2)

    if to_win == 2:
        if us == bs:
            return 0.92
        table = {
            (0, 1): 0.46,                          # you are down & they’re on game point
            (1, 0): 0.92 + (0.92 - 0.46),          # 1.38 (symmetry)
        }
        return round(table.get((us, bs), 0.92), 2)

    # Fallback for other match lengths (keep your existing logic if desired)
    base = 0.92
    prog = us / to_win if to_win else 0.0
    lead = us - bs
    mult = base + 0.30 * prog + 0.25 * lead
    return round(max(0.08, min(mult, 1.80)), 2)


async def handle_user_rolls(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles user's 🎲 dice messages during an active match.
    - Records user roll(s)
    - If user goes first -> replies "Bot, your turn!" to the user's dice and makes the bot roll
    - If bot goes first -> after bot roll it replies to the user's last message: "<you>, your turn!"
    - Computes round result, updates score, checks match end
    - Sends threaded prompts and score updates
    """
    msg = update.message
    if not msg or not msg.dice or msg.dice.emoji != "🎲":
        return

    uid   = msg.from_user.id
    state = games.get(uid)
    if not state or state.get("stage") != "playing":
        return

    # Track anchor to reply to
    state["last_user_dice_msg_id"] = msg.message_id

    # Record user's roll(s)
    state.setdefault("user_rolls", [])
    state["user_rolls"].append(msg.dice.value)
    needed = 2 if state["mode"] == "double" else 1

    # If double-roll and only 1 roll received so far, ask for the second roll
    if len(state["user_rolls"]) < needed:
        return await msg.reply_text(
            f"<b>{msg.from_user.full_name}</b>, one more turn!",
            parse_mode="HTML"
        )

    # Determine who should have rolled first this round
    rn = state["round_no"]
    first_roller = state["initial_first"] if (rn % 2) == 1 else ("bot" if state["initial_first"] == "user" else "user")

    # ========== When user goes first: make bot roll now and thread the prompt ==========
    if first_roller == "user" and not state.get("bot_total"):
        await context.bot.send_message(
            chat_id=state["chat_id"],
            text="Bot, your turn!",
            parse_mode="HTML",
            reply_to_message_id=state["last_user_dice_msg_id"]
        )
        bot_rolls = []
        for _ in range(needed):
            dmsg = await helper_bot.send_dice(chat_id=state["chat_id"], emoji="🎲")
            await asyncio.sleep(1)
            bot_rolls.append(dmsg.dice.value)
        state["bot_total"] = bot_rolls if needed > 1 else bot_rolls[0]
        state["bot_has_rolled"] = True

    # ========== When bot goes first but hasn't rolled yet (user rolled prematurely) ==========
    if first_roller == "bot" and not state.get("bot_total"):
        # Ask the bot to roll first, then tell the user "Your turn!" replying to user's dice
        await context.bot.send_message(
            chat_id=state["chat_id"],
            text="Bot, your turn!",
            parse_mode="HTML",
            reply_to_message_id=state["last_user_dice_msg_id"]
        )
        bot_rolls = []
        for _ in range(needed):
            dmsg = await helper_bot.send_dice(chat_id=state["chat_id"], emoji="🎲")
            await asyncio.sleep(1)
            bot_rolls.append(dmsg.dice.value)
        state["bot_total"] = bot_rolls if needed > 1 else bot_rolls[0]
        state["bot_has_rolled"] = True

        # Tag the user that it's their turn, threaded to their last dice
        await context.bot.send_message(
            chat_id=state["chat_id"],
            text=f"<b>{msg.from_user.full_name}</b>, your turn!",
            parse_mode="HTML",
            reply_to_message_id=state["last_user_dice_msg_id"]
        )
        # Return here because user already rolled; next code will evaluate the result below

    # ========== Both have rolled -> decide the round ==========
    ut = sum(state["user_rolls"])
    bt = state["bot_total"]
    if isinstance(bt, list):
        bt = sum(bt)

    # Crazy mode inversion
    if state["mode"] == "crazy":
        ut = sum(7 - v for v in state["user_rolls"])
        bt = sum(7 - v for v in (state["bot_total"] if isinstance(state["bot_total"], list) else [state["bot_total"]]))

    round_no = state["round_no"]
    if ut == bt:
        # draw: no score change
        round_text = (
            f"<b>Round {round_no} result:</b>\n"
            f"{msg.from_user.full_name} rolled <b>{ut}</b>\n"
            f"🤖 Bot rolled <b>{bt}</b>\n\n"
            "🤝 <b>It’s a draw!</b>\n"
        )
    else:
        user_wins = (ut < bt) if state["mode"] == "crazy" else (ut > bt)
        winner = "user" if user_wins else "bot"
        state["score"][winner] += 1
        round_text = (
            f"<b>Round {round_no} result:</b>\n"
            f"{msg.from_user.full_name} rolled <b>{ut}</b>\n"
            f"🤖 Bot rolled <b>{bt}</b>\n\n"
            f"✅ Round over: <b>{'You' if winner == 'user' else 'Bot'} wins!</b>\n"
        )

    us, bs = state["score"]["user"], state["score"]["bot"]

    # ========== Match end? ==========
    if max(us, bs) >= state["to_win"]:
        winner = "user" if us > bs else "bot"
        payout = round(state["bet"] * (BASE_PAYOUT if winner == "user" else 0), 2)

        # Balance + stats
        update_balance(uid, -state["bet"])
        add_wager(uid, state["bet"])
        if winner == "user":
            update_balance(uid, payout)

        save_session(
            uid,
            f"{state['mode']}_{state['to_win']}",
            state["bet"],
            payout,
            winner == "user"
        )

        member = await context.bot.get_chat_member(state["chat_id"], uid)
        header = (
            "🏆 Game over!\n\n"
            "Score:\n"
            f"{mention(member.user)} • <b>{us}</b>\n"
            f"Bot • <b>{bs}</b>\n\n"
        )
        if winner == "user":
            body = f"🎉 Congratulations, {member.user.full_name}! You won <b>${payout:.2f}</b>!"
            end_amt = payout
        else:
            bot_win_amt = round(state["bet"] * BASE_PAYOUT, 2)
            body = f"🤖 Bot wins <b>${bot_win_amt:.2f}</b>!"
            end_amt = bot_win_amt

        await context.bot.send_message(
            chat_id=state["chat_id"],
            text=header + body,
            parse_mode="HTML",
            reply_to_message_id=state.get("last_user_dice_msg_id"),
            reply_markup=build_end_keyboard(state["bet"], end_amt)
        )

        del games[uid]
        return

    # ========== Prepare for next round ==========
    state["round_no"] += 1
    state["user_rolls"].clear()
    state["bot_total"] = []
    state["bot_has_rolled"] = False

    # Who starts next
    rn_next    = state["round_no"]
    next_first = state["initial_first"] if (rn_next % 2) == 1 else ("bot" if state["initial_first"] == "user" else "user")

    member       = await context.bot.get_chat_member(state["chat_id"], uid)
    user_display = f"<b>{member.user.full_name}</b>"
    prompt       = f"{user_display}, your turn!" if next_first == "user" else "Bot, your turn!"

    score_text = (
        f"Score\n\n"
        f"{user_display}: {us}\n"
        f"Bot: {bs}\n\n"
        f"{prompt}"
    )

    # Cashout button only when it's user's turn to start the next round
    if next_first == "user":
        mult        = cashout_multiplier(us, bs, state["to_win"])
        cashout_amt = round(state["bet"] * mult, 2)
        cash_label  = f"Cashout ${cashout_amt:.2f} (x{mult:.2f})"
        sent = await context.bot.send_message(
            chat_id=state["chat_id"],
            text=score_text,
            parse_mode="HTML",
            reply_to_message_id=state.get("last_user_dice_msg_id"),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(cash_label, callback_data="action:cashout")]])
        )
        state["last_score_msg_id"] = sent.message_id
    else:
        # Tell bot to roll immediately for next round (and keep it threaded)
        await context.bot.send_message(
            chat_id=state["chat_id"],
            text=score_text,
            parse_mode="HTML",
            reply_to_message_id=state.get("last_user_dice_msg_id")
        )
        # Bot actually rolls now for the next round
        bot_rolls = []
        for _ in range(needed):
            dmsg = await helper_bot.send_dice(chat_id=state["chat_id"], emoji="🎲")
            await asyncio.sleep(1)
            bot_rolls.append(dmsg.dice.value)
        state["bot_total"] = bot_rolls if needed > 1 else bot_rolls[0]
        state["bot_has_rolled"] = True

        # After bot finishes rolling first, ping the user under their last 🎲
        await context.bot.send_message(
            chat_id=state["chat_id"],
            text=f"{member.user.full_name}, your turn!",
            reply_to_message_id=state.get("last_user_dice_msg_id"),
            parse_mode="HTML"
        )



# ─────────────────────────────────────────────────────────────────────────────
#                       Next Round & Cashout (patched)
# ─────────────────────────────────────────────────────────────────────────────
async def action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q     = update.callback_query; await q.answer()
    uid   = q.from_user.id
    state = games.get(uid)
    if not state or state["stage"] != "playing":
        return

    action = q.data.split(":",1)[1]
    us, bs  = state["score"]["user"], state["score"]["bot"]

    if action == "next":
        dice_ct = 2 if state["mode"] == "double" else 1
        rolls   = []
        for _ in range(dice_ct):
            dmsg = await helper_bot.send_dice(
                chat_id=state["chat_id"],
                emoji="🎲"
            )
            await asyncio.sleep(2)
            rolls.append(dmsg.dice.value)
        # store raw rolls list
        state["bot_total"] = rolls

        # prompt user
        await context.bot.send_message(
            chat_id=state["chat_id"],
            text=(
                f"{mention(context.bot.get_chat(state['chat_id']).get_member(uid).user)}\n"
                "🎲 Your turn!"
            ),
            parse_mode="HTML"
        )

    elif action == "cashout":
        us = state["score"]["user"]
        bs = state["score"]["bot"]
        mult = cashout_multiplier(us, bs, state["to_win"])
        cash = round(state["bet"] * mult, 2)
        update_balance(uid, -state["bet"])
        update_balance(uid, cash)
        add_wager(uid, state["bet"])
        save_session(
            uid,
            f"{state['mode']}_{state['to_win']}_cashout",
            state["bet"],
            cash,
            True
        )
        member = await context.bot.get_chat_member(state["chat_id"], uid)
        user_display = f"<b>{member.user.first_name}</b>"
        await context.bot.edit_message_text(
            chat_id=state["chat_id"],
            message_id=state.get("last_score_msg_id"),
            text=f"💸 {user_display} cashed out <b>${cash:.2f}</b>!",
            parse_mode="HTML"
        )

        del games[uid]
        return


# ─────────────────────────────────────────────────────────────────────────────
#                            Replay & Double
# ─────────────────────────────────────────────────────────────────────────────

async def replay_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    bet = safe_parse_float(q.data.split(":",1)[1])
    context.args = [str(bet)]
    await dice_command(update, context)

async def double_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q      = update.callback_query; await q.answer()
    payout = safe_parse_float(q.data.split(":",1)[1])
    context.args = [str(payout)]
    await dice_command(update, context)

