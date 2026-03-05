# housebal.py
from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime
import sqlite3

DB_PATH = "dicegame.db"

# List of admin Telegram user IDs allowed to set balance
ALLOWED_ADMINS = {123456789, 987654321}  # <-- replace with your IDs

# ---- setup ----
def _init_tables():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Table to track house balance
    c.execute("""
    CREATE TABLE IF NOT EXISTS house_balance (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        balance REAL NOT NULL DEFAULT 0
    )
    """)
    c.execute("INSERT OR IGNORE INTO house_balance (id, balance) VALUES (1, 0)")

    conn.commit()
    conn.close()

_init_tables()

# ---- helpers ----
def _fmt_money(x: float) -> str:
    x = float(x)
    return f"${x:,.0f}" if x >= 1000 else (f"${int(x)}" if x.is_integer() else f"${x:,.2f}")

def get_house_balance() -> float:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT balance FROM house_balance WHERE id = 1")
    bal = c.fetchone()[0]
    conn.close()
    return float(bal)

def adjust_house_balance(delta: float, *, user_id=None, reason: str = "", game_ref: str = "") -> float:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("BEGIN IMMEDIATE")
        c.execute("UPDATE house_balance SET balance = balance + ? WHERE id = 1", (float(delta),))
        c.execute("SELECT balance FROM house_balance WHERE id = 1")
        new_bal = float(c.fetchone()[0])
        # Optional: log in transactions
        if user_id is not None:
            c.execute("""
                INSERT INTO transactions (user_id, type, amount, details, timestamp)
                VALUES (?, 'house_balance', ?, ?, ?)
            """, (
                user_id,
                float(delta),
                reason or "House balance adjust",
                datetime.utcnow().isoformat(timespec="seconds")
            ))
        conn.commit()
        return new_bal
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def set_house_balance(new_amount: float) -> float:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE house_balance SET balance = ? WHERE id = 1", (float(new_amount),))
    conn.commit()
    conn.close()
    return float(new_amount)

# ---- Telegram commands ----
async def housebal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current house balance (anyone can use)."""
    bal = get_house_balance()
    await update.message.reply_text(f"💰 Available balance of the bot: <b>{_fmt_money(bal)}</b>", parse_mode="HTML")

async def sethousebal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set the house balance (admin only)."""
    user_id = update.effective_user.id
    if user_id not in ALLOWED_ADMINS:
        await update.message.reply_text("")
        return

    if not context.args:
        await update.message.reply_text("Usage: /sethousebal <amount>")
        return

    try:
        amt = float(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount.")
        return

    set_house_balance(amt)
    await update.message.reply_text(f"✅ House balance set to <b>{_fmt_money(amt)}</b>", parse_mode="HTML")
