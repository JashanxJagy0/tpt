# referral.py

import os
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
DB_PATH      = os.getenv("DB_PATH",      "dicegame.db")
BOT_USERNAME = os.getenv("BOT_USERNAME", "Dice_GambleBot")   # your bot’s @username
ADMIN_ID     = int(os.getenv("ADMIN_ID", "7900370587"))      # your Telegram ID

# ─────────────────────────────────────────────────────────────────────────────
# Initialize schema if needed
# ─────────────────────────────────────────────────────────────────────────────
def initialize_referral_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    # each user’s code
    cur.execute("""
    CREATE TABLE IF NOT EXISTS referral_codes (
        user_id     INTEGER PRIMARY KEY,
        code        TEXT    UNIQUE NOT NULL,
        created_at  TEXT    NOT NULL
    );
    """)
    # each usage
    cur.execute("""
    CREATE TABLE IF NOT EXISTS referral_usages (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        code              TEXT    NOT NULL,
        referred_user_id  INTEGER NOT NULL,
        used_at           TEXT    NOT NULL
    );
    """)
    conn.commit()
    conn.close()

initialize_referral_db()

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _get_user_code(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("SELECT code, created_at FROM referral_codes WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row  # (code, created_at) or None

def _count_code_uses(code: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM referral_usages WHERE code = ?", (code,))
    cnt = cur.fetchone()[0]
    conn.close()
    return cnt

def _insert_usage(code: str, user_id: int):
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO referral_usages(code, referred_user_id, used_at) VALUES (?, ?, ?)",
        (code, user_id, now)
    )
    conn.commit()
    conn.close()

def _delete_code(code: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("DELETE FROM referral_codes WHERE code = ?", (code,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def _top_referrers(limit: int = 5):
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("""
        SELECT rc.code, COUNT(ru.id) AS uses
          FROM referral_codes rc
          LEFT JOIN referral_usages ru ON ru.code = rc.code
         GROUP BY rc.code
         ORDER BY uses DESC
         LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows  # list of (code, uses)

# ─────────────────────────────────────────────────────────────────────────────
# /createreferralcode — admin only
# Usage: /createreferralcode <user_id> <code>
# ─────────────────────────────────────────────────────────────────────────────
async def createreferralcode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ You’re not allowed to run this.")
    if len(context.args) != 2:
        return await update.message.reply_text("Usage: /createreferralcode <user_id> <code>")

    try:
        target_id = int(context.args[0])
    except ValueError:
        return await update.message.reply_text("❌ Invalid user_id. Must be an integer.")

    code = context.args[1].strip().upper()
    now  = datetime.utcnow().isoformat()

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO referral_codes(user_id, code, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
              code        = excluded.code,
              created_at  = excluded.created_at
        """, (target_id, code, now))
        conn.commit()
    except sqlite3.IntegrityError:
        await update.message.reply_text("❗️ That code is already taken.")
        conn.close()
        return
    conn.close()

    await update.message.reply_text(
        f"✅ Assigned referral code <b>{code}</b> to user <code>{target_id}</code>.",
        parse_mode="HTML"
    )

# ─────────────────────────────────────────────────────────────────────────────
# /referral or /ref — show code & stats
# ─────────────────────────────────────────────────────────────────────────────
async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    row     = _get_user_code(user_id)
    if not row:
        # no code yet
        return await update.message.reply_text(
            "🤝 <b>Referral system</b>\n\n"
            "Invite your friends to join the bot using referral link and get a bunch of bonuses!\n\n"
            "❔ To use a referral code, send <code>/code &lt;referral_code&gt;</code>\n"
            "🔑 To get your own referral link, ask an admin for <code>/createreferralcode</code>.",
            parse_mode="HTML"
        )

    code, created_at = row
    uses = _count_code_uses(code)
    link = f"https://t.me/{BOT_USERNAME}?start=r-{code}"

    await update.message.reply_text(
        "🤝 <b>Referral system</b>\n\n"
        "Invite your friends to join the bot using referral link and get a bunch of bonuses!\n\n"
        "<b>Benefits:</b>\n"
        "• You will receive 10% of the playing fees of your referred players\n\n"
        f"💰 <b>Referral earnings:</b> ${uses * 0:.2f}\n"
        f"👥 <b>Invited users:</b> {uses}\n\n"
        f"Your referral code: <code>{code}</code>\n"
        f"Your referral link: {link}",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

# ─────────────────────────────────────────────────────────────────────────────
# /code <referral_code> — apply someone’s code
# ─────────────────────────────────────────────────────────────────────────────
async def usecode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /code <referral_code>")

    code = context.args[0].strip().upper()
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    # verify
    cur.execute("SELECT user_id FROM referral_codes WHERE code = ?", (code,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return await update.message.reply_text("❌ Invalid referral code.")
    referrer_id = row[0]
    if referrer_id == user_id:
        conn.close()
        return await update.message.reply_text("❌ You can’t use your own code.")
    # already used?
    cur.execute(
        "SELECT 1 FROM referral_usages WHERE code = ? AND referred_user_id = ?",
        (code, user_id)
    )
    if cur.fetchone():
        conn.close()
        return await update.message.reply_text("ℹ️ You’ve already used a referral code.")
    conn.close()

    _insert_usage(code, user_id)
    await update.message.reply_text(
        f"✅ Code <code>{code}</code> applied! From now on, 10% of your house fees will go to its owner.",
        parse_mode="HTML"
    )

# ─────────────────────────────────────────────────────────────────────────────
# /delrefcode <code> — admin only revoke code
# ─────────────────────────────────────────────────────────────────────────────
async def delete_referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ You’re not allowed to run this.")
    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /delrefcode <referral_code>")

    code = context.args[0].strip().upper()
    if _delete_code(code):
        await update.message.reply_text(f"✅ Code <code>{code}</code> deleted.", parse_mode="HTML")
    else:
        await update.message.reply_text(f"❌ Code <code>{code}</code> not found.", parse_mode="HTML")

# ─────────────────────────────────────────────────────────────────────────────
# /referralstats — leaderboard of top referrers
# ─────────────────────────────────────────────────────────────────────────────
async def referralstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = _top_referrers(5)
    if not rows:
        return await update.message.reply_text("No referral activity yet.")
    lines = ["🏆 <b>Top Referrers</b>"]
    for idx, (code, uses) in enumerate(rows, start=1):
        lines.append(f"{idx}. <code>{code}</code> — {uses} use{'s' if uses != 1 else ''}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

# ─────────────────────────────────────────────────────────────────────────────
# Cross‐module helper to credit 10% of house fee
# Call right after you do: update_balance(user_id, -house_fee)
# ─────────────────────────────────────────────────────────────────────────────
def track_referral_event(referred_user_id: int, fee_amount: float):
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("""
        SELECT code
          FROM referral_usages
         WHERE referred_user_id = ?
         ORDER BY used_at DESC
         LIMIT 1
    """, (referred_user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return
    code = row[0]
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("SELECT user_id FROM referral_codes WHERE code = ?", (code,))
    owner = cur.fetchone()
    conn.close()
    if not owner:
        return
    referrer_id = owner[0]
    bonus       = round(fee_amount * 0.10, 2)
    from models import update_balance
    update_balance(referrer_id, bonus)
