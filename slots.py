# slots.py

from __future__ import annotations
import os
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
)

from balance import get_balance, update_balance, add_wager
from models import get_connection, update_stats


# ─────────────────────────────────────────────────────────────────────────────
# Constants & State
# ─────────────────────────────────────────────────────────────────────────────

SLOTS_PREFIX = "slots"

# Telegram's 🎰 sends a value (1..64). Map it to multipliers you want to pay.
# NOTE: The exact mapping is Telegram-internal; adjust values if you want
# different payouts per symbol mix. Unknown values default to 0× (lose).
VALUE_TO_MULTIPLIER = {
    64: 25.0,  # 7 7 7 — 25x Jackpot (page 1)
    60: 7.0,   # 🍸🍸🍸 or other 7x examples
    56: 7.0,
    52: 7.0,
    48: 2.0,   # 7 7 ? — 2x
    44: 1.0,   # 7 ? 7 — 1x
    40: 0.5,   # 0.5x rows
    36: 0.25,  # 0.25x rows
    32: 0.25,
    # You can add more mappings if you want fine-grained outcomes
}

MIN_BET = 0.25


# ─────────────────────────────────────────────────────────────────────────────
# Text & Keyboards
# ─────────────────────────────────────────────────────────────────────────────

def combos_text(page: int = 0) -> str:
    pages = [
        (
            "<b>🏛️ Spin Slots</b>\n\n"
            "<b>Winning combinations:</b>\n\n"
            "7️⃣7️⃣7️⃣ — <b>25x Jackpot!</b>\n"
            "🍸🍸🍸 — <b>7x</b>\n"
            "🍋🍋🍋 — <b>7x</b>\n"
            "🍇🍇🍇 — <b>7x</b>\n"
            "7️⃣7️⃣❔ — <b>2x</b>\n"
            "7️⃣❔7️⃣ — <b>1x</b>\n"
            "🍸🍸❔ — <b>0.5x</b>\n"
            "🍋❔❔ — <b>0.25x</b>\n"
            "🍇❔❔ — <b>0.25x</b>\n\n"
            "🍀 <b>Good Luck!</b>"
        ),
        (
            "<b>🏛️ Spin Slots</b>\n\n"
            "<b>Winning combinations:</b>\n\n"
            "7️⃣7️⃣7️⃣ — <b>20x Jackpot!</b>\n"
            "7️⃣7️⃣❔ — <b>4x</b>\n"
            "7️⃣❔❔ — <b>1.5x</b>\n"
            "❔7️⃣❔ — <b>1.5x</b>\n"
            "❔❔7️⃣ — <b>1.3x</b>\n"
            "❔7️⃣7️⃣ — <b>0.5x</b>\n"
            "❔❔7️⃣ — <b>0.5x</b>\n\n"
            "🍀 <b>Good Luck!</b>"
        ),
        (
            "<b>🏛️ Spin Slots</b>\n\n"
            "<b>Winning combinations:</b>\n\n"
            "7️⃣7️⃣7️⃣ — <b>60x Jackpot!</b>\n\n"
            "🍀 <b>Good Luck!</b>"
        ),
    ]
    return pages[page % len(pages)]

    return pages[page % len(pages)]


def combos_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Next combinations", callback_data=f"{SLOTS_PREFIX}:next")],
        [
            InlineKeyboardButton("⬅️ Back",  callback_data=f"{SLOTS_PREFIX}:back"),   # (stub, stays on page)
            InlineKeyboardButton("🏛️ Start!", callback_data=f"{SLOTS_PREFIX}:start"),
        ],
    ])


def bet_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("-0.25",  callback_data=f"{SLOTS_PREFIX}:bet:-0.25"),
            InlineKeyboardButton("$0.25",  callback_data=f"{SLOTS_PREFIX}:bet:set:0.25"),
            InlineKeyboardButton("+0.25",  callback_data=f"{SLOTS_PREFIX}:bet:+0.25"),
        ],
        [
            InlineKeyboardButton("Min",    callback_data=f"{SLOTS_PREFIX}:bet:min"),
            InlineKeyboardButton("Double", callback_data=f"{SLOTS_PREFIX}:bet:double"),
            InlineKeyboardButton("Max",    callback_data=f"{SLOTS_PREFIX}:bet:max"),
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data=f"{SLOTS_PREFIX}:combos"),
            InlineKeyboardButton("🏛️ Spin", callback_data=f"{SLOTS_PREFIX}:spin"),
        ],
    ])


def end_keyboard(bet: float, payload: float) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Play Again", callback_data=f"{SLOTS_PREFIX}:replay:{bet:.2f}"),
            InlineKeyboardButton("✖ Double",      callback_data=f"{SLOTS_PREFIX}:double:{payload:.2f}"),
        ]
    ])


def mention(user) -> str:
    return f'<a href="tg://user?id={user.id}">{user.first_name}</a>'


# ─────────────────────────────────────────────────────────────────────────────
# Persistence helpers
# ─────────────────────────────────────────────────────────────────────────────

def save_session(user_id: int, bet: float, won: float, is_win: bool):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO game_sessions(user_id, mode, played_at, bet, won_amount, is_win) "
        "VALUES (?,?,?,?,?,?)",
        (user_id, "slots", datetime.utcnow().isoformat(), bet, won, int(is_win))
    )
    conn.commit()
    conn.close()
    update_stats(user_id, is_win)


# ─────────────────────────────────────────────────────────────────────────────
# Command & Callback Handlers
# ─────────────────────────────────────────────────────────────────────────────

async def slots_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry: show combinations page 1 with Start! button."""
    context.user_data["slots_page"] = 0
    await update.message.reply_text(
        combos_text(0),
        reply_markup=combos_keyboard(),
        parse_mode=ParseMode.HTML
    )


async def next_combos_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    page = context.user_data.get("slots_page", 0)
    context.user_data["slots_page"] = (page + 1) % 3
    await q.edit_message_text(
        combos_text(context.user_data["slots_page"]),
        reply_markup=combos_keyboard(),
        parse_mode=ParseMode.HTML
    )


async def combos_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Back from bet selector → show combinations again."""
    q = update.callback_query; await q.answer()
    page = context.user_data.get("slots_page", 0)
    await q.edit_message_text(
        combos_text(page),
        reply_markup=combos_keyboard(),
        parse_mode=ParseMode.HTML
    )


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start! → open bet selector (like screenshot 4)."""
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    bal = get_balance(uid)

    # default bet
    context.user_data["slots_bet"] = MIN_BET if bal >= MIN_BET else round(bal, 2)

    await q.edit_message_text(
        f"💰 Balance: ${bal:.2f}\n\nChoose the bet size:",
        reply_markup=bet_keyboard()
    )


async def bet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    bal = get_balance(uid)
    bet = context.user_data.get("slots_bet", MIN_BET)

    parts = q.data.split(":")
    # formats:
    # slots:bet:-0.25
    # slots:bet:+0.25
    # slots:bet:min
    # slots:bet:max
    # slots:bet:double
    # slots:bet:set:0.25
    if len(parts) >= 3:
        action = parts[2]
        if action in ("-0.25", "+0.25"):
            try:
                bet = bet + float(action)
            except Exception:
                pass
        elif action == "min":
            bet = MIN_BET
        elif action == "max":
            bet = bal
        elif action == "double":
            bet = bet * 2
        elif action == "set" and len(parts) == 4:
            try:
                bet = float(parts[3])
            except Exception:
                pass

    # clamp
    if bet < MIN_BET:
        bet = MIN_BET
    if bet > bal:
        bet = bal

    context.user_data["slots_bet"] = round(bet, 2)

    await q.edit_message_text(
        f"💰 Balance: ${bal:.2f}\n\nChoose the bet size:",
        reply_markup=bet_keyboard()
    )


def get_multiplier(v: int) -> float:
    return VALUE_TO_MULTIPLIER.get(v, 0.0)


async def spin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deduct bet → roll 🎰 → pay winnings → show result + replay."""
    q = update.callback_query; await q.answer()
    user = q.from_user
    uid = user.id

    bal = get_balance(uid)
    bet = float(context.user_data.get("slots_bet", MIN_BET))

    if bet < MIN_BET:
        return await q.edit_message_text("❗ Minimum bet is $0.25.")
    if bet > bal:
        return await q.edit_message_text(f"❗ Insufficient balance: ${bal:.2f}")

    # Deduct, record wager
    update_balance(uid, -bet)
    add_wager(uid, bet)

    # Roll Telegram slot
    dmsg = await q.message.reply_dice(emoji="🎰")
    value = dmsg.dice.value
    mult = get_multiplier(value)
    win_amt = round(bet * mult, 2) if mult > 0 else 0.0

    # Payout
    if win_amt > 0:
        update_balance(uid, win_amt)

    # Persist session
    save_session(uid, bet, win_amt, win_amt > 0)

    # Result message
    result_text = (
        f"{mention(user)}\n"
        f"🎰 <b>Result:</b> {value}\n"
        f"Bet: <b>${bet:.2f}</b>\n"
        f"{'🎉 You won' if win_amt > 0 else '😅 You lost'} <b>${win_amt:.2f}</b>"
    )

    await q.message.reply_text(
        result_text,
        parse_mode=ParseMode.HTML,
        reply_markup=end_keyboard(bet, win_amt if win_amt > 0 else bet)
    )


async def replay_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _, _, amt = q.data.split(":", 2)
    try:
        bet = max(MIN_BET, float(amt))
    except Exception:
        bet = MIN_BET
    context.user_data["slots_bet"] = bet
    bal = get_balance(q.from_user.id)
    await q.edit_message_text(
        f"💰 Balance: ${bal:.2f}\n\nChoose the bet size:",
        reply_markup=bet_keyboard()
    )


async def double_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _, _, amt = q.data.split(":", 2)
    try:
        payout = float(amt)
    except Exception:
        payout = MIN_BET
    context.user_data["slots_bet"] = max(MIN_BET, payout)
    bal = get_balance(q.from_user.id)
    await q.edit_message_text(
        f"💰 Balance: ${bal:.2f}\n\nChoose the bet size:",
        reply_markup=bet_keyboard()
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public registration helpers
# (use either explicit adds in bot.py or the helper below)
# ─────────────────────────────────────────────────────────────────────────────

def get_slots_handlers():
    """Convenience: add this loop in bot.py, or import handlers individually."""
    return [
        CommandHandler("slots", slots_command),

        CallbackQueryHandler(next_combos_handler, pattern=f"^{SLOTS_PREFIX}:next$"),
        CallbackQueryHandler(start_handler,       pattern=f"^{SLOTS_PREFIX}:start$"),
        CallbackQueryHandler(combos_handler,      pattern=f"^{SLOTS_PREFIX}:combos$"),

        CallbackQueryHandler(bet_handler,  pattern=f"^{SLOTS_PREFIX}:bet"),
        CallbackQueryHandler(spin_handler, pattern=f"^{SLOTS_PREFIX}:spin$"),

        CallbackQueryHandler(replay_handler, pattern=f"^{SLOTS_PREFIX}:replay"),
        CallbackQueryHandler(double_handler, pattern=f"^{SLOTS_PREFIX}:double"),
    ]
