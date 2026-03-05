import sqlite3
import random
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes

# — Adjust to your actual DB path or env var if needed —
DB_PATH = "dicegame.db"

# — Admin ID for /startraffle & /endraffle —
ADMIN_ID = 7900370587  # ← change to your Telegram user ID

# ─── Schema Initialization ────────────────────────────────────────────────

def initialize_events_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # single row table to track current raffle
    c.execute("""
    CREATE TABLE IF NOT EXISTS raffle_state (
        is_active  INTEGER NOT NULL,
        prize      TEXT,
        started_at TEXT
    )
    """)
    # each ticket purchase
    c.execute("""
    CREATE TABLE IF NOT EXISTS raffle_entry (
        user_id    INTEGER,
        entered_at TEXT
    )
    """)
    # history of completed raffles
    c.execute("""
    CREATE TABLE IF NOT EXISTS raffle_history (
        winner_id  INTEGER,
        prize      TEXT,
        entries    INTEGER,
        ended_at   TEXT
    )
    """)
    conn.commit()
    conn.close()

# ─── /raffle (shows current or “no raffle”) ───────────────────────────────

async def raffle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT is_active, prize FROM raffle_state LIMIT 1")
    row = c.fetchone()
    conn.close()

    if not row or row[0] == 0:
        # no active raffle
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📜 Rules",    callback_data="raffle_rules")],
            [InlineKeyboardButton("📜 History",  callback_data="raffle_history")],
        ])
        return await update.message.reply_text(
            "🎟️ There is no raffle running right now.\n"
            "Check back later!",
            reply_markup=kb
        )

    # raffle is live
    prize = row[1]
    conn  = sqlite3.connect(DB_PATH)
    c     = conn.cursor()
    c.execute("SELECT COUNT(*) FROM raffle_entry")
    count = c.fetchone()[0]
    conn.close()

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎫 Buy Ticket", callback_data="buyraffle")],
        [InlineKeyboardButton("📜 Rules",      callback_data="raffle_rules")],
        [InlineKeyboardButton("📜 History",    callback_data="raffle_history")],
    ])
    await update.message.reply_text(
        f"🎉 A raffle is LIVE!\n\n"
        f"Prize: <b>{prize}</b>\n"
        f"Entries so far: <b>{count}</b>\n\n"
        "Tap 🎫 or use /buyraffle to get your ticket!",
        parse_mode="HTML",
        reply_markup=kb
    )

# ─── /buyraffle (user buys exactly one ticket) ────────────────────────────

async def buyraffle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    # ensure raffle is active
    c.execute("SELECT is_active FROM raffle_state LIMIT 1")
    row = c.fetchone()
    if not row or row[0] == 0:
        conn.close()
        return await update.message.reply_text("❌ There is no active raffle to enter.")

    # check if already entered
    c.execute(
        "SELECT 1 FROM raffle_entry WHERE user_id = ?",
        (user.id,)
    )
    if c.fetchone():
        conn.close()
        return await update.message.reply_text("ℹ️ You’ve already got a ticket for this raffle.")

    # insert ticket
    c.execute(
        "INSERT INTO raffle_entry (user_id, entered_at) VALUES (?, ?)",
        (user.id, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Ticket purchased! Good luck!")

# ─── /startraffle (admin starts a new raffle) ────────────────────────────

async def startraffle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ You’re not authorized to start raffles.")

    if not context.args:
        return await update.message.reply_text("Usage: /startraffle <prize description>")

    prize = " ".join(context.args).strip()

    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    # clear any old state
    c.execute("DELETE FROM raffle_state")
    c.execute("DELETE FROM raffle_entry")
    # create new state
    c.execute(
        "INSERT INTO raffle_state (is_active, prize, started_at) VALUES (1, ?, ?)",
        (prize, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(f"🎉 Raffle started for prize: <b>{prize}</b>", parse_mode="HTML")

# ─── /endraffle (admin ends, picks a winner) ─────────────────────────────

async def endraffle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ You’re not authorized to end raffles.")

    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT is_active, prize FROM raffle_state LIMIT 1")
    state = c.fetchone()
    if not state or state[0] == 0:
        conn.close()
        return await update.message.reply_text("❌ There’s no active raffle to end.")

    prize = state[1]
    # fetch entries
    c.execute("SELECT user_id FROM raffle_entry")
    entries = [r[0] for r in c.fetchall()]

    if not entries:
        # no tickets sold
        c.execute("DELETE FROM raffle_state")
        conn.commit()
        conn.close()
        return await update.message.reply_text("❌ No tickets were sold; raffle cancelled.")

    winner_id = random.choice(entries)
    # record to history
    c.execute(
        "INSERT INTO raffle_history (winner_id, prize, entries, ended_at) VALUES (?, ?, ?, ?)",
        (winner_id, prize, len(entries), datetime.utcnow().isoformat())
    )
    # clear state & entries
    c.execute("DELETE FROM raffle_state")
    c.execute("DELETE FROM raffle_entry")
    conn.commit()
    conn.close()

    # mention winner
    mention = f'<a href="tg://user?id={winner_id}">winner</a>'
    await update.message.reply_text(
        f"🎉 Raffle ended!\n\n"
        f"Prize: <b>{prize}</b>\n"
        f"Winner: {mention}\n"
        f"Tickets sold: {len(entries)}",
        parse_mode="HTML"
    )

# ─── 📜 Inline: Rules, History, Back ─────────────────────────────────────

async def raffle_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "📜 <b>Raffle Rules</b>\n\n"
        "1. Admin starts a raffle with /startraffle.<br>"
        "2. Users buy one ticket each via /buyraffle.<br>"
        "3. When admin ends the raffle (/endraffle), a random ticket wins.<br>"
        "4. Each user may only buy one ticket per raffle.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="raffle_back")]
        ])
    )

async def raffle_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    # Link out to your update channel or show recent history from DB
    await q.edit_message_text(
        "📜 Raffle History is available in @abir_channel",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="raffle_back")]
        ])
    )

async def raffle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    # simply delete the inline menu so the user can call /raffle again
    await q.message.delete()
