# leaderboard.py
from __future__ import annotations

import sqlite3
from typing import List, Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

DB_PATH = "dicegame.db"  # <-- your DB file

# -----------------------------
# Helpers
# -----------------------------
def tg_username(user_id: int, fallback: Optional[str] = None) -> str:
    """
    Replace with your real user lookup if you store names in DB.
    Using a Telegram deep-link mention keeps it clickable even if you
    don't know the display name yet.
    """
    name = fallback or f"User {user_id}"
    # HTML mention; make sure to set parse_mode=HTML when sending
    return f"<a href='tg://user?id={user_id}'>{name}</a>"

def fmt_money(v: float) -> str:
    return f"${v:,.2f}"

def medal(n: int) -> str:
    return "🥇" if n == 1 else "🥈" if n == 2 else "🥉" if n == 3 else f"{n})"

def shield() -> str:
    return "🛡️"

# -----------------------------
# DB QUERIES
# -----------------------------
def q(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[tuple]:
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return rows

def top_wagerers_all_time(limit: int = 10) -> List[Tuple[int, float]]:
    """
    Table expected: wagers(user_id INTEGER, amount REAL, timestamp TEXT ISO8601)
    Returns [(user_id, total_wager), ...]
    """
    conn = sqlite3.connect(DB_PATH)
    rows = q(
        conn,
        """
        SELECT user_id, SUM(amount) AS total_wager
        FROM wagers
        GROUP BY user_id
        ORDER BY total_wager DESC
        LIMIT ?
        """,
        (limit,),
    )
    conn.close()
    return rows

def biggest_dices_this_week(limit: int = 5) -> List[Tuple[int, int, float]]:
    """
    Table expected: games(p1_id INTEGER, p2_id INTEGER, amount REAL, created_at TEXT ISO8601)
    Returns [(p1_id, p2_id, amount), ...] for the last full Monday-Sunday range including today.
    """
    conn = sqlite3.connect(DB_PATH)
    rows = q(
        conn,
        """
        SELECT p1_id, p2_id, amount
        FROM games
        WHERE created_at >= date('now','weekday 0','-6 days')
        ORDER BY amount DESC
        LIMIT ?
        """,
        (limit,),
    )
    conn.close()
    return rows

def biggest_dices_all_time(limit: int = 5) -> List[Tuple[int, int, float]]:
    conn = sqlite3.connect(DB_PATH)
    rows = q(
        conn,
        """
        SELECT p1_id, p2_id, amount
        FROM games
        ORDER BY amount DESC
        LIMIT ?
        """,
        (limit,),
    )
    conn.close()
    return rows

# -----------------------------
# TEXT BUILDERS
# -----------------------------
def leaderboard_buttons(active: str) -> InlineKeyboardMarkup:
    # active ∈ {"wager_all","dice_week","dice_all"}
    def style(label: str, is_active: bool) -> str:
        return f"• {label} •" if is_active else label

    row = [
        InlineKeyboardButton(
            style("Most Wagered all time", active == "wager_all"),
            callback_data="lb:wager_all",
        ),
    ]
    row2 = [
        InlineKeyboardButton(
            style("Biggest Dices this week", active == "dice_week"),
            callback_data="lb:dice_week",
        ),
    ]
    row3 = [
        InlineKeyboardButton(
            style("Biggest Dices all time", active == "dice_all"),
            callback_data="lb:dice_all",
        ),
    ]
    back = [InlineKeyboardButton("🔙 Back", callback_data="lb:back")]
    return InlineKeyboardMarkup([row, row2, row3, back])

def text_wager_all_time() -> str:
    data = top_wagerers_all_time(10)
    if not data:
        return "🏆 Leaderboard\n\nNo data available."

    lines = ["🏆 <b>Leaderboard</b>", "", "Most Wagered all time:"]
    for i, (uid, total) in enumerate(data, start=1):
        lines.append(f"{medal(i)} {tg_username(uid)} - {fmt_money(total)}")
    return "\n".join(lines)

def text_biggest_dices_week() -> str:
    data = biggest_dices_this_week(5)
    if not data:
        return "🏆 Leaderboard\n\nNo data available."

    lines = ["🏆 <b>Leaderboard</b>", "", "Biggest Dices this week:"]
    for i, (p1, p2, amt) in enumerate(data, start=1):
        lines.append(f"{medal(i)} {shield()} {tg_username(p1)}  -  {shield()} {tg_username(p2)} • {fmt_money(amt)}")
    return "\n".join(lines)

def text_biggest_dices_all_time() -> str:
    data = biggest_dices_all_time(5)
    if not data:
        return "🏆 Leaderboard\n\nNo data available."

    lines = ["🏆 <b>Leaderboard</b>", "", "Biggest Dices all time:"]
    for i, (p1, p2, amt) in enumerate(data, start=1):
        lines.append(f"{medal(i)} {shield()} {tg_username(p1)}  -  {shield()} {tg_username(p2)} • {fmt_money(amt)}")
    return "\n".join(lines)

# -----------------------------
# HANDLERS
# -----------------------------
async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Default tab: "Most Wagered all time"
    text = text_wager_all_time()
    kb = leaderboard_buttons("wager_all")
    await update.message.reply_text(
        text, reply_markup=kb, parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )

async def leaderboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "lb:wager_all":
        await query.edit_message_text(
            text_wager_all_time(),
            reply_markup=leaderboard_buttons("wager_all"),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    elif data == "lb:dice_week":
        await query.edit_message_text(
            text_biggest_dices_week(),
            reply_markup=leaderboard_buttons("dice_week"),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    elif data == "lb:dice_all":
        await query.edit_message_text(
            text_biggest_dices_all_time(),
            reply_markup=leaderboard_buttons("dice_all"),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    elif data == "lb:back":
        # If you have a main menu, show it here.
        # For now, just go back to the default leaderboard tab.
        await query.edit_message_text(
            text_wager_all_time(),
            reply_markup=leaderboard_buttons("wager_all"),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
