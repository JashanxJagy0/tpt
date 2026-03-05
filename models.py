import os
import sqlite3
from datetime import datetime
import os

DB_PATH = os.getenv("DB_PATH", "dicegame.db")



# You can override this via environment if needed
DB_PATH = os.getenv("DB_PATH", "dicegame.db")

def get_connection():
    """Open a connection to the configured SQLite database."""
    return sqlite3.connect(DB_PATH)

def initialize_database():
    """Create all required tables if they don't already exist."""
    conn   = get_connection()
    cursor = conn.cursor()

    # ─── Users ──────────────────────────────────────────────────────────────
    # Added join_date with default timestamp
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id      INTEGER PRIMARY KEY,
        balance      REAL    DEFAULT 0,
        games_played INTEGER DEFAULT 0,
        games_won    INTEGER DEFAULT 0,
        games_lost   INTEGER DEFAULT 0,
        join_date    TEXT    DEFAULT (datetime('now'))
    )
    """)

    # ─── Transactions ───────────────────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER,
        type      TEXT,
        amount    REAL,
        details   TEXT,
        timestamp TEXT DEFAULT (datetime('now'))
    )
    """)

    # ─── Wagers ─────────────────────────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wagers (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER,
        amount    REAL,
        timestamp TEXT DEFAULT (datetime('now'))
    )
    """)

    # ─── Dice Matches (optional state) ─────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dice_matches (
        match_id   TEXT PRIMARY KEY,
        data       TEXT,
        updated_at TEXT DEFAULT (datetime('now'))
    )
    """)

    # ─── Game Sessions ─────────────────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS game_sessions (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER NOT NULL,
        mode         TEXT    NOT NULL,
        played_at    TEXT    NOT NULL,
        bet          REAL    NOT NULL,
        won_amount   REAL    NOT NULL,
        is_win       INTEGER NOT NULL
    )
    """)

    # ─── Referrers: who has codes, invite counts & earnings ───────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS referrers (
        user_id   INTEGER PRIMARY KEY,
        code      TEXT    UNIQUE,
        invited   INTEGER DEFAULT 0,
        earnings  REAL    DEFAULT 0.0
    )
    """)

    # ─── Referred: which user was referred by whom ────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS referred (
        user_id     INTEGER PRIMARY KEY,
        referrer_id INTEGER,
        FOREIGN KEY(referrer_id) REFERENCES referrers(user_id)
    )
    """)

    conn.commit()
    conn.close()


# --- Balance Helpers --------------------------------------------------------

def get_balance(user_id: int) -> float:
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0.0

def update_balance(user_id: int, amount_delta: float):
    conn   = get_connection()
    cursor = conn.cursor()
    # ensure user row exists, capturing join_date automatically
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, balance)
        VALUES (?, 0)
    """, (user_id,))
    cursor.execute("""
        UPDATE users
           SET balance = balance + ?
         WHERE user_id = ?
    """, (amount_delta, user_id))
    conn.commit()
    conn.close()

def set_balance(user_id: int, new_balance: float):
    conn   = get_connection()
    cursor = conn.cursor()
    # ensure user row exists, capturing join_date automatically
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, balance)
        VALUES (?, 0)
    """, (user_id,))
    cursor.execute("""
        UPDATE users
           SET balance = ?
         WHERE user_id = ?
    """, (new_balance, user_id))
    conn.commit()
    conn.close()


# --- Transactions -----------------------------------------------------------

def log_transaction(user_id: int, type_: str, amount: float, details: str):
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (user_id, type, amount, details)
        VALUES (?, ?, ?, ?)
    """, (user_id, type_, amount, details))
    conn.commit()
    conn.close()


# --- Wagers -----------------------------------------------------------------

def add_wager(user_id: int, amount: float):
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO wagers (user_id, amount)
        VALUES (?, ?)
    """, (user_id, amount))
    conn.commit()
    conn.close()

def get_wager_sum_last_7_days(user_id: int) -> float:
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
          FROM wagers
         WHERE user_id = ?
           AND timestamp >= datetime('now', '-7 days')
    """, (user_id,))
    total = cursor.fetchone()[0]
    conn.close()
    return total


# --- Stats ------------------------------------------------------------------

def update_stats(user_id: int, won: bool):
    conn   = get_connection()
    cursor = conn.cursor()
    # ensure user row exists (captures join_date)
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, balance)
        VALUES (?, 0)
    """, (user_id,))
    cursor.execute("""
        UPDATE users
           SET games_played = games_played + 1
         WHERE user_id = ?
    """, (user_id,))
    if won:
        cursor.execute("""
            UPDATE users
               SET games_won = games_won + 1
             WHERE user_id = ?
        """, (user_id,))
    else:
        cursor.execute("""
            UPDATE users
               SET games_lost = games_lost + 1
             WHERE user_id = ?
        """, (user_id,))
    conn.commit()
    conn.close()

def get_stats(user_id: int):
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT games_played, games_won, games_lost, balance, join_date
          FROM users
         WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "games_played": row[0],
            "games_won":    row[1],
            "games_lost":   row[2],
            "balance":      row[3],
            "join_date":    row[4],
        }
    return {"games_played": 0, "games_won": 0, "games_lost": 0, "balance": 0.0, "join_date": None}


# --- Game Sessions ----------------------------------------------------------
def save_session(user_id: int, mode: str, bet: float, won: float, is_win: bool):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO game_sessions(user_id, mode, played_at, bet, won_amount, is_win) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, mode, datetime.utcnow().isoformat(), bet, won, int(is_win))
    )
    conn.commit()
    conn.close()

# --- Dice Matches Persistence (optional) -----------------------------------

def save_match(match_id: str, data: str):
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO dice_matches (match_id, data)
        VALUES (?, ?)
    """, (match_id, data))
    conn.commit()
    conn.close()

def load_match(match_id: str):
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM dice_matches WHERE match_id = ?", (match_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def delete_match(match_id: str):
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dice_matches WHERE match_id = ?", (match_id,))
    conn.commit()
    conn.close()


# --- Referral Helpers -------------------------------------------------------

def create_referral_code(user_id: int, code: str):
    """
    Assign or overwrite a referral code for a user.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO referrers (user_id, code)
          VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET code=excluded.code
    """, (user_id, code))
    conn.commit()
    conn.close()

def delete_referral_code(user_id: int):
    """
    Remove a user's referral code and any referrals they've made.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM referrers WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM referred  WHERE referrer_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_referral_code(user_id: int) -> str | None:
    """
    Return the code for a given user, or None.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT code FROM referrers WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_user_by_code(code: str) -> int | None:
    """
    Lookup which user owns a given code.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM referrers WHERE code = ?", (code,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def has_been_referred(user_id: int) -> bool:
    """
    Check if a user has already used a code.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM referred WHERE user_id = ?", (user_id,))
    found = cursor.fetchone() is not None
    conn.close()
    return found

def record_referral(user_id: int, referrer_id: int, fee_amount: float):
    """
    Link a user to their referrer, increment invite count,
    and credit 10% of the house fee back to the referrer.
    """
    conn   = get_connection()
    cursor = conn.cursor()

    # only record once
    cursor.execute("""
        INSERT OR IGNORE INTO referred (user_id, referrer_id)
        VALUES (?, ?)
    """, (user_id, referrer_id))

    # bump invited count & earnings
    cursor.execute("""
        UPDATE referrers
           SET invited  = invited  + 1,
               earnings = earnings + ?
         WHERE user_id = ?
    """, (round(fee_amount * 0.10, 2), referrer_id))

    conn.commit()
    conn.close()

    # also credit their balance
    update_balance(referrer_id, round(fee_amount * 0.10, 2))

def get_referrer_stats(user_id: int) -> dict:
    """
    Return { invited: int, earnings: float } for a referrer.
    """
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT invited, earnings
          FROM referrers
         WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"invited": row[0], "earnings": row[1]}
    return {"invited": 0, "earnings": 0.0}

initialize_database()

