import random
import asyncio
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# —— Hook in your real balance + stats functions here —— #
from balance import get_balance, update_balance, add_wager
from models import get_connection, update_stats

# —— Configuration —— #
HOUSE_EDGE  = 4.0
DEFAULT_BET = 5.0

# —— Game modes with their emojis & option lists —— #
MODES = [
    {"name": "dice",       "emoji": "🎲", "options": [str(i) for i in range(1, 7)]},
    {"name": "darts",      "emoji": "🎯", "options": [str(i) for i in range(1, 7)]},  # 1–6
    {"name": "basketball", "emoji": "🏀", "options": ["Score", "Miss", "Stuck"]},
    {"name": "soccer",     "emoji": "⚽", "options": ["Goal", "Miss", "Bar"]},
    {"name": "bowling",    "emoji": "🎳", "options": [str(i) for i in [0,1,3,4,5,6]]},
]

def calc_multiplier(opt_ct: int, pick_ct: int) -> float:
    if pick_ct < 1 or pick_ct > opt_ct:
        return 0.0
    fair = opt_ct / pick_ct
    return round(fair * (100 - HOUSE_EDGE) / 100, 2)

def build_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Play",  callback_data="predict_action:play"),
            InlineKeyboardButton("ℹ️ Rules", callback_data="predict_action:rules"),
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="predict_action:back")
        ]
    ])

def build_game_keyboard(state: dict) -> InlineKeyboardMarkup:
    mode  = MODES[state["mode_index"]]
    opts  = mode["options"]
    picks = state.get("picks", [])
    bet   = state.get("bet", DEFAULT_BET)

    # Row 1: option toggles
    row1 = [
        InlineKeyboardButton(
            f"{o}{' ✅' if o in picks else ''}",
            callback_data=f"predict_opt:{o}"
        ) for o in opts
    ]
    # Row 2: bet adjust
    row2 = [
        InlineKeyboardButton("½ Bet",            callback_data="predict_bet:half"),
        InlineKeyboardButton(f"Bet: ${bet:.2f}", callback_data="predict_bet:none"),
        InlineKeyboardButton("2× Bet",           callback_data="predict_bet:dbl"),
    ]
    # Row 3: mode arrows
    row3 = [
        InlineKeyboardButton("◀️",                    callback_data="predict_mode:prev"),
        InlineKeyboardButton(f"Mode: {mode['emoji']}", callback_data="predict_mode:none"),
        InlineKeyboardButton("▶️",                    callback_data="predict_mode:next"),
    ]
    # Row 4: back & start
    row4 = [
        InlineKeyboardButton("⬅️ Back",  callback_data="predict_action:back"),
        InlineKeyboardButton("✅ Start", callback_data="predict_action:start"),
    ]

    return InlineKeyboardMarkup([row1, row2, row3, row4])

def build_header(user_id: int, state: dict) -> str:
    mode    = MODES[state["mode_index"]]
    bal     = get_balance(user_id)
    opt_ct  = len(mode["options"])
    pick_ct = max(1, len(state.get("picks", [])))
    mult    = calc_multiplier(opt_ct, pick_ct)

    return (
        f"{mode['emoji']} <b>{mode['name'].capitalize()} Prediction</b>\n\n"
        f"Your balance: ${bal:.2f}\n"
        f"Multiplier: <b>{mult:.2f}x</b>\n\n"
        "Make your prediction:"
    )

async def _show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎲 <b>Prediction Games</b>\n\n"
        "Try Dice, Darts, Basketball,\n"
        "Soccer or Bowling!\n\n"
        "Tip: `/predict <bet>` to start quickly.\n"
        "Examples:\n"
        "`/predict 10` — bet $10\n"
        "`/predict half` — half your balance\n"
        "`/predict all` — all-in"
    )
    kb = build_menu_keyboard()
    if update.callback_query:
        q = update.callback_query
        await q.answer()
        await q.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

async def _show_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = context.user_data
    st.setdefault("mode_index", 0)
    st.setdefault("picks",      [])
    st.setdefault("bet",        DEFAULT_BET)

    header = build_header(update.effective_user.id, st)
    kb     = build_game_keyboard(st)
    if update.callback_query:
        q = update.callback_query
        await q.answer()
        await q.edit_message_text(header, parse_mode="HTML", reply_markup=kb)
    else:
        await update.message.reply_text(header, parse_mode="HTML", reply_markup=kb)

async def predict_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bal = get_balance(update.effective_user.id)
    if context.args:
        a = context.args[0].lower()
        if a == "half":
            bet = round(bal/2, 2)
        elif a == "all":
            bet = bal
        else:
            try:
                bet = float(a)
            except ValueError:
                return await _show_menu(update, context)
        if bet <= 0 or bet > bal:
            return await update.message.reply_text(f"❗️Invalid bet. You have ${bal:.2f}.")
        context.user_data.update({"mode_index":0, "picks":[], "bet":bet})
        return await _show_game(update, context)

    await _show_menu(update, context)

async def predict_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q        = update.callback_query
    kind, arg = q.data.split(":", 1)
    st       = context.user_data
    await q.answer()

    # ─── Action Buttons ─────────────────────────────── #
    if kind == "predict_action":
        if arg == "play":
            st.update({"mode_index":0, "picks":[], "bet":DEFAULT_BET})
            return await _show_game(update, context)
        if arg == "rules":
            rules = (
                "📜 <b>Rules</b>\n\n"
                "1. Press ✅ Play\n"
                "2. Tap options to pick\n"
                "3. Adjust bet with ½ Bet or 2× Bet\n"
                "4. Use ◀️ ▶️ to switch modes\n"
                "5. Press ✅ Start to roll\n"
                "6. Win if the result matches your pick!"
            )
            return await q.edit_message_text(rules, parse_mode="HTML")
        if arg == "back":
            return await _show_menu(update, context)
        if arg == "start":
            user  = q.from_user
            picks = st.get("picks", [])
            bet   = st.get("bet", 0.0)
            mode  = MODES[st["mode_index"]]
            bal   = get_balance(user.id)

            if not picks:
                return await q.answer("❗️Select at least one option.", show_alert=True)
            if bet <= 0 or bet > bal:
                return await q.answer(f"Insufficient balance (${bal:.2f}).", show_alert=True)

            update_balance(user.id, -bet)
            add_wager(user.id, bet)

            dice_msg = await q.message.reply_dice(emoji=mode["emoji"])
            await asyncio.sleep(1)

            if mode["name"] in ("dice", "darts", "bowling"):
                res = str(dice_msg.dice.value)
            else:
                res = random.choice(mode["options"])

            opt_ct  = len(mode["options"])
            pick_ct = len(picks)
            mult    = calc_multiplier(opt_ct, pick_ct)
            payout  = round(bet * mult, 2) if res in picks else 0.0
            if res in picks:
                update_balance(user.id, payout)

            conn = get_connection()
            cur  = conn.cursor()
            cur.execute("""
                INSERT INTO game_sessions(user_id, mode, played_at, bet, won_amount, is_win)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user.id,
                mode["name"],
                datetime.utcnow().isoformat(),
                bet,
                payout,
                1 if res in picks else 0
            ))
            conn.commit()
            conn.close()
            update_stats(user.id, res in picks)

            result_text = (
                f"{mode['emoji']} {user.mention_html()}\n\n"
                f"{'🎉 You won!' if res in picks else '🤖 I win!'} Rolled: <b>{res}</b>\n"
                f"{'Payout' if res in picks else 'Loss'}: <b>${payout:.2f}</b>\n"
                f"Balance: <b>${get_balance(user.id):.2f}</b>"
            )
            await q.message.chat.send_message(
                result_text,
                parse_mode="HTML",
                reply_to_message_id=dice_msg.message_id
            )

            # clean up old UI and re-show fresh
            await q.message.delete()
            st.update({"mode_index":0, "picks":[], "bet":DEFAULT_BET})
            header = build_header(user.id, st)
            kb     = build_game_keyboard(st)
            await q.message.chat.send_message(header, parse_mode="HTML", reply_markup=kb)
            return

    # ─── Mode ← → ──────────────────────────────────── #
    if kind == "predict_mode":
        if arg == "prev":
            st["mode_index"] = (st["mode_index"] - 1) % len(MODES)
        elif arg == "next":
            st["mode_index"] = (st["mode_index"] + 1) % len(MODES)
        return await _show_game(update, context)

    # ─── Option Toggles ────────────────────────────── #
    if kind == "predict_opt":
        picks = st.setdefault("picks", [])
        if arg in picks:
            picks.remove(arg)
        else:
            picks.append(arg)
        return await _show_game(update, context)

    # ─── Bet Adjust ────────────────────────────────── #
    if kind == "predict_bet":
        if arg == "half":
            st["bet"] = max(0.01, st["bet"]/2)
        elif arg == "dbl":
            st["bet"] = st["bet"] * 2
        return await _show_game(update, context)

def register_predict_handlers(app):
    from telegram.ext import CommandHandler, CallbackQueryHandler
    app.add_handler(CommandHandler("predict", predict_command))
    app.add_handler(
        CallbackQueryHandler(
            predict_router,
            pattern="^(predict_action|predict_mode|predict_opt|predict_bet):"
        )
    )
