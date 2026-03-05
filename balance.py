import os
import json
import requests
import sqlite3
from dotenv import load_dotenv

load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# Load admin IDs from environment variable (JSON list of IDs)
ADMIN_IDS = json.loads(os.getenv("ADMIN_IDS", "[8259998062]"))

# Bot user ID for storing bot’s balance in DB
BOT_USER_ID = 0  # Change if needed

async def is_admin(update: Update) -> bool:
    return update.effective_user.id in ADMIN_IDS
def get_target_user_from_reply(update: Update):
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    return None

def get_balance(user_id: int) -> float:
    conn = sqlite3.connect("dicegame.db")
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0.0

def update_balance(user_id: int, amount: float):
    conn = sqlite3.connect("dicegame.db")
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row:
        new_balance = row[0] + amount
        c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
    else:
        c.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, amount))
    conn.commit()
    conn.close()

def add_wager(user_id: int, amount: float):
    conn = sqlite3.connect("dicegame.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO wagers (user_id, amount, timestamp) VALUES (?, ?, datetime('now'))",
        (user_id, amount)
    )
    conn.commit()
    conn.close()

async def extract_user_by_username(update: Update, username: str):
    members = list(await update.effective_chat.get_administrators())
    for member in members:
        if member.user.username and member.user.username.lower() == username.lower().lstrip("@"):
            return member.user
    await update.message.reply_text("❌ Username not found in this chat.")
    return None

# --- Command: /setbalance (Admin only) ---
async def set_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("⛔ You are not an admin.")
        return

    # 1️⃣ Try reply-based user
    user = get_target_user_from_reply(update)

    # 2️⃣ Fallback to username
    if not user:
        if len(context.args) < 2:
            await update.message.reply_text(
                "Usage:\n"
                "• Reply to a user: /setbalance amount\n"
                "• Or: /setbalance @username amount"
            )
            return
        user = await extract_user_by_username(update, context.args[0])
        if not user:
            return
        amount_arg = context.args[1]
    else:
        if len(context.args) < 1:
            await update.message.reply_text("Usage: reply → /setbalance amount")
            return
        amount_arg = context.args[0]

    try:
        amount = float(amount_arg)
    except ValueError:
        await update.message.reply_text("❌ Invalid amount.")
        return

    update_balance(user.id, -get_balance(user.id))
    update_balance(user.id, amount)

    await update.message.reply_text(
        f"✅ Set balance of {user.first_name} to ${amount:,.2f}"
    )

# --- Command: /addbalance (Admin only) ---
async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("⛔ You are not an admin.")
        return

    user = get_target_user_from_reply(update)

    if not user:
        if len(context.args) < 2:
            await update.message.reply_text(
                "Usage:\n"
                "• Reply → /addbalance amount\n"
                "• Or: /addbalance @username amount"
            )
            return
        user = await extract_user_by_username(update, context.args[0])
        if not user:
            return
        amount_arg = context.args[1]
    else:
        if len(context.args) < 1:
            await update.message.reply_text("Usage: reply → /addbalance amount")
            return
        amount_arg = context.args[0]

    try:
        amount = float(amount_arg)
    except ValueError:
        await update.message.reply_text("❌ Invalid amount.")
        return

    update_balance(user.id, amount)
    await update.message.reply_text(
        f"✅ Added ${amount:,.2f} to {user.first_name}"
    )

# --- Command: /drainbalance (Admin only) ---
async def drain_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("⛔ You are not an admin.")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /drainbalance @username")
        return

    user = await extract_user_by_username(update, context.args[0])
    if not user:
        return

    update_balance(user.id, -get_balance(user.id))
    await update.message.reply_text(f"🧹 Drained balance of @{user.username}")

# --- Command: /balance ---
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bal = get_balance(user_id)
    rate = get_ltc_usd_rate()
    ltc_equiv = bal * rate

    text = f"Your balance: <b>${bal:,.2f}</b> ({ltc_equiv:.4f} LTC)"
    keyboard = [[
        InlineKeyboardButton("💳 Deposit", callback_data="deposit"),
        InlineKeyboardButton("🪙 Withdraw", callback_data="withdraw")
    ]]
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- LTC/USD rate from CoinGecko ---
def get_ltc_usd_rate():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=usd",
            timeout=2
        )
        return 1 / r.json()["litecoin"]["usd"]
    except:
        return 0.00004

# --- Command: /housebal, /hb, /housebalance ---
async def house_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bal = get_balance(BOT_USER_ID)
    await update.message.reply_text(f"💰 Available balance of the bot: ${bal:,.2f}")

# --- Command: /setbotbalance (Admin only) ---
async def set_bot_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("⛔ You are not authorized to use this command.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /setbotbalance amount")
        return

    try:
        amount = float(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid amount. Please enter a valid number.")
        return

    update_balance(BOT_USER_ID, -get_balance(BOT_USER_ID))
    update_balance(BOT_USER_ID, amount)
    await update.message.reply_text(f"✅ Bot balance set to ${amount:,.2f}")

__all__ = [
    "balance",
    "set_balance",
    "add_balance",
    "drain_balance",
    "house_balance_command",
    "set_bot_balance_command"
]
