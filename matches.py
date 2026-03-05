# matches.py

import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime

DB_PATH = "dicegame.db"
PAGE_SIZE = 10

def get_total_count(user_id: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM game_sessions WHERE user_id = ?", (user_id,))
        total = cur.fetchone()[0]
    except Exception:
        total = 0
    finally:
        conn.close()
    return total

def fetch_matches(user_id: int, page: int):
    """
    Fetch a page of match history for the user.
    Always returns matches in ascending order (oldest first, newest last).
    """
    total = get_total_count(user_id)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))

    offset = (page - 1) * PAGE_SIZE
    limit = PAGE_SIZE

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            SELECT is_win, mode, played_at, bet
              FROM game_sessions
             WHERE user_id = ?
             ORDER BY played_at ASC
             LIMIT ? OFFSET ?
        """, (user_id, limit, offset))
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    return rows, total, total_pages

def build_matches_text(matches, page, total_count):
    if not matches:
        return "📅 <b>Your Matches History</b>\n\n<em>No matches found.</em>"

    EMOJI = {
        "dice":       "🎲",
        "darts":      "🎯",
        "basketball": "🏀",
        "soccer":     "⚽",
        "bowling":    "🎳",
        "roulette":   "🎰"
    }

    # Calculate the index for the first item on this page
    start_idx = (page - 1) * PAGE_SIZE + 1

    lines = []
    for i, (is_win, mode, ts, bet) in enumerate(matches):
        idx = start_idx + i
        mark = "✅" if is_win else "❌"
        emoji = EMOJI.get(mode, "")
        try:
            dt = datetime.fromisoformat(ts)
            dt_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            dt_str = ts
        lines.append(f"{idx}. {mark} {emoji} | {dt_str} | <b>Bet: ${bet:.2f}</b>")
    return "📅 <b>Your Matches History</b>\n\n" + "\n".join(lines)

def build_pagination_kb(user_id: int, page: int, total_pages: int):
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("⬅ Prev", callback_data=f"matches:{page-1}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton("Next ➡", callback_data=f"matches:{page+1}"))
    return InlineKeyboardMarkup([buttons]) if buttons else None

async def matches_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /matches — show the last page of history (most recent matches).
    """
    user_id = update.effective_user.id
    total = get_total_count(user_id)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = total_pages  # Always show last page first
    matches, total_count, total_pages = fetch_matches(user_id, page)
    text = build_matches_text(matches, page, total_count)
    kb = build_pagination_kb(user_id, page, total_pages)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)

async def matches_page_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle callbacks "matches:<page>".
    """
    q = update.callback_query
    _, pg = q.data.split(":", 1)
    page = max(1, int(pg))
    user_id = q.from_user.id

    matches, total_count, total_pages = fetch_matches(user_id, page)
    text = build_matches_text(matches, page, total_count)
    kb = build_pagination_kb(user_id, page, total_pages)

    await q.answer()
    await q.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
