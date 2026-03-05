import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from models import (
    get_connection,
    update_balance,
    log_transaction,
    update_stats,
)
from referral import track_referral_event

# ─── Configuration ────────────────────────────────────────────────────────────

BOT_USERNAME = os.getenv("BOT_USERNAME", "Dice_GambleBot")
ADMIN_ID     = int(os.getenv("ADMIN_ID", "7900370587"))

# ─── 30 Sticker IDs + Multipliers ─────────────────────────────────────────────
STICKERS = [
    ("CAACAgQAAxkBAAMFaGwKrS-rWLnfQSxAF6V3FFCR1EUAAvYZAAKzbllQ43UO0x1gJfE2BA", 4.0),
    ("CAACAgQAAxkBAAMMaGwQFGPbeIcivdOtFf127UhGiO0AArIWAALGpFlQErKhGWyL4gw2BA", 1.2),
    ("CAACAgQAAxkBAAMOaGwQON8j10t3aMngOhwRlfEOOwcAArMVAAJQxVlQNNzQEScpP-E2BA", 0.0),
    ("CAACAgQAAxkBAAMQaGwQaeyN-lshfLBDjk9oYz5YaMEAAs0ZAALsP1lQHIoXAr5xgkc2BA", 2.0),
    ("CAACAgQAAxkBAAMSaGwQhpXr-N7OrD-A9wWwiS3uRAUAAoEaAAK5LFhQMxhZrK18ef02BA", 0.0),
    ("CAACAgQAAxkBAAMUaGwQlFYva5ZKazTHtskH96Ndw6MAAukaAAKItFlQLU0lATGko742BA", 0.0),
    ("CAACAmQAAxkBAAMWaGwQs_YlMMc-7ntMnGUkW0zZ0QUAAn4ZAAIBnllQpzVcZPZe5pQ2BA", 1.7),
    ("CAACAmQAAxkBAAMYaGwQxy3iGeBpWTpwnAlKosnPd8IAAksVAAILtWFQDcyLsunOkfo2BA", 0.0),
    ("CAACAmQAAxkBAAMaaGwQ0yFxVxCnbz_g_FDsZRVhi9AAAoEZAAJGEmBQJKdR2owLR582BA", 2.0),
    ("CAACAmQAAxkBAAMcaGwQ9zhfnMNFLk5qqX1UwmhD4nkAAi0dAAIvYFhQKGAHiuwOczY2BA", 0.0),
    ("CAACAmQAAxkBAAMeaGwRHeN7jel7dDPPNM_bd19UnI8AAhIdAAIOEGFQE8A4ySE5yFg2BA", 1.7),
    ("CAACAmQAAxkBAAMgaGwRMNT8Rylq1T-w_ROBwjc1uX0AAncWAAJDWmBQjn3UKYEousI2BA", 0.0),
    ("CAACAmQAAxkBAAMiaGwRRKgxF6WnY1J98z1SDih_BeQAAm0XAAIMF1lQWtqRuC5d2Cc2BA", 1.2),
    ("CAACAmQAAxkBAAMkaGwRYw6qkrqBIImZNEINYTYMiMYAAh8XAALK1FhQwoawwWKDFxQ2BA", 0.0),
    ("CAACAmQAAxkBAAMmaGwRevg8fSwcJkjKnKvQFMAaO4oAAkwYAALQYFhQzMRHGnbxnyU2BA", 2.0),
    ("CAACAmQAAxkBAAMoaGwRjn_1JSCnRW7yuc3DmGC8G0gAAroXAAJoOllQj4_Mdubc3xg2BA", 0.0),
    ("CAACAmQAAxkBAAMqaGwRoxdkF8g5xGWS8KhlLhc-t-EAAp0WAAJEMWBQOlTJMjFkPBs2BA", 1.2),
    ("CAACAmQAAxkBAAMsaGwRxCeJdtzA-cdFGN9rZZppfBgAApoWAAKukGFQjqdYQUmOQNc2BA", 0.0),
    ("CAACAmQAAxkBAAMuaGwR50xdZ2Q4irQiqDFZ-EGJPfgAAoIWAAIKyVlQs9T24-YLPsk2BA", 1.2),
    ("CAACAmQAAxkBAAMwaGwR-9nbVNNvfCb8okoy0N61bUsAApQWAALlSlhQmevE2zTYdWI2BA", 0.0),
    ("CAACAmQAAxkBAAMyaGwSHCakoJUPAaIj47dT5OceFTQAAkcYAAJD31lQg3vzYnuOing2BA", 3.0),
    ("CAACAmQAAxkBAAM0aGwSKcyWeaR9wxPc5vMVVK02SaYAAgMUAAJt2VhQ3-Fup9rrjTE2BA", 0.0),
    ("CAACAmQAAxkBAAM2aGwSOnJ-zJpC3WROhrJ7Fta1N6cAAiwdAAKu31lQnBjRwvI4x-M2BA", 0.0),
    ("CAACAmQAAxkBAAM4aGwSU7lkMxmaj4kluh6_OfUy1ZsAAtYXAAJPaVlQgnMvbjkSs_82BA", 1.2),
    ("CAACAmQAAxkBAAM6aGwSbLw72E6ZP8G2lWcmhlmJnTwAArYZAALSsVlQn-agVOXTWJw2BA", 2.0),
    ("CAACAmQAAxkBAAM8aGwSe69f8YwLkGODCeVsm62ahaIAAuFfAAKdfllQd1gd-tUTdBs2BA", 0.0),
    ("CAACAmQAAxkBAAM-aGwSk9o3B9xmiE8mOfcLsBcoAAEEAAJlFwAC6R1YUMfY5TOho570NgQ", 0.0),
    ("CAACAmQAAxkBAANAaGwSoRdjeem1tIDdcuGN1iw5NCkAAggYAAJeYVhQhWRX0kks6sc2BA", 1.2),
    ("CAACAmQAAxkBAANCaGwStvIfBa_lp6UmXTgN4_ifV0IAAogZAAIhlVlQj-uVXzV2-tU2BA", 2.0),
    ("CAACAmQAAxkBAANEaGwSwGMi2iG613GV0Er2VOY-OdIAAuwYAAKinFhQfkISLCDNNfg2BA", 0.0),
]

# ─── Keyboards ─────────────────────────────────────────────────────────────────

def build_intro_kb():
    # ✅ Play & ◀️ Back on one row
    return InlineKeyboardMarkup([[  
        InlineKeyboardButton("✅ Play", callback_data="wheel_play"),
        InlineKeyboardButton("◀️ Back", callback_data="wheel_back"),
    ]])

def build_bet_kb(bet: float, bal: float, result_text: str = None):
    header = (
        f"🎡 *Wheel*\n\n"
        f"Bet: ${bet:.2f}\n"
        f"Balance: ${bal:.2f}"
    )
    if result_text:
        header += f"\n\n{result_text}"
    kb = [
        # ✅ Start Game
        [InlineKeyboardButton("✅ Start Game", callback_data="wheel_start")],
        # ½ Bet & 2× Bet
        [
            InlineKeyboardButton("½ Bet",   callback_data="wheel_half"),
            InlineKeyboardButton("2× Bet", callback_data="wheel_double"),
        ],
        # ◀️ Back & 🔍 Verify
        [
            InlineKeyboardButton("◀️ Back",   callback_data="wheel_back"),
            InlineKeyboardButton("🔍 Verify", callback_data="wheel_verify"),
        ],
    ]
    return header, InlineKeyboardMarkup(kb)

# ─── /wheel entrypoint ────────────────────────────────────────────────────────

async def wheel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    uid  = update.effective_user.id
    bal  = _get_balance(uid)

    # parse optional bet
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

    context.user_data.clear()
    context.user_data["wheel_bet"] = round(bet, 2)

    if bet > 0:
        header, kb = build_bet_kb(bet, bal)
        await update.message.reply_text(header, parse_mode="Markdown", reply_markup=kb)
    else:
        # Intro card (no bet)
        await update.message.reply_text(
            "🎡 *Wheel of Fortune*\n\n"
            "Classic wheel of fortune – spin and collect multipliers for your bet.\n\n"
            "To quickly start the game, type `/wheel <bet>`\n\n"
            "Examples:\n"
            "`/wheel 10` – bet $10\n"
            "`/wheel half` – bet half your balance\n"
            "`/wheel all` – go all-in",
            parse_mode="Markdown",
            reply_markup=build_intro_kb()
        )

# ─── ▶️ Play ──────────────────────────────────────────────────────────────────

async def wheel_play_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    uid = q.from_user.id
    bal = _get_balance(uid)
    bet = context.user_data.get("wheel_bet", 0.0) or min(1.0, bal)
    context.user_data["wheel_bet"] = round(bet, 2)

    header, kb = build_bet_kb(bet, bal)
    await q.edit_message_text(header, parse_mode="Markdown", reply_markup=kb)

# ─── ½ Bet ────────────────────────────────────────────────────────────────────

async def wheel_half_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer("½ Bet")
    uid = q.from_user.id; bal = _get_balance(uid)
    bet = bal / 2
    context.user_data["wheel_bet"] = round(bet, 2)

    header, kb = build_bet_kb(bet, bal)
    await q.edit_message_text(header, parse_mode="Markdown", reply_markup=kb)

# ─── 2× Bet ───────────────────────────────────────────────────────────────────

async def wheel_double_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer("2× Bet")
    uid = q.from_user.id; bal = _get_balance(uid)
    prev = context.user_data.get("wheel_bet", 0.0)
    bet  = min(bal, prev * 2)
    context.user_data["wheel_bet"] = round(bet, 2)

    header, kb = build_bet_kb(bet, bal)
    await q.edit_message_text(header, parse_mode="Markdown", reply_markup=kb)

# ─── ◀️ Back to intro ─────────────────────────────────────────────────────────

async def wheel_back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await wheel_command(q, context)

# ─── ▶️ Spin ─────────────────────────────────────────────────────────────────

async def wheel_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    uid = q.from_user.id
    bet = context.user_data.get("wheel_bet", 0.0)
    bal = _get_balance(uid)
    if bet <= 0 or bal < bet:
        return await q.answer("Invalid bet or insufficient balance", show_alert=True)

    # Deduct + referral
    update_balance(uid, -bet)
    log_transaction(uid, "wheel_bet", -bet, "spin")
    track_referral_event(uid, bet * 0.10)

    # Outcome
    sticker_id, mult = random.choice(STICKERS)
    won              = mult > 0
    payout           = round(bet * mult, 2) if won else 0.0

    if won:
        update_balance(uid, payout)
        log_transaction(uid, "wheel_win", payout, f"×{mult:.2f}")
        update_stats(uid, True)
        result_text = f"🎉 You won ${payout:.2f} (×{mult:.2f})!"
        is_win = 1
    else:
        update_stats(uid, False)
        result_text = "😢 You lost."
        is_win = 0

    _record_wheel_match(uid, bet, payout, is_win)

    # delete old menu, send sticker + result card
    await q.delete_message()
    await context.bot.send_sticker(chat_id=q.message.chat_id, sticker=sticker_id)

    # now show the final result card in the exact layout
    new_bal = _get_balance(uid)
    header, kb = build_bet_kb(bet, new_bal, result_text)
    await context.bot.send_message(
        chat_id=q.message.chat_id,
        text=header,
        parse_mode="Markdown",
        reply_markup=kb
    )

# ─── 🔍 Verify (placeholder) ───────────────────────────────────────────────────

async def wheel_verify_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer("Verification not implemented", show_alert=True)

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_balance(user_id: int) -> float:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0.0

def _record_wheel_match(user_id: int, bet: float, payout: float, is_win: int):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO game_sessions(user_id, mode, played_at, bet, won_amount, is_win) "
        "VALUES (?, 'wheel', datetime('now'), ?, ?, ?)",
        (user_id, bet, payout, is_win)
    )
    conn.commit()
    conn.close()
