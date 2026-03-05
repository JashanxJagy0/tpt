from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import sqlite3
from datetime import datetime

DB_PATH = "dicegame.db"  # adjust if your file is named differently

def get_user_stats(user_id: int) -> dict:
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Base defaults
    stats = {
        'level':       'Silver III',
        'games_played': 0,
        'wins':         0,
        'wagered':     0.0,
        'won':         0.0,
        'first_game':  None,
        'last_game':   None,
        'join_date':   None,
    }

    # 1) If you ever add a join_date column in users, grab it
    try:
        cursor.execute("SELECT join_date FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row and row[0]:
            stats['join_date'] = row[0]
    except sqlite3.OperationalError:
        # no such column/table → ignore
        pass

    # 2) Pull all aggregated stats from game_sessions
    try:
        cursor.execute("""
            SELECT
              COUNT(*)            AS games_played,
              SUM(is_win)         AS wins,
              SUM(bet)            AS total_wagered,
              SUM(won_amount)     AS total_won,
              MIN(played_at)      AS first_game,
              MAX(played_at)      AS last_game
            FROM game_sessions
            WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if row:
            stats['games_played'] = row[0] or 0
            stats['wins']         = row[1] or 0
            stats['wagered']      = row[2] or 0.0
            stats['won']          = row[3] or 0.0
            stats['first_game']   = row[4]
            stats['last_game']    = row[5]
    except sqlite3.OperationalError:
        # table missing → leave defaults
        pass

    conn.close()
    return stats

def format_stats_message(username: str, stats: dict) -> str:
    win_ratio = (stats['wins'] / stats['games_played'] * 100) if stats['games_played'] else 0.0

    def fmt(dt_str: str) -> str:
        if not dt_str:
            return "N/A"
        try:
            # support ISO timestamps
            return datetime.fromisoformat(dt_str).strftime("%b %d, %Y")
        except ValueError:
            return "N/A"

    return (
        f"ℹ️ <b>Stats of {username}</b>\n\n"
        f"Level: 🛡 <b>{stats['level']}</b>\n"
        f"Games Played: <b>{stats['games_played']}</b>\n"
        f"Wins: <b>{stats['wins']} ({win_ratio:.2f}%)</b>\n"
        f"Total Wagered: <b>${stats['wagered']:.2f}</b>\n"
        f"Total Won: <b>${stats['won']:.2f}</b>\n\n"
        f"Join date: <b>{fmt(stats['join_date'])}</b>\n"
        f"First game: <b>{fmt(stats['first_game'])}</b>\n"
        f"Last game: <b>{fmt(stats['last_game'])}</b>\n"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    stats = get_user_stats(user.id)
    msg   = format_stats_message(user.first_name or user.username or "User", stats)

    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]
    await update.message.reply_text(
        msg,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
