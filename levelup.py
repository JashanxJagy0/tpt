# levelup.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime
import sqlite3
import pytz

from levels import LEVELS_DATA, LEVEL_ORDER  # your levels.py

BONUS_DB = "bonus.db"
GAME_DB = "dicegame.db"  # where wagers live

IST = pytz.timezone("Asia/Kolkata")

# ---------- DB init ----------
def _init_bonus_db():
    conn = sqlite3.connect(BONUS_DB)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS level_progress (
        user_id INTEGER PRIMARY KEY,
        total_wager REAL NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS level_bonus_claims (
        user_id INTEGER NOT NULL,
        level_name TEXT NOT NULL,      -- e.g., "Bronze I"
        claimed_at TEXT NOT NULL,
        PRIMARY KEY (user_id, level_name)
    )
    """)
    # helpful index for rank queries
    c.execute("CREATE INDEX IF NOT EXISTS idx_progress_wager ON level_progress(total_wager)")
    conn.commit()
    conn.close()

_init_bonus_db()

# ---------- Helpers: wager sync & rank ----------
def _get_total_wager_from_game_db(user_id: int) -> float:
    """Sum all wagers for the user from dicegame.db (UTC timestamps)."""
    conn = sqlite3.connect(GAME_DB)
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(amount),0) FROM wagers WHERE user_id=?", (user_id,))
    total = c.fetchone()[0] or 0.0
    conn.close()
    return float(total)

def _upsert_progress(user_id: int, total_wager: float):
    now = datetime.utcnow().isoformat(timespec="seconds")
    conn = sqlite3.connect(BONUS_DB)
    c = conn.cursor()
    c.execute("""
    INSERT INTO level_progress (user_id, total_wager, updated_at)
    VALUES (?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET
        total_wager=excluded.total_wager,
        updated_at=excluded.updated_at
    """, (user_id, total_wager, now))
    conn.commit()
    conn.close()

def _get_rank(user_id: int) -> int:
    """Rank by total_wager DESC among users present in bonus.db."""
    conn = sqlite3.connect(BONUS_DB)
    c = conn.cursor()
    c.execute("SELECT total_wager FROM level_progress WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return 0
    mine = float(row[0])
    c.execute("SELECT COUNT(*) FROM level_progress WHERE total_wager > ?", (mine,))
    higher = c.fetchone()[0] or 0
    conn.close()
    return higher + 1

# ---------- Helpers: levels ----------
def _flatten_levels():
    """Return [(level_name, threshold_wager, bonus), ...] in progression order."""
    flat = []
    for tier in LEVEL_ORDER:
        for name, wager, bonus in LEVELS_DATA[tier]:
            flat.append((name, wager, bonus))
    return flat

ALL_LEVELS = _flatten_levels()
NAME_TO_INDEX = {name: i for i, (name, _, _) in enumerate(ALL_LEVELS)}

def _current_and_next_level(total_wager: float):
    """Find current level by highest threshold <= total_wager."""
    curr_idx = -1
    for i, (_, threshold, _) in enumerate(ALL_LEVELS):
        if total_wager >= threshold:
            curr_idx = i
        else:
            break

    current = ALL_LEVELS[curr_idx] if curr_idx >= 0 else ("Iron (Base Level)", 0, 0)
    next_level = ALL_LEVELS[curr_idx + 1] if curr_idx + 1 < len(ALL_LEVELS) else None
    return curr_idx, current, next_level

def _claimed_levels_set(user_id: int):
    conn = sqlite3.connect(BONUS_DB)
    c = conn.cursor()
    c.execute("SELECT level_name FROM level_bonus_claims WHERE user_id=?", (user_id,))
    names = {r[0] for r in c.fetchall()}
    conn.close()
    return names

def _record_level_claim(user_id: int, level_name: str):
    conn = sqlite3.connect(BONUS_DB)
    c = conn.cursor()
    c.execute("""INSERT OR IGNORE INTO level_bonus_claims (user_id, level_name, claimed_at)
                 VALUES (?, ?, ?)""", (user_id, level_name, datetime.utcnow().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()

# ---------- Text helpers ----------
def _fmt_money(x) -> str:
    x = float(x)
    if x >= 1000:
        return f"${x:,.0f}"
    if x.is_integer():
        return f"${int(x)}"
    return f"${x:,.2f}"

def _build_levelup_text(user_id: int, total_wager: float):
    rank = _get_rank(user_id)
    _, (curr_name, curr_thr, _), next_level = _current_and_next_level(total_wager)

    lines = []
    lines.append("🌲 <b>Level Up Bonus</b>\n")
    lines.append("Play games, level up and get even more bonuses!\n")
    lines.append(f"Your current level:\n🛡 <b>{curr_name}</b> - {_fmt_money(total_wager)} wagered\n")

    if next_level:
        next_name, next_thr, _ = next_level
        need = max(0.0, next_thr - total_wager)
        lines.append(f"Next Level:\n🛡 <b>{next_name}</b> - {_fmt_money(next_thr)} wagered\n")
        lines.append(f"You are ranked <b>#{rank}</b>.\n")
        lines.append(f"Wager <b>{_fmt_money(need)}</b> more to upgrade your level!\n")
    else:
        lines.append("You’re at the top tier. 🔥\n")
        lines.append(f"You are ranked <b>#{rank}</b>.\n")

    return "\n".join(lines).strip()

def _pending_claim_amount(user_id: int, total_wager: float):
    """
    If user crossed a level that is not claimed yet, return (level_name, bonus_amount).
    Else (None, 0).
    """
    idx, (curr_name, _, curr_bonus), _ = _current_and_next_level(total_wager)
    if idx < 0:
        return (None, 0.0)

    claimed = _claimed_levels_set(user_id)
    if curr_name not in claimed:
        return (curr_name, float(curr_bonus))
    return (None, 0.0)

# ---------- UI handlers ----------
async def levelup_bonus_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open the Level Up Bonus screen (with lock/unlock state)."""
    q = update.callback_query
    if q:
        await q.answer()
        user = q.from_user
    else:
        user = update.effective_user

    user_id = user.id

    # Sync user’s total wager from game DB into bonus DB
    total = _get_total_wager_from_game_db(user_id)
    _upsert_progress(user_id, total)

    # Primary text
    text = _build_levelup_text(user_id, total)

    # Determine claim state and annotate text with lock/unlock info
    pending_level, pending_amount = _pending_claim_amount(user_id, total)
    idx, (_, _, _curr_bonus), next_level = _current_and_next_level(total)

    if pending_level:
        text += f"\n\n✅ Bonus available for <b>{pending_level}</b>: <b>{_fmt_money(pending_amount)}</b>"
    else:
        if next_level:
            next_name, _, next_bonus = next_level
            text += f"\n\n🔒 Bonus locked for <b>{next_name}</b>: <b>{_fmt_money(next_bonus)}</b>"
        else:
            text += "\n\n🔒 No further bonuses — you’re at the top!"

    # Build button (unlocked = claim; locked = noop with lock)
    if pending_level:
        claim_btn = InlineKeyboardButton(
            f"Claim {_fmt_money(pending_amount)} Bonus",
            callback_data="level_claim"
        )
    else:
        shown_amt = next_level[2] if next_level else 0
        claim_btn = InlineKeyboardButton(
            f"Claim {_fmt_money(shown_amt)} Bonus 🔒",
            callback_data="noop_locked"
        )

    kb = [
        [claim_btn],
        [InlineKeyboardButton("Levels List", callback_data="levels_Bronze")],
        [InlineKeyboardButton("⬅️ Back", callback_data="bonus_menu")]
    ]
    markup = InlineKeyboardMarkup(kb)

    if q:
        try:
            await q.edit_message_text(text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            await q.message.reply_text(text, parse_mode="HTML", reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup)

async def level_claim_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pressing the Claim button when a level-up is unclaimed."""
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id

    # Re-check live (prevents race conditions)
    total = _get_total_wager_from_game_db(user_id)
    _upsert_progress(user_id, total)
    level_name, amount = _pending_claim_amount(user_id, total)
    if not level_name or amount <= 0:
        await q.answer("No level-up bonus available to claim.", show_alert=True)
        return

    # Credit user + record claim in main DB
    conn = sqlite3.connect(GAME_DB)
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    c.execute("""INSERT INTO transactions (user_id, type, amount, details, timestamp)
                 VALUES (?, 'level_bonus', ?, ?, ?)""",
              (user_id, amount, f"Level-Up Bonus ({level_name})", datetime.utcnow().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()

    _record_level_claim(user_id, level_name)

    await q.edit_message_text(
        f"🎉 You claimed <b>{_fmt_money(amount)}</b> for reaching <b>{level_name}</b>!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="bonus_levelup")]
        ])
    )

# ---------- Handler for locked button ----------
async def noop_locked_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows an alert when claim is locked."""
    await update.callback_query.answer("You haven’t unlocked this bonus yet!", show_alert=True)
