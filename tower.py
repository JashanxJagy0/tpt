"""
Monkey Tower — Telegram Inline-Keyboard game (PTB v20+)

External deps expected in your project:
- balance.get_balance(user_id) -> float
- balance.update_balance(user_id, delta: float) -> None        # delta can be negative or positive
- balance.add_wager(user_id, amount: float) -> None
- models.update_stats(user_id, won: bool) -> None

If you already have an Application, just register the handlers from main()
or copy the functions into your bot module and wire the handlers there.
"""

import random
from typing import List, Tuple, Set

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, ApplicationBuilder,
    CommandHandler, CallbackQueryHandler, ContextTypes
)

# ─── Config ──────────────────────────────────────────────────────────────

TOWER_ROWS = 8
MIN_BET = 0.5
HOUSE_EDGE = 1.00  # use table values directly

# Zero-width no-break space so Telegram allows "blank" buttons
ZWNBSP = "\u2060"

TILE = {
    "blank": ZWNBSP,
    "play": "🟩",     # playable cell (matches your UI)
    "leaf": "🌴",     # picked safe tile (what you called "tree")
    "snake": "🐍",
    "banana": "🍌",
    "explode": "💥",
}

DIFFICULTIES: List[Tuple[str, str, int]] = [
    ("Easy", "🟢", 4),
    ("Medium", "🟡", 3),
    ("Hard", "🔴", 2),
]

_RAW_PAYOUTS = {
    # first step 1.25x so $0.50 -> $0.63
    "Easy":   [1.25, 1.60, 2.05, 2.60, 3.30, 4.20, 5.40, 6.95],
    "Medium": [1.86, 2.74, 4.03, 5.93, 8.73, 12.86, 18.97, 28.00],
    "Hard":   [3.00, 6.00, 12.00, 24.00, 48.00, 96.00, 192.00, 384.00],
}

def payout_table(difficulty: str):
    raw = _RAW_PAYOUTS.get(difficulty, _RAW_PAYOUTS["Medium"])
    return [round(x * HOUSE_EDGE, 2) for x in raw]

# External app funcs (import from your project)
from balance import get_balance, update_balance, add_wager
from models import update_stats


# ─── State Helpers ────────────────────────────────────────────────────────

def _get(ctx, key, default):
    return ctx.user_data.get(key, default)

def _set(ctx, key, val):
    ctx.user_data[key] = val

def _difficulty(ctx):
    return _get(ctx, "tower_difficulty", "Medium")

def _bet(ctx):
    return _get(ctx, "tower_bet", MIN_BET)

def _row(ctx):
    """Current playable row (0 = bottom)."""
    return _get(ctx, "tower_row", 0)

def _board(ctx):
    return _get(ctx, "tower_board", [])

def _chosen(ctx) -> Set[tuple]:
    """Safe picks made so far {(row, col), ...}."""
    return _get(ctx, "tower_chosen", set())


def new_board(difficulty: str):
    cols = dict((d, c) for d, _, c in DIFFICULTIES)[difficulty]
    board = []
    for _ in range(TOWER_ROWS):
        row = ["leaf"] * cols
        row[random.randrange(cols)] = "snake"
        board.append(row)
    # ensure at least one banana on the top row (index TOWER_ROWS-1)
    for i in range(cols):
        if board[-1][i] != "snake":
            board[-1][i] = "banana"
    return board


# ─── Header ──────────────────────────────────────────────────────────────

def header_text(ctx, bal: float):
    bet = _bet(ctx)
    row = _row(ctx)
    diff = _difficulty(ctx)

    lines = [
        "🐒 <b>Monkey Tower</b>",
        "",
        f"Bet: <b>${bet:.2f}</b>",
        f"Balance: <b>${bal:.2f}</b>",
    ]

    # After first safe pick (row > 0), show profit + multiplier
    if row > 0:
        mult = payout_table(diff)[row - 1]
        payout = mult * bet
        lines += ["", f"Total profit: <b>${payout:.2f}</b> ({mult:.2f}x)"]

    lines += ["", "Click on 🟩 to climb the tree!"]
    return "\n".join(lines)


# ─── UI Keyboards ────────────────────────────────────────────────────────

def build_keyboard(ctx: ContextTypes.DEFAULT_TYPE, finished: bool, can_start=False, can_pick=False, reveal=False):
    diff = _difficulty(ctx)
    cols = dict((d, c) for d, _, c in DIFFICULTIES)[diff]
    row = _row(ctx)
    board = _board(ctx)
    chosen = _chosen(ctx)

    names = [d for d, _, _ in DIFFICULTIES]
    diff_emoji = dict((d, e) for d, e, _ in DIFFICULTIES)[diff]

    kb: List[List[InlineKeyboardButton]] = []

    # Top action row
    if can_start:
        kb.append([InlineKeyboardButton("✅ Start Game", callback_data="tower_start")])
    elif can_pick and row > 0:  # cashout right after clearing first row
        mult = payout_table(diff)[row - 1]
        payout = mult * _bet(ctx)
        kb.append([InlineKeyboardButton(f"💰 Cashout ${payout:.2f}", callback_data="tower_cashout")])

    # Difficulty row
    kb.append([
        InlineKeyboardButton("⬅️", callback_data="tower_diff_left"),
        InlineKeyboardButton(f"{diff_emoji} {diff}", callback_data="tower_none"),
        InlineKeyboardButton("➡️", callback_data="tower_diff_right"),
    ])

    # IMPORTANT: Render TOP -> BOTTOM so the bottom row appears at the bottom visually.
    for r in range(TOWER_ROWS - 1, -1, -1):
        this_row = []
        for c in range(cols):
            if finished or reveal:
                cell = board[r][c]
                if cell == "snake" and _get(ctx, "tower_snake", (-1, -1)) == (r, c):
                    this_row.append(InlineKeyboardButton(TILE["explode"], callback_data="tower_none"))
                else:
                    this_row.append(InlineKeyboardButton(TILE.get(cell, TILE["blank"]), callback_data="tower_none"))
            elif r < row:
                # Past rows: show picked cell as 🌴; all other cells BLANK
                if (r, c) in chosen:
                    this_row.append(InlineKeyboardButton(TILE["leaf"], callback_data="tower_none"))
                else:
                    this_row.append(InlineKeyboardButton(TILE["blank"], callback_data="tower_none"))
            elif r == row and can_pick:
                # Current playable row
                this_row.append(InlineKeyboardButton(TILE["play"], callback_data=f"tower_pick:{r}:{c}"))
            else:
                this_row.append(InlineKeyboardButton(TILE["blank"], callback_data="tower_none"))
        kb.append(this_row)

    # Bottom menu
    kb.append([InlineKeyboardButton("🛈 Rules", callback_data="tower_rules")])
    return InlineKeyboardMarkup(kb)


# ─── /tower Command ───────────────────────────────────────────────────────

async def tower_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bal = get_balance(user.id)
    args = context.args
    if not args:
        # Intro
        text = (
            "🐒 <b>Monkey Tower</b>\n\n"
            "Your mission is to climb to the top of the tree and collect the 🍌 bananas.\n\n"
            "To quickly start the game, type <code>/tower &lt;bet&gt;</code>\n\n"
            "<b>Examples:</b>\n"
            "/tower 10 - bet $10\n"
            "/tower half - bet half of the balance\n"
            "/tower all - go all-in"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🐒 Play", callback_data="tower_play"),
            InlineKeyboardButton("🛈 Rules", callback_data="tower_rules"),
        ]])
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
        return

    # /tower <amount>
    arg = args[0].lower()
    if arg == "half":
        bet = round(bal / 2, 2)
    elif arg == "all":
        bet = bal
    else:
        try:
            bet = float(arg)
        except Exception:
            bet = MIN_BET

    if bet < MIN_BET:
        bet = MIN_BET
    if bet > bal:
        await update.message.reply_text(f"⛔ You only have ${bal:.2f}.")
        return

    # waiting to start
    _set(context, "tower_bet", bet)
    _set(context, "tower_difficulty", "Medium")
    _set(context, "tower_row", 0)
    _set(context, "tower_board", new_board("Medium"))
    _set(context, "tower_snake", (-1, -1))
    _set(context, "tower_chosen", set())

    text = (
        "🐒 <b>Monkey Tower</b>\n\n"
        f"Bet: <b>${bet:.2f}</b>\n"
        f"Balance: <b>${bal:.2f}</b>"
    )
    await update.message.reply_text(text, parse_mode="HTML",
                                    reply_markup=build_keyboard(context, finished=False, can_start=True))


# ─── Callbacks ───────────────────────────────────────────────────────────

async def tower_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    bal = get_balance(q.from_user.id)
    bet = MIN_BET if bal >= MIN_BET else bal
    _set(context, "tower_bet", bet)
    _set(context, "tower_difficulty", "Medium")
    _set(context, "tower_row", 0)
    _set(context, "tower_board", new_board("Medium"))
    _set(context, "tower_snake", (-1, -1))
    _set(context, "tower_chosen", set())
    text = (
        "🐒 <b>Monkey Tower</b>\n\n"
        f"Bet: <b>${bet:.2f}</b>\n"
        f"Balance: <b>${bal:.2f}</b>"
    )
    await q.edit_message_text(text, parse_mode="HTML",
                              reply_markup=build_keyboard(context, finished=False, can_start=True))

async def tower_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    text = (
        "<b>Monkey Tower Rules</b>\n\n"
        "• 🐒 Climb up the tree to increase the multiplier.\n"
        "• 🟢 Difficulty chosen will influence the payout multiplier progression.\n"
        "• 💰 You can lock in winnings after at least one safe climb.\n"
        "• 🐍 Hitting a snake ends the game and loses the bet.\n"
        "• 🍌 Reach the top to win bananas."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="tower_play")]])
    await q.edit_message_text(text, parse_mode="HTML", reply_markup=kb)

async def tower_diff_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    names = [d for d, _, _ in DIFFICULTIES]
    idx = names.index(_difficulty(context))
    new = names[(idx - 1) % len(names)]
    _set(context, "tower_difficulty", new)
    _set(context, "tower_board", new_board(new))
    _set(context, "tower_row", 0)
    _set(context, "tower_snake", (-1, -1))
    _set(context, "tower_chosen", set())
    bal = get_balance(q.from_user.id)
    bet = _bet(context)
    await q.edit_message_text(
        "🐒 <b>Monkey Tower</b>\n\n"
        f"Bet: <b>${bet:.2f}</b>\n"
        f"Balance: <b>${bal:.2f}</b>",
        parse_mode="HTML",
        reply_markup=build_keyboard(context, finished=False, can_start=True)
    )

async def tower_diff_right(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    names = [d for d, _, _ in DIFFICULTIES]
    idx = names.index(_difficulty(context))
    new = names[(idx + 1) % len(names)]
    _set(context, "tower_difficulty", new)
    _set(context, "tower_board", new_board(new))
    _set(context, "tower_row", 0)
    _set(context, "tower_snake", (-1, -1))
    _set(context, "tower_chosen", set())
    bal = get_balance(q.from_user.id)
    bet = _bet(context)
    await q.edit_message_text(
        "🐒 <b>Monkey Tower</b>\n\n"
        f"Bet: <b>${bet:.2f}</b>\n"
        f"Balance: <b>${bal:.2f}</b>",
        parse_mode="HTML",
        reply_markup=build_keyboard(context, finished=False, can_start=True)
    )

async def tower_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    user = q.from_user
    bal = get_balance(user.id)
    bet = _bet(context)
    if bal < bet:
        await q.answer("⛔ Insufficient balance!", show_alert=True)
        return
    update_balance(user.id, -bet)
    add_wager(user.id, bet)
    update_stats(user.id, False)
    _set(context, "tower_row", 0)           # bottom row is first playable
    _set(context, "tower_snake", (-1, -1))
    _set(context, "tower_chosen", set())
    bal = get_balance(user.id)
    await q.edit_message_text(
        header_text(context, bal),
        parse_mode="HTML",
        reply_markup=build_keyboard(context, finished=False, can_pick=True)
    )

async def tower_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _, r_s, c_s = q.data.split(":")
    r, c = int(r_s), int(c_s)
    board = _board(context)
    tile = board[r][c]
    _set(context, "tower_snake", (r, c))

    if tile == "snake":
        await _tower_end(update, context, snake=True, hit=(r, c))
        return

    # safe pick
    chosen = _chosen(context)
    chosen.add((r, c))
    _set(context, "tower_chosen", chosen)

    nr = r + 1
    _set(context, "tower_row", nr)
    if nr >= TOWER_ROWS:
        await _tower_end(update, context, win=True)
        return

    bal = get_balance(q.from_user.id)
    await q.edit_message_text(
        header_text(context, bal),           # profit line appears once row > 0
        parse_mode="HTML",
        reply_markup=build_keyboard(context, finished=False, can_pick=True),
    )

async def tower_cashout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    row = _row(context)
    diff = _difficulty(context)
    bet = _bet(context)
    amount = round(bet * payout_table(diff)[row - 1], 2)
    update_balance(q.from_user.id, amount)
    update_stats(q.from_user.id, True)
    await q.answer(f"Cashed out ${amount:.2f}", show_alert=True)
    await _tower_end(update, context, cashout=amount)

async def _tower_end(update: Update, context: ContextTypes.DEFAULT_TYPE, win=False, snake=False, cashout=None, hit=None):
    q = update.callback_query
    user_id = q.from_user.id
    bet = _bet(context)
    diff = _difficulty(context)

    if win:
        amount = round(bet * payout_table(diff)[-1], 2)
        update_balance(user_id, amount)
        update_stats(user_id, True)
        msg = f"🍌 Bananas! You won ${amount:.2f} ({payout_table(diff)[-1]:.2f}x)"
    elif snake:
        update_stats(user_id, False)
        msg = "🐍 You found the snake and lost."
    else:
        msg = f"🎉 You won ${cashout:.2f} ({cashout/bet:.2f}x)"

    bal = get_balance(user_id)

    await q.edit_message_text(
        f"🐒 <b>Monkey Tower</b>\n\n"
        f"Bet: <b>${bet:.2f}</b>\n"
        f"Balance: <b>${bal:.2f}</b>\n\n"
        f"{msg}",
        parse_mode="HTML",
        reply_markup=build_keyboard(context, finished=True, reveal=True)
    )

async def tower_none(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()


# ─── Wiring (example main) ────────────────────────────────────────────────

def main():
    TOKEN = "YOUR_BOT_TOKEN_HERE"
    app: Application = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("tower", tower_command))
    app.add_handler(CallbackQueryHandler(tower_play,       pattern=r"^tower_play$"))
    app.add_handler(CallbackQueryHandler(tower_rules,      pattern=r"^tower_rules$"))
    app.add_handler(CallbackQueryHandler(tower_diff_left,  pattern=r"^tower_diff_left$"))
    app.add_handler(CallbackQueryHandler(tower_diff_right, pattern=r"^tower_diff_right$"))
    app.add_handler(CallbackQueryHandler(tower_start,      pattern=r"^tower_start$"))
    app.add_handler(CallbackQueryHandler(tower_cashout,    pattern=r"^tower_cashout$"))
    app.add_handler(CallbackQueryHandler(tower_none,       pattern=r"^tower_none$"))
    app.add_handler(CallbackQueryHandler(tower_pick,       pattern=r"^tower_pick:\d+:\d+$"))

    app.run_polling()

if __name__ == "__main__":
    main()
