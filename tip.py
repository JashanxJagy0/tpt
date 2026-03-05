from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from models import get_balance, update_balance
from datetime import datetime
import sqlite3

TIP_LOG_CHANNEL = ""  # <-- Replace with your tip log channel ID or @channel_username

# === In-memory store for tip confirmation ===
pending_tips = {}

# ========== /tip Command ==========
async def tip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    if not args:
        await update.message.reply_text("Usage: /tip <amount> @username OR reply to a user with /tip <amount>")
        return

    try:
        amount = float(args[0])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Invalid tip amount.")
        return

    # Get recipient
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
    elif len(args) >= 2 and args[1].startswith("@"):
        for member in await update.effective_chat.get_administrators():
            if member.user.username and member.user.username.lower() == args[1][1:].lower():
                target_user = member.user
                break
        else:
            await update.message.reply_text("❌ Could not find the mentioned user.")
            return
    else:
        await update.message.reply_text("Please reply to someone or mention their @username.")
        return

    if target_user.id == user.id:
        await update.message.reply_text("😅 You cannot tip yourself.")
        return

    sender_balance = get_balance(user.id)
    if sender_balance < amount:
        await update.message.reply_text("🚫 Insufficient balance.")
        return

    pending_tips[user.id] = {
        "to_id": target_user.id,
        "to_name": f"@{target_user.username or target_user.first_name}",
        "amount": amount
    }

    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="tip_confirm"),
            InlineKeyboardButton("❌ No", callback_data="tip_cancel")
        ]
    ]
    await update.message.reply_text(
        f"Are you sure you want to tip {pending_tips[user.id]['to_name']} ${amount:.2f}?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ========== Tip Confirmation ==========
async def tip_confirmation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    tip_data = pending_tips.get(user_id)
    if not tip_data:
        await query.edit_message_text("⚠️ Tip session expired or invalid.")
        return

    if query.data == "tip_cancel":
        pending_tips.pop(user_id)
        await query.edit_message_text("❌ Tip cancelled.")
        return

    from_id = user_id
    to_id = tip_data["to_id"]
    amount = tip_data["amount"]

    update_balance(from_id, -amount)
    update_balance(to_id, amount)

    log_transaction(from_id, "tip_sent", -amount, f"To {tip_data['to_name']}")
    log_transaction(to_id, "tip_received", amount, f"From @{query.from_user.username or query.from_user.first_name}")

    await query.edit_message_text(f"✅ You tipped {tip_data['to_name']} ${amount:.2f} successfully!")

    
    if TIP_LOG_CHANNEL:
        await context.bot.send_message(
            chat_id=TIP_LOG_CHANNEL,
            text=f"💸 @{query.from_user.username or query.from_user.first_name} tipped {tip_data['to_name']} ${amount:.2f}!"
        )

    pending_tips.pop(user_id)

# ========== Logging ==========
def log_transaction(user_id, t_type, amount, details):
    conn = sqlite3.connect("dicegame.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (user_id, type, amount, details, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, t_type, amount, details, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

# ========== /tiplog ==========
LOGS_PER_PAGE = 10

def fetch_tip_logs(user_id, offset):
    conn = sqlite3.connect("dicegame.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM transactions WHERE user_id = ? AND type LIKE 'tip_%'", (user_id,))
    total = cursor.fetchone()[0]
    cursor.execute("""
        SELECT type, amount, details, timestamp 
        FROM transactions 
        WHERE user_id = ? AND type LIKE 'tip_%'
        ORDER BY timestamp DESC 
        LIMIT ? OFFSET ?
    """, (user_id, LOGS_PER_PAGE, offset))
    entries = cursor.fetchall()
    conn.close()
    return total, entries

def format_tip_log(entries, page, total_pages, username):
    lines = [f"📒 <b>Tip Log for {username}</b> (Page {page}/{total_pages})\n"]
    for t_type, amount, detail, ts in entries:
        sign = "+" if t_type == "tip_received" else "-"
        dt = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
        lines.append(f"🕘 {dt}\n{sign}${abs(amount):.2f} {detail}\n")
    return "\n".join(lines)

async def tiplog_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1 or not context.args[0].startswith("@"):
        await update.message.reply_text("Usage: /tiplog @username")
        return

    username = context.args[0][1:].lower()
    chat = update.effective_chat
    members = await chat.get_administrators()

    target_user = next((m.user for m in members if m.user.username and m.user.username.lower() == username), None)
    if not target_user:
        await update.message.reply_text("❌ User not found in this chat.")
        return

    user_id = target_user.id
    total, logs = fetch_tip_logs(user_id, offset=0)
    total_pages = max(1, (total + LOGS_PER_PAGE - 1) // LOGS_PER_PAGE)
    text = format_tip_log(logs, 1, total_pages, f"@{username}")

    buttons = []
    if total_pages > 1:
        buttons = [[
            InlineKeyboardButton("➡️ Next Page", callback_data=f"tiplog:{user_id}:2:@{username}")
        ]]

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
    )

async def tiplog_page_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, user_id, page, username = query.data.split(":")
        user_id = int(user_id)
        page = int(page)
    except Exception:
        await query.edit_message_text("❌ Invalid callback data.")
        return

    offset = (page - 1) * LOGS_PER_PAGE
    total, logs = fetch_tip_logs(user_id, offset)
    total_pages = max(1, (total + LOGS_PER_PAGE - 1) // LOGS_PER_PAGE)

    if page < 1 or page > total_pages:
        await query.edit_message_text("❌ Page out of range.")
        return

    text = format_tip_log(logs, page, total_pages, username)

    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("⬅️ Prev Page", callback_data=f"tiplog:{user_id}:{page - 1}:{username}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton("➡️ Next Page", callback_data=f"tiplog:{user_id}:{page + 1}:{username}"))

    await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([buttons]) if buttons else None
    )
