import os
import random
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes

from models import (
    get_connection,
    update_balance,
    log_transaction,
    update_stats,
)
from referral import track_referral_event

# ─── Configuration ────────────────────────────────────────────────────────────

MULTIPLIER   = 1.92
BOT_USERNAME = os.getenv("BOT_USERNAME", "Dice_GambleBot")
ADMIN_ID     = int(os.getenv("ADMIN_ID", "7900370587"))

# ─── Sticker IDs ──────────────────────────────────────────────────────────────

HEADS_STICKER = "CAACAgQAAxkBAANIaGzqueo_5O6IgBkP1tBaB5181vIAAo0aAAJM_nBRp2ONT4HzK6w2BA"
TAILS_STICKER = "CAACAgQAAxkBAANKaGzq0VkN8PO3QQzpLbWVWRMg398AAqQZAAIIAXBRhg46ea3-ER42BA"

# ─── Keyboards ─────────────────────────────────────────────────────────────────

def build_intro_kb():
    return InlineKeyboardMarkup([[  
        InlineKeyboardButton("🔄 Play Coinflip", callback_data="coin_start"),
        InlineKeyboardButton("❌ Cancel",       callback_data="coin_cancel"),
    ]])

def build_side_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Heads (Trump)",     callback_data="coin_side:heads")],
        [InlineKeyboardButton("Tails (Dice logo)", callback_data="coin_side:tails")],
        [InlineKeyboardButton("❌ Cancel",         callback_data="coin_cancel")],
    ])

def build_invite_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Accept Match",  callback_data="coin_accept_friend"),
            InlineKeyboardButton("🤖 Play against bot", callback_data="coin_accept_bot"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="coin_cancel"),
        ]
    ])


def build_flip_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪙 Flip the coin",  callback_data="coin_flip")],
    ])

def build_result_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Play Again",   callback_data="coin_start"),
            InlineKeyboardButton("2× Bet Again",    callback_data="coin_double"),
        ],
        [
            InlineKeyboardButton("🔍 Verify",       callback_data="coin_verify"),
        ]
    ])


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_balance(user_id: int) -> float:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0.0

def _record_match(user_id: int, bet: float, payout: float, is_win: int):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO game_sessions(user_id, mode, played_at, bet, won_amount, is_win) "
        "VALUES (?, 'coinflip', datetime('now'), ?, ?, ?)",
        (user_id, bet, payout, is_win)
    )
    conn.commit()
    conn.close()


# ─── /coin entrypoint ─────────────────────────────────────────────────────────

async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User sends /coin <amount>"""
    args = context.args
    user = update.effective_user
    bal  = _get_balance(user.id)

    # parse bet
    bet = 0.0
    if args:
        a = args[0].lower()
        if a == "half":
            bet = bal / 2
        elif a == "all":
            bet = bal
        else:
            try:
                bet = float(a)
            except ValueError:
                bet = 0.0

    # clear previous
    context.user_data.clear()
    context.user_data["coin_bet"] = round(bet, 2)

    if bet > 0:
        # record creator
        context.user_data["coin_creator_id"]   = user.id
        context.user_data["coin_creator_name"] = user.first_name

        # immediately ask for side (Image 2)
        await update.message.reply_text(
            f"🪙 *{user.first_name}*, choose the coin side:",
            parse_mode="Markdown",
            reply_markup=build_side_kb()
        )
    else:
        # show intro card (Image 1)
        await update.message.reply_text(
            "🪙 *Play Coinflip*\n\n"
            "To play, type the command `/coin <amount>`\n\n"
            "Examples:\n"
            "`/coin 5.50` – play for $5.50\n"
            "`/coin half`  – bet half your balance\n"
            "`/coin all`   – go all-in",
            parse_mode="Markdown",
            reply_markup=build_intro_kb()
        )


# ─── side chosen → invite ────────────────────────────────────────────────────

async def coin_side_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    await q.answer()
    side = q.data.split(":", 1)[1]
    context.user_data["coin_side"] = side

    bet   = context.user_data["coin_bet"]
    name  = context.user_data["coin_creator_name"]

    text = (
        f"{name} wants to play Coinflip!\n\n"
        f"Bet: *${bet:.2f}*\n"
        f"Win multiplier: *{MULTIPLIER:.2f}x*\n"
        "Mode: *First to 1 point*\n\n"
        "*Normal Mode*\n"
        "Basic game mode. You take turns rolling the dice, and whoever has the highest digit wins the round.\n\n"
        "_If you want to play, click the \"Accept Match\" button_"
    )

    await q.edit_message_text(text=text, parse_mode="Markdown", reply_markup=build_invite_kb())



# ─── accepted by friend ──────────────────────────────────────────────────────

async def coin_accept_friend_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Match accepted!")
    cd      = context.user_data
    creator = cd["coin_creator_id"], cd["coin_creator_name"]
    friend  = q.from_user

    # record players
    cd["coin_opponent_id"]   = friend.id
    cd["coin_opponent_name"] = friend.first_name

    # show accepted card (Image 3)
    text = (
        "🪙 *Match accepted!*\n\n"
        f"Player 1: *{cd['coin_creator_name']}*\n"
        f"Player 2: *{cd['coin_opponent_name']}*\n\n"
        f"{cd['coin_creator_name']}, your turn! To start, click the button below"
    )
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=build_flip_kb())


# ─── accepted vs bot ─────────────────────────────────────────────────────────

async def coin_accept_bot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Playing vs Bot!")
    cd      = context.user_data

    cd["coin_opponent_id"]   = None
    cd["coin_opponent_name"] = "Bot"

    text = (
        "🪙 *Match accepted!*\n\n"
        f"Player 1: *{cd['coin_creator_name']}*\n"
        "Player 2: *Bot*\n\n"
        f"{cd['coin_creator_name']}, your turn! To start, click the button below"
    )
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=build_flip_kb())


# ─── cancel ───────────────────────────────────────────────────────────────────

async def coin_cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Canceled.")
    await q.delete_message()


# ─── flip the coin → result ───────────────────────────────────────────────────
def build_flipped_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Flipped", callback_data="coin_locked")]
    ])
async def coin_flip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    cd = context.user_data

    # 🚫 Prevent double click exploit
    if cd.get("coin_flipped"):
        return

    cd["coin_flipped"] = True

    # ✅ Instantly lock button visually
    await q.edit_message_reply_markup(reply_markup=build_flipped_kb())

    user_id = cd["coin_creator_id"]
    bet     = cd["coin_bet"]
    chosen  = cd["coin_side"]

    # deduct bet
    update_balance(user_id, -bet)
    log_transaction(user_id, "coin_bet", bet, "coinflip")
    track_referral_event(user_id, bet * 0.10)

    # flip
    flip    = random.choice(["heads", "tails"])
    sticker = HEADS_STICKER if flip == "heads" else TAILS_STICKER
    await q.message.reply_sticker(sticker=sticker)

    # result
    win    = (flip == chosen)
    payout = round(bet * MULTIPLIER, 2) if win else 0.0

    if win:
        update_balance(user_id, payout)
        log_transaction(user_id, "coin_win", payout, f"×{MULTIPLIER:.2f}")
        update_stats(user_id, True)
    else:
        update_stats(user_id, False)

    _record_match(user_id, bet, payout, int(win))

    final_text = (
        "🏆 *Game over!*\n\n"
        "*Score:*\n"
        f"{cd['coin_creator_name']} • {1 if win else 0}\n"
        f"{cd['coin_opponent_name']} • {0 if win else 1}\n\n"
        + (
            f"🎉 Congratulations, *{cd['coin_creator_name']}*! You won *${payout:.2f}*"
            if win else
            f"{cd['coin_opponent_name']} wins *${payout:.2f}*!"
        )
    )

    await q.message.reply_text(
        final_text,
        parse_mode="Markdown",
        reply_markup=build_result_kb()
    )

# ─── verify placeholder ───────────────────────────────────────────────────────

async def coin_verify_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Verification not implemented.", show_alert=True)
