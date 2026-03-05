from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import pytz
import sqlite3
import random

BONUS_WINDOW_HOURS = 12
BONUS_DAY = 4  # Friday
BONUS_TIME_IST = 21  # 9 PM IST
BONUS_PERCENTAGE = 0.003
BOOST_PERCENTAGE = 0.20

# ========== Time Utilities ==========
def is_bonus_time():
    now = datetime.now(pytz.timezone("Asia/Kolkata"))
    if now.weekday() != BONUS_DAY:
        return False
    start_time = now.replace(hour=BONUS_TIME_IST, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=BONUS_WINDOW_HOURS)
    return start_time <= now <= end_time

def time_until_bonus():
    now = datetime.now(pytz.timezone("Asia/Kolkata"))
    bonus_day = now + timedelta((BONUS_DAY - now.weekday()) % 7)
    next_bonus_time = bonus_day.replace(hour=BONUS_TIME_IST, minute=0, second=0, microsecond=0)
    if now > next_bonus_time:
        next_bonus_time += timedelta(days=7)
    return next_bonus_time - now

# ========== Bonus Calculation ==========
def calculate_bonus(user_id, has_boost=False):
    conn = sqlite3.connect("dicegame.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(amount) FROM wagers 
        WHERE user_id = ? AND timestamp >= datetime('now', '-7 days')
    """, (user_id,))
    total_wager = cursor.fetchone()[0] or 0
    conn.close()

    base_bonus = total_wager * BONUS_PERCENTAGE
    if has_boost:
        base_bonus *= (1 + BOOST_PERCENTAGE)
    return round(base_bonus, 2), round(total_wager, 2)

# ========== /bonus command ==========
async def bonus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await bonus_menu(update, context)

# ========== Bonus Menu ==========
def _bonus_text():
    return (
        "🎁 <b>Bonus</b>\n\n"
        "In this section you can find bonuses that you can get by playing games!\n\n"
        "💎 <b>Weekly Bonus</b>\n"
        "Play different games during the week and claim your bonus every Friday. Just don't slip up or the bonus will burn out!\n\n"
        "💎 <b>Level Up Bonus</b>\n"
        "Play games, level up and earn money!"
    )

def _bonus_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎁 Weekly Bonus", callback_data="bonus_weekly"),
            InlineKeyboardButton("🎁 Level Up Bonus", callback_data="bonus_levelup")
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]
    ])

async def bonus_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = _bonus_text()
    keyboard = _bonus_keyboard()

    query = update.callback_query
    if query:
        await query.answer()
        try:
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            # fallback if message can't be edited
            await query.message.reply_text(text=text, parse_mode="HTML", reply_markup=keyboard)
    elif update.message:
        await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=keyboard)


# ========== Weekly Bonus UI ==========
async def weekly_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_id = user.id
    has_boost = "bot" in (user.username or "").lower()
    bonus, wager = calculate_bonus(user_id, has_boost)

    can_claim = is_bonus_time()
    remaining = time_until_bonus()
    hours, rem = divmod(remaining.seconds, 3600)

    level = "Iron (Base Level)"
    next_level = "Bronze I"
    required_wager = "$100"

    text = (
        "🎁 <b>Weekly Bonus</b>\n\n"
        "Here you can get a percentage of the fees from your games! You can get a bonus for the past week games every Friday. "
        "If you don't do it in time – the bonuses will be burned!\n\n"
        "❓ <b>Rules</b>\n"
        "You have the choice of taking your bonus or trying to double it.\n"
        "In the second case we will send a dice and depending on its value you will get a different bonus value (multiplier):\n"
        "<b>Dice values:</b>\n"
        "1 - 0x\n2 - 0.5x\n3 - 1x\n4 - 1x\n5 - 1.5x\n6 - 2x\n\n"
        f"Your level: <b>{level}</b>\n"
        f"Boost: {'✅ Active' if has_boost else '❌ Inactive'}\n\n"
        f"Next level: 🛡 <b>{next_level}</b>\n"
        f"Wager <b>{required_wager}</b> more to upgrade your level!\n\n"
    )

    if can_claim:
        text += "✅ You can claim your bonus <b>now</b>!\n"
    else:
        text += f"⏳ You will be able to claim bonus in <b>{remaining.days}d {hours}h</b>\n"

    text += f"🎁 <b>Bonus</b>: <b>${bonus}</b>"

    keyboard = [
        [
            InlineKeyboardButton("🎁 Claim Bonus", callback_data="claim_bonus"),
            InlineKeyboardButton("🎲 Try To Double", callback_data="try_double")
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="bonus_menu")]
    ]

    await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# ========== Claim Bonus ==========
async def claim_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    has_boost = "bot" in (query.from_user.username or "").lower()

    if not is_bonus_time():
        await query.answer("⏳ Bonus claim period is over or not started yet!", show_alert=True)
        return

    bonus, _ = calculate_bonus(user_id, has_boost)
    if bonus <= 0:
        await query.answer("🚫 No bonus to claim!", show_alert=True)
        return

    conn = sqlite3.connect("dicegame.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bonus, user_id))
    cursor.execute("INSERT INTO transactions (user_id, type, amount, details, timestamp) VALUES (?, ?, ?, ?, ?)",
                   (user_id, "bonus", bonus, "Weekly Bonus Claimed", datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

    await query.edit_message_text(f"🎉 You successfully claimed your weekly bonus of <b>${bonus}</b>!", parse_mode="HTML")

# ========== Try To Double ==========
async def try_to_double(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    has_boost = "bot" in (query.from_user.username or "").lower()

    if not is_bonus_time():
        await query.answer("⏳ Bonus claim period is over or not started yet!", show_alert=True)
        return

    base_bonus, _ = calculate_bonus(user_id, has_boost)
    if base_bonus <= 0:
        await query.answer("🚫 No bonus to double!", show_alert=True)
        return

    roll = random.randint(1, 6)
    multiplier = {1: 0, 2: 0.5, 3: 1, 4: 1, 5: 1.5, 6: 2}[roll]
    final_bonus = round(base_bonus * multiplier, 2)

    if final_bonus > 0:
        conn = sqlite3.connect("dicegame.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (final_bonus, user_id))
        cursor.execute("INSERT INTO transactions (user_id, type, amount, details, timestamp) VALUES (?, ?, ?, ?, ?)",
                       (user_id, "bonus", final_bonus, f"Try To Double (Rolled {roll})", datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()

    await query.edit_message_text(
        f"🎲 You rolled a <b>{roll}</b>!\n"
        f"{'✅' if final_bonus > 0 else '❌'} Bonus received: <b>${final_bonus}</b>",
        parse_mode="HTML"
    )

# ========== Export for import ==========
__all__ = [
    "bonus_command",
    "bonus_menu",
    "weekly_bonus",
    "claim_bonus",
    "try_to_double"
]
