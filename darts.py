# darts.py

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

# Prefix for callback_data to avoid overlap with dice
DART_PREFIX = "dart"

# ─────────────────────────────────────────────────────────────────────────────
#                         Darts Game Configuration
# ─────────────────────────────────────────────────────────────────────────────

BASE_PAYOUT = 1.92   # uniform payout multiplier for all modes

# In-memory game state
# dart_games[user_id] = {
#    bet, mode, to_win, stage,
#    round_no, initial_first,
#    score: {user,bot},
#    bot_total (list), user_throws,
#    chat_id, msg_id
# }
dart_games = {}

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
        [InlineKeyboardButton("Normal Mode",   callback_data=f"{DART_PREFIX}:mode:normal")],
        [InlineKeyboardButton("Double Throw",  callback_data=f"{DART_PREFIX}:mode:double")],
        [InlineKeyboardButton("Crazy Mode",    callback_data=f"{DART_PREFIX}:mode:crazy")],
        [
            InlineKeyboardButton("ℹ Mode Guide", callback_data=f"{DART_PREFIX}:mode:guide"),
            InlineKeyboardButton("❌ Cancel",     callback_data=f"{DART_PREFIX}:cancel")
        ]
    ])

def build_points_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("First to 3 points", callback_data=f"{DART_PREFIX}:points:3")],
        [InlineKeyboardButton("First to 2 points", callback_data=f"{DART_PREFIX}:points:2")],
        [InlineKeyboardButton("First to 1 point",  callback_data=f"{DART_PREFIX}:points:1")],
        [InlineKeyboardButton("❌ Cancel",         callback_data=f"{DART_PREFIX}:cancel")]
    ])

def build_confirm_keyboard():
    return InlineKeyboardMarkup([[ 
        InlineKeyboardButton("✅ Confirm", callback_data=f"{DART_PREFIX}:confirm:yes"),
        InlineKeyboardButton("❌ Cancel",  callback_data=f"{DART_PREFIX}:cancel")
    ]])

def build_accept_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Accept Match",     callback_data=f"{DART_PREFIX}:accept:yes"),
            InlineKeyboardButton("✅ Play against bot", callback_data=f"{DART_PREFIX}:accept:bot")
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"{DART_PREFIX}:cancel")]
    ])

def build_next_round_keyboard(us: int, bs: int, to_win: int):
    mult = cashout_multiplier(us, bs, to_win)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Next Round",       callback_data=f"{DART_PREFIX}:action:next")],
        [InlineKeyboardButton(f"💸 Cashout {mult}×", callback_data=f"{DART_PREFIX}:action:cashout")]
    ])

def build_end_keyboard(bet: float, payout: float):
    return InlineKeyboardMarkup([[ 
        InlineKeyboardButton("🔄 Play Again", callback_data=f"{DART_PREFIX}:replay:{bet}"),
        InlineKeyboardButton("✖ Double",      callback_data=f"{DART_PREFIX}:double:{payout}")
    ]])

# ─────────────────────────────────────────────────────────────────────────────
#                            /dart Command
# ─────────────────────────────────────────────────────────────────────────────

async def dart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    bal     = get_balance(user.id)
    args    = context.args
    chat_id = update.effective_chat.id

    if not args:
        return await update.message.reply_text(
            "🎯 *Play Darts*\n\n"
            "To play, type the command /dart with the desired bet.\n\n"
            "Examples:\n"
            "/dart 5.50 - to play for $5.50\n"
            "/dart half - to play for half your balance\n"
            "/dart all - to play all-in",
            parse_mode="Markdown"
        )

    bet = parse_bet(args[0], bal)
    if bet <= 0 or bet > bal:
        return await update.message.reply_text(f"❗️ Insufficient balance: ${bal:.2f}")

    dart_games[user.id] = {
        "bet":         bet,
        "mode":        None,
        "to_win":      None,
        "stage":       "mode",
        "round_no":    1,
        "initial_first":"user",
        "score":       {"user":0,"bot":0},
        "bot_total":   [],        # store as list now
        "user_throws": [],
        "chat_id":     chat_id,
        "msg_id":      None
    }

    sent = await update.message.reply_text(
        f"{mention(user)}\nPlease choose game mode:",
        parse_mode="HTML",
        reply_markup=build_mode_keyboard()
    )
    dart_games[user.id]["msg_id"] = sent.message_id

# ─────────────────────────────────────────────────────────────────────────────
#                           Mode Selection
# ─────────────────────────────────────────────────────────────────────────────
async def mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    user = q.from_user
    parts = q.data.split(":", 2)
    if len(parts) < 2 or parts[0] != DART_PREFIX or parts[1] != "mode":
        return
    value = parts[2] if len(parts) > 2 else None

    state = dart_games.get(user.id)
    if not state or state["stage"] != "mode":
        return await q.edit_message_text("⚠ No game in progress.")

    if value == "guide":
        return await q.edit_message_text(
            "🎯 *Game Modes*\n\n"
            "*Normal Mode*\n"
            "Basic game mode. You take turns throwing the darts, and whoever has the highest digit wins the round.\n\n"
            "*Double Throw*\n"
            "Similar to Normal, but you are throwing 2 darts in a row. The winner of the round is the one who has the greater sum of the two darts’ digits.\n\n"
            "*Crazy Mode*\n"
            "Are you throwing low all night? Then this Crazy Mode is for you! In this gamemode it’s all about throwing low! All darts are inverted – 6 is 1 and 1 is 6. Will you be able to keep from going crazy?",
            parse_mode="Markdown"
        )

    if value == "cancel":
        del dart_games[user.id]
        return await q.edit_message_text("❌ Game cancelled.")

    state["mode"]  = value
    state["stage"] = "points"
    await q.edit_message_text(
        "Select number of points to win:",
        reply_markup=build_points_keyboard()
    )

# ─────────────────────────────────────────────────────────────────────────────
#                          Points Selection
# ─────────────────────────────────────────────────────────────────────────────
async def points_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    user = q.from_user
    parts = q.data.split(":", 2)
    if len(parts) < 3 or parts[0] != DART_PREFIX or parts[1] != "points":
        return
    pts = int(parts[2])

    state = dart_games.get(user.id)
    if not state or state["stage"] != "points":
        return await q.edit_message_text("⚠ No game in progress.")
    if pts not in (1,2,3):
        del dart_games[user.id]
        return await q.edit_message_text("❌ Game cancelled.")

    state["to_win"] = pts
    state["stage"]  = "confirm"

    await q.edit_message_text(
        "🎯 <b>Game confirmation</b>\n\n"
        "<b>Game: Darts 🎯</b>\n"
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
    q = update.callback_query; await q.answer()
    user = q.from_user
    parts = q.data.split(":", 2)
    if len(parts) < 3 or parts[0] != DART_PREFIX or parts[1] != "confirm":
        return
    choice = parts[2]

    state  = dart_games.get(user.id)
    if not state or state["stage"]!="confirm":
        return await q.edit_message_text("⚠ No game in progress.")

    if choice!="yes":
        del dart_games[user.id]
        return await q.edit_message_text("❌ Game cancelled.")

    if state["mode"]=="normal":
        desc = (
            "*Normal Mode*\n"
            "Basic game mode. You take turns throwing the darts, and whoever has the highest digit wins the round.\n\n"
        )
    elif state["mode"]=="double":
        desc = (
            "*Double Throw*\n"
            "Similar to Normal, but you are throwing 2 darts in a row. "
            "The winner of the round is the one who has the greater sum of the two darts’ digits.\n\n"
        )
    else:
        desc = (
            "*Crazy Mode*\n"
            "Are you throwing low all night? Then this Crazy Mode is for you! "
            "In this gamemode it’s all about throwing low! All darts are inverted – 6 is 1 and 1 is 6. "
            "Will you be able to keep from going crazy?\n\n"
        )

    state["stage"] = "accept"
    username_text = f"<b>{user.first_name}</b>"

    await q.edit_message_text(
        f"🎯 {username_text} wants to play Darts!\n\n"
        f"Bet: <b>${state['bet']:,.2f}</b>\n"
        f"Win multiplier: <b>1.92×</b>\n"
        f"Mode: First to <b>{state['to_win']}</b> point{'s' if state['to_win']>1 else ''}\n\n"
        f"<b>{state['mode'].title()} Mode</b>\n"
        f"{desc}"
        "<i>If you want to play, click the \"Accept Match\" button</i>",
        parse_mode="HTML",
        reply_markup=build_accept_keyboard()
    )

# ─────────────────────────────────────────────────────────────────────────────
#                     Accept Match / Play vs Bot
# ─────────────────────────────────────────────────────────────────────────────
async def accept_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    user = q.from_user
    parts = q.data.split(":", 2)
    if len(parts) < 3 or parts[0] != DART_PREFIX or parts[1] != "accept":
        return
    choice = parts[2]

    state  = dart_games.get(user.id)
    if not state or state["stage"]!="accept":
        return await q.edit_message_text("⚠ No game in progress.", parse_mode="HTML")

    state["player1"]   = user.id
    state["player2"]   = user.id if choice=="yes" else "bot"
    state["stage"]     = "playing"
    state["round_no"]  = 1

    username_text = f"<b>{user.first_name}</b>"

    await q.edit_message_text(
        "🎯 Match accepted!\n\n"
        f"Player 1: {username_text}\n"
        "Player 2: Bot\n\n"
        f"{username_text}, your turn! To start, send this emoji: 🎯",
        parse_mode="HTML"
    )

# ─────────────────────────────────────────────────────────────────────────────
#                            Round Starter Helper
# ─────────────────────────────────────────────────────────────────────────────

async def start_round(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    state   = dart_games[user_id]
    chat_id = state["chat_id"]
    rn      = state["round_no"]
    init    = state["initial_first"]

    # Who throws first this round?
    thrower = init if (rn % 2) == 1 else ("bot" if init == "user" else "user")

    if thrower == "bot":
        # Bot throws first
        dart_ct = 2 if state["mode"] == "double" else 1
        throws = []
        for _ in range(dart_ct):
            dmsg = await helper_bot.send_dice(chat_id=chat_id, emoji="🎯")
            await asyncio.sleep(1)
            throws.append(dmsg.dice.value)
        state["bot_total"] = throws if dart_ct > 1 else throws[0]
        state["bot_has_thrown"] = True

        # Now ping the user to throw — reply to their last dart, use full name
        member = await context.bot.get_chat_member(chat_id, user_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{member.user.full_name}, your turn!",
            reply_to_message_id=state.get("last_user_dart_msg_id"),
            parse_mode="HTML"
        )
    else:
        # User throws first
        member = await context.bot.get_chat_member(chat_id, user_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{member.user.full_name}, your turn! Send 🎯",
            parse_mode="HTML"
        )

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
# ─────────────────────────────────────────────────────────────────────────────
#                       Handle User’s Dart Emojis
# ─────────────────────────────────────────────────────────────────────────────
async def handle_user_throws(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles user's 🎯 dart messages during an active match.
    - Records user throw(s)
    - If user goes first -> replies "Bot, your turn!" to the user's dart and makes the bot throw
    - If bot goes first -> after bot throw it replies to the user's last message: "<you>, your turn!"
    - Computes round result, updates score, checks match end
    - Sends threaded prompts and score updates
    """
    msg = update.message
    if not msg or not msg.dice or msg.dice.emoji != "🎯":
        return

    uid   = msg.from_user.id
    state = dart_games.get(uid)
    if not state or state.get("stage") != "playing":
        return

    # Track anchor to reply to
    state["last_user_dart_msg_id"] = msg.message_id

    # Record user's throw(s)
    state.setdefault("user_throws", [])
    state["user_throws"].append(msg.dice.value)
    needed = 2 if state["mode"] == "double" else 1

    # If double-throw and only 1 throw received so far, ask for the second throw
    if len(state["user_throws"]) < needed:
        return await msg.reply_text(
            f"<b>{msg.from_user.full_name}</b>, one more throw!",
            parse_mode="HTML"
        )

    # Determine who should have thrown first this round
    rn = state["round_no"]
    first_thrower = state["initial_first"] if (rn % 2) == 1 else ("bot" if state["initial_first"] == "user" else "user")

    # ========== When user goes first: make bot throw now and thread the prompt ==========
    if first_thrower == "user" and not state.get("bot_total"):
        await context.bot.send_message(
            chat_id=state["chat_id"],
            text="Bot, your turn!",
            parse_mode="HTML",
            reply_to_message_id=state["last_user_dart_msg_id"]
        )
        bot_throws = []
        for _ in range(needed):
            dmsg = await helper_bot.send_dice(chat_id=state["chat_id"], emoji="🎯")
            await asyncio.sleep(1)
            bot_throws.append(dmsg.dice.value)
        state["bot_total"] = bot_throws if needed > 1 else bot_throws[0]
        state["bot_has_thrown"] = True

    # ========== When bot goes first but hasn't thrown yet (user threw prematurely) ==========
    if first_thrower == "bot" and not state.get("bot_total"):
        # Ask the bot to throw first, then tell the user "Your turn!" replying to user's dart
        await context.bot.send_message(
            chat_id=state["chat_id"],
            text="Bot, your turn!",
            parse_mode="HTML",
            reply_to_message_id=state["last_user_dart_msg_id"]
        )
        bot_throws = []
        for _ in range(needed):
            dmsg = await helper_bot.send_dice(chat_id=state["chat_id"], emoji="🎯")
            await asyncio.sleep(1)
            bot_throws.append(dmsg.dice.value)
        state["bot_total"] = bot_throws if needed > 1 else bot_throws[0]
        state["bot_has_thrown"] = True

        # Tag the user that it's their turn, threaded to their last dart
        await context.bot.send_message(
            chat_id=state["chat_id"],
            text=f"<b>{msg.from_user.full_name}</b>, your turn!",
            parse_mode="HTML",
            reply_to_message_id=state["last_user_dart_msg_id"]
        )
        # Return here because user already threw; next code will evaluate the result below

    # ========== Both have thrown -> decide the round ==========
    ut = sum(state["user_throws"])
    bt = state["bot_total"]
    if isinstance(bt, list):
        bt = sum(bt)

    # Crazy mode inversion
    if state["mode"] == "crazy":
        ut = sum(7 - v for v in state["user_throws"])
        bt = sum(7 - v for v in (state["bot_total"] if isinstance(state["bot_total"], list) else [state["bot_total"]]))

    round_no = state["round_no"]
    if ut == bt:
        round_text = (
            f"<b>Round {round_no} result:</b>\n"
            f"{msg.from_user.full_name} threw <b>{ut}</b>\n"
            f"🤖 Bot threw <b>{bt}</b>\n\n"
            "🤝 <b>It’s a draw!</b>\n"
        )
    else:
        user_wins = (ut < bt) if state["mode"] == "crazy" else (ut > bt)
        winner = "user" if user_wins else "bot"
        state["score"][winner] += 1
        round_text = (
            f"<b>Round {round_no} result:</b>\n"
            f"{msg.from_user.full_name} threw <b>{ut}</b>\n"
            f"🤖 Bot threw <b>{bt}</b>\n\n"
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
            reply_to_message_id=state.get("last_user_dart_msg_id"),
            reply_markup=build_end_keyboard(state["bet"], end_amt)
        )

        del dart_games[uid]
        return

    # ========== Prepare for next round ==========
    state["round_no"] += 1
    state["user_throws"].clear()
    state["bot_total"] = []
    state["bot_has_thrown"] = False

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

    if next_first == "user":
        mult        = cashout_multiplier(us, bs, state["to_win"])
        cashout_amt = round(state["bet"] * mult, 2)
        cash_label  = f"Cashout ${cashout_amt:.2f} (x{mult:.2f})"
        sent = await context.bot.send_message(
            chat_id=state["chat_id"],
            text=score_text,
            parse_mode="HTML",
            reply_to_message_id=state.get("last_user_dart_msg_id"),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(cash_label, callback_data=f"{DART_PREFIX}:action:cashout")]])
        )
        state["last_score_msg_id"] = sent.message_id
    else:
        await context.bot.send_message(
            chat_id=state["chat_id"],
            text=score_text,
            parse_mode="HTML",
            reply_to_message_id=state.get("last_user_dart_msg_id")
        )
        # Bot actually throws now for the next round
        bot_throws = []
        for _ in range(needed):
            dmsg = await helper_bot.send_dice(chat_id=state["chat_id"], emoji="🎯")
            await asyncio.sleep(1)
            bot_throws.append(dmsg.dice.value)
        state["bot_total"] = bot_throws if needed > 1 else bot_throws[0]
        state["bot_has_thrown"] = True

        # After bot finishes throwing first, ping the user under their last 🎯
        await context.bot.send_message(
            chat_id=state["chat_id"],
            text=f"{member.user.full_name}, your turn!",
            reply_to_message_id=state.get("last_user_dart_msg_id"),
            parse_mode="HTML"
        )

# ─────────────────────────────────────────────────────────────────────────────
#                       Next Round & Cashout
# ─────────────────────────────────────────────────────────────────────────────
async def action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    state = dart_games.get(uid)
    if not state or state["stage"] != "playing":
        return

    parts = q.data.split(":", 2)
    if len(parts) < 3 or parts[0] != DART_PREFIX or parts[1] != "action":
        return
    action = parts[2]

    us, bs = state["score"]["user"], state["score"]["bot"]

    if action == "next":
        dart_ct = 2 if state["mode"] == "double" else 1
        throws = []
        for _ in range(dart_ct):
            dmsg = await helper_bot.send_dice(
                chat_id=state["chat_id"],
                emoji="🎯"
            )
            await asyncio.sleep(2)
            throws.append(dmsg.dice.value)
        state["bot_total"] = throws

        await context.bot.send_message(
            chat_id=state["chat_id"],
            text=f"{mention(q.from_user)}\n🎯 Your turn!",
            parse_mode="HTML"
        )

    elif action == "cashout":
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
        user_display = f"<b>{member.user.full_name}</b>"
        await context.bot.edit_message_text(
            chat_id=state["chat_id"],
            message_id=state.get("last_score_msg_id"),
            text=f"💸 {user_display} cashed out <b>${cash:.2f}</b>!",
            parse_mode="HTML"
        )

        del dart_games[uid]
        return

# ─────────────────────────────────────────────────────────────────────────────
#                            Replay & Double
# ─────────────────────────────────────────────────────────────────────────────

async def replay_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    parts = q.data.split(":", 2)
    if len(parts) < 3 or parts[0] != DART_PREFIX or parts[1] != "replay":
        return
    bet = safe_parse_float(parts[2])
    context.args = [str(bet)]
    await dart_command(update, context)

async def double_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    parts = q.data.split(":", 2)
    if len(parts) < 3 or parts[0] != DART_PREFIX or parts[1] != "double":
        return
    payout = safe_parse_float(parts[2])
    context.args = [str(payout)]
    await dart_command(update, context)
