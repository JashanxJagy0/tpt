# roulette.py
# Requires: python-telegram-bot >= 20, Pillow

import os
import json
import html
import logging
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from io import BytesIO
from PIL import Image
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

# ─── External balance & DB ─────────────────────────────────────────────────────
from balance import get_balance, update_balance, add_wager
from models import get_connection, update_stats
from housebal import adjust_house_balance
from owner_guard import set_owner, check_owner, remove_owner

# ─── Config ───────────────────────────────────────────────────────────────────
IMAGE_PATH = os.environ.get(
    "ROULETTE_IMAGE",
    os.path.join(os.path.dirname(__file__), "roulette.png"),
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("roulette")

# ─── Roulette constants ───────────────────────────────────────────────────────
RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
MAX_SELECT = 6

# Sticker IDs (your list)
ROULETTE_STICKERS = [ "CAACAgQAAxkBAAIaAAFoor7iFYgU-aPtzN_GrSQcRFgrAgAC1BgAAkmhgFG_0u82E59m3DYE", # 00 
"CAACAgQAAyEFAASrImQNAAIBvWiLZDne0b_gDav_cu9Zoz_Wn8QAA9QYAAJJoYBRv9LvNhOfZtw2BA", # 0 
"CAACAgQAAyEFAASrImQNAAIBxWiLZNEh0p7950vmRhKNC3S3ZU25AAKoFgAC9OuBUThYKjFsHNUINgQ", # 1 
"CAACAgQAAyEFAASrImQNAAIBx2iLZOqAubPVdNGdZzvcnsXjTpqpAALVFgAChvR5UXXNtwbTRSMzNgQ", # 2 
"CAACAgQAAyEFAASrImQNAAIBzWiLZQ6zjkGiwJm-7gMR-5pTaDl7AAJJGAACzviBUTIdC1OxHKQaNgQ", # 3 
"CAACAgQAAyEFAASrImQNAAIBz2iLZSVhamntTktG1qeRTcyAamngAAJ8GAACDciAUYSN0sp7C2LnNgQ", # 4 
"CAACAgQAAyEFAASrImQNAAIB0WiLZT6zKhE_zIZeIN7b3S6tUzh8AALKFgACW3KBUQIpefveRTIKNgQ", # 5 
"CAACAgQAAyEFAASrImQNAAIB02iLZVAeRDcVkPbHf67K-6P9hMSkAALLGgACC62BUbKIJ7iU0rb4NgQ", # 6 
"CAACAgQAAyEFAASrImQNAAIB1WiLZWLCIx-z_rMuhRNLgPR1qW54AALVGAAClPyBUSUxwoUHdsn8NgQ", # 7 
"CAACAgQAAyEFAASrImQNAAIB12iLZXTKXalIWjkrGoCaVd1kdLwWAAKAFAACaVaBUUiaHozlFwAB0jYE", # 8 
"CAACAgQAAyEFAASrImQNAAIB2WiLZYebcuzYSQbvfQPnMdLARswWAALgFwAC88p5UUHH5NnJwBYPNgQ", # 9 
"CAACAgQAAyEFAASrImQNAAIB22iLZZmLTjEPN3kacYZtInsUCKZtAALyGAACucCAUZ6fXOAfAAEs9zYE", # 10 
"CAACAgQAAyEFAASrImQNAAIB3WiLZb-01H91oXUKEFcGpCv8nAupAALZEwACbN2BURqjRgAB0jLjWDYE", # 11 
"CAACAgQAAyEFAASrImQNAAIB4WiLZdWV8Mm3ERAAAUtDcsbOQB8F4gACVRgAAovngVFUjR-qYgq8LDYE", # 12 
"CAACAgQAAyEFAASrImQNAAIB8miLZi2XoFr2zDBIJmb7FqK_NWeNAAJNHQACZzSAUdecnnT052I6NgQ", # 13 
"CAACAgQAAyEFAASrImQNAAIB9GiLZkNMlJ-I8vVZ0hrPyeKG1IdTAAJDGQACpcN5URDm4Ifd0r06NgQ", # 14
"CAACAgQAAyEFAASrImQNAAIB92iLZlqc-BO3IIxiXkyXlKi0iZfBAAKtFgACUFaBUf0GoZ1742K-NgQ", # 15 
"CAACAgQAAyEFAASrImQNAAIB-2iLZmnlAfTNlsfSaexM1GASzMAbAAKvGwACRx95Ub2KbQXS25k_NgQ", # 16 
"CAACAgQAAyEFAASrImQNAAICAWiLZoVPqOAoPNEu8ciguHbhPth-AAIuGAACK5eBUdo-jXChdkRhNgQ", # 17 
"CAACAgQAAyEFAASrImQNAAICBGiLZpjAERL_jSk0_Knhenev_rEkAAJjGQACfHt4Uaxk_YBdcErDNgQ", # 18 
"CAACAgQAAyEFAASrImQNAAICBmiLZqsspVHNaTc4ENzdfqcJEPqmAAIpGQACsPCAUfSIqog8-IdgNgQ", # 19 
"CAACAgQAAyEFAASrImQNAAICDGiLZsPmYc3VwL5hWWfQr62cb10_AAJzGgACvs54UZK5KgfIrF_lNgQ", # 20 
"CAACAgQAAyEFAASrImQNAAICDmiLZtWGzKI2zY3wzLprkoAqc-KVAALGFwAC_V2AUXeSG0ZgWd5jNgQ", # 21 
"CAACAgQAAyEFAASrImQNAAICEGiLZuNlaO9D0c85DyutySD1u_qMAAMZAAITwoBRIlMrM9BBD0g2BA", # 22 
"CAACAgQAAyEFAASrImQNAAICEmiLZvojsOnJx8YE-yfuFiZmpe6cAAJMGAAC6d2BUXq6dfIzfhljNgQ", # 23
"CAACAgQAAyEFAASrImQNAAICFGiLZwjZ2PZBmj4YgAKLvUrmAkbNAALhGgACeS-AUdEviXb3bvCcNgQ", # 24
"CAACAgQAAyEFAASrImQNAAICFmiLZxey5PH6Qm_FuX_ar_n1Qr8DAALmFwACI96AUWwyQ3Omp9HTNgQ", # 25
"CAACAgQAAyEFAASrImQNAAICGWiLZygMUnBPnLmep_qtebbW-ucoAALNIAACfXmBUb6hDihoktivNgQ", # 26 
"CAACAgQAAyEFAASrImQNAAICHGiLZziBU-1FLh5G2ZwRDFoJXShpAAKgFwACMrSBUWqhExYnRXYCNgQ", # 27 
"CAACAgQAAyEFAASrImQNAAICHmiLZ0a5rK8mKDySuCZ5xWhG6R3XAALzFQACNO2BUVsOM4juGOTINgQ", # 28 
"CAACAgQAAyEFAASrImQNAAICIGiLZ1pVZYUGwoBvfOBIUySGC1_3AAJ6FwACAvZ4UXK88kRPGqWWNgQ", # 29 
"CAACAgQAAyEFAASrImQNAAICImiLZ2zFmnOl2hUGfKqGwmrWVFPAAAKsFQACoyyBUSIq6OlCBV8kNgQ", # 30 
"CAACAgQAAyEFAASrImQNAAICJGiLZ352bXF_C2aVFEgnO-dlGOJtAAIOGwACtbqAUQ1y_oj3ur3ENgQ", # 31 
"CAACAgQAAyEFAASrImQNAAICJmiLZ4u_-YlnmI26z9JRKtnREL1cAAJbFwACyad5UYWo5iH3DzX9NgQ", # 32 
"CAACAgQAAyEFAASHyrY2AAIIZGiLRIkLwf5ktSB3VkFL8pReOa9BAAKMGQACjcl4URhc62AjMUuNNgQ", # 33 
"CAACAgQAAyEFAASrImQNAAICKmiLZ-hPWbW7WDMTkhBmtZYy66oNAAJYFgAC-feBUSUjonJS-hFjNgQ", # 34 
"CAACAgQAAyEFAASrImQNAAICLGiLZ_PGUGYeKbdSWBr0uvv5TAirAAKSFgACwpOAUcdyb2uPc8PINgQ", # 35 
"CAACAgQAAyEFAASrImQNAAICLmiLaAABmtHjXzRZDz5Zy3dT5v8v0wACrBcAAtbQgVFt8Uw1gyn4MDYE", # 36 
]

# ─── Helpers ──────────────────────────────────────────────────────────────────
def pack(action: str, **kwargs) -> str:
    d = {"a": action}
    d.update(kwargs)
    s = json.dumps(d, separators=(",", ":"))
    if len(s) > 60:
        raise ValueError("Callback data too long")
    return s

def unpack(data: str) -> Dict:
    return json.loads(data)

def fmt_money(v: float) -> str:
    return f"${int(v)}" if float(v).is_integer() else f"${v:.2f}"

def user_mention(update: Update) -> str:
    u = update.effective_user
    if u.username:
        return f"@{u.username}"
    name = (u.first_name or "Player")
    return f'<a href="tg://user?id={u.id}">{html.escape(name)}</a>'

# ─── Session ──────────────────────────────────────────────────────────────────
@dataclass
class RoundState:
    bet_amount: float = 1.0
    selection_mode: str = "root"            # "root" or "grid"
    preset_group: Optional[str] = None      # e.g., "red", "even", "1-12"
    chosen_numbers: Set[str] = field(default_factory=set)
    message_id: Optional[int] = None

    def reset_numbers(self):
        self.chosen_numbers.clear()

SESSIONS: Dict[Tuple[int, int], RoundState] = {}

def session_for(update: Update) -> Tuple[Tuple[int, int], RoundState]:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    key = (chat_id, user_id)
    st = SESSIONS.get(key)
    if not st:
        st = RoundState()
        SESSIONS[key] = st
    return key, st

# ─── Keyboards ────────────────────────────────────────────────────────────────
def teaser_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Play", callback_data=pack("play"))]])

def preset_label(st: RoundState, code: str, title: str) -> str:
    return f"✅ {title}" if st.preset_group == code else title

def root_kb(st: RoundState) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("✅ Start", callback_data=pack("spin"))],
        [InlineKeyboardButton("Bet On Number", callback_data=pack("to_numbers"))],
        [
            InlineKeyboardButton(preset_label(st, "1-12", "1 to 12"), callback_data=pack("preset", g="1-12")),
            InlineKeyboardButton(preset_label(st, "13-24", "13 to 24"), callback_data=pack("preset", g="13-24")),
            InlineKeyboardButton(preset_label(st, "25-36", "25 to 36"), callback_data=pack("preset", g="25-36")),
        ],
        [
            InlineKeyboardButton(preset_label(st, "1-18", "1 to 18"), callback_data=pack("preset", g="1-18")),
            InlineKeyboardButton(preset_label(st, "19-36", "19 to 36"), callback_data=pack("preset", g="19-36")),
        ],
        [
            InlineKeyboardButton(preset_label(st, "even", "Even"), callback_data=pack("preset", g="even")),
            InlineKeyboardButton(preset_label(st, "odd", "Odd"), callback_data=pack("preset", g="odd")),
        ],
        [
            InlineKeyboardButton(preset_label(st, "red", "🔴"), callback_data=pack("preset", g="red")),
            InlineKeyboardButton(preset_label(st, "black", "⚫"), callback_data=pack("preset", g="black")),
        ],
    ]
    return InlineKeyboardMarkup(rows)

# ─── Images & captions ────────────────────────────────────────────────────────
def convert_image_to_png(image_path: str) -> BytesIO:
    img = Image.open(image_path)
    img.thumbnail((1024, 1024))
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def compute_multiplier(st: RoundState) -> float:
    if not st.chosen_numbers:
        return 2.0
    table = {1: 36.0, 2: 18.0, 3: 12.0, 4: 9.0, 5: 7.0, 6: 6.0}
    return table.get(min(len(st.chosen_numbers), 6), 6.0)

def build_caption(st: RoundState, balance: float) -> str:
    mult = compute_multiplier(st)
    picks = ", ".join(sorted(st.chosen_numbers, key=lambda x: (len(x), x))) or "—"
    preset = st.preset_group or "—"
    return (
        "🎰 <b>Roulette</b>\n\n"
        f"<b>Bet:</b> {fmt_money(st.bet_amount)}\n"
        f"<b>Balance:</b> {fmt_money(balance)}\n"
        f"<b>Multiplier:</b> {mult:.2f}x\n"
        f"<b>Preset:</b> {preset}\n\n"
        "Place your bet:"
        f"\nSelections: {picks}"
    )


def result_caption(st: RoundState, balance: float, won_amt: float) -> str:
    status = f"🎉 You won {fmt_money(won_amt)}" if won_amt > 0 else "You lost"
    mult = compute_multiplier(st)
    return (
        "🎰 <b>Roulette</b>\n\n"
        f"<b>Bet:</b> {fmt_money(st.bet_amount)}\n"
        f"<b>Balance:</b> {fmt_money(balance)}\n"
        f"<b>Multiplier:</b> {mult:.2f}x\n\n"
        f"{status}"
    )

# ─── Spin helpers & settle ────────────────────────────────────────────────────
def random_sticker_id() -> str:
    return random.choice(ROULETTE_STICKERS)

def spin_number() -> str:
    pool = [str(i) for i in range(37)] + ["00"]
    return random.choice(pool)

def matches_preset(num_int: int, preset: str) -> bool:
    if preset == "1-12":  return 1 <= num_int <= 12
    if preset == "13-24": return 13 <= num_int <= 24
    if preset == "25-36": return 25 <= num_int <= 36
    if preset == "1-18":  return 1 <= num_int <= 18
    if preset == "19-36": return 19 <= num_int <= 36
    if preset == "even":  return num_int != 0 and num_int % 2 == 0
    if preset == "odd":   return num_int % 2 == 1
    if preset == "red":   return num_int in RED
    if preset == "black": return num_int in BLACK
    return False

async def settle_round(update: Update, context: ContextTypes.DEFAULT_TYPE, st: RoundState) -> None:
    user_id = update.effective_user.id
    chat = update.effective_chat

    balance = get_balance(user_id)
    bet = max(0.01, float(st.bet_amount))

    # ✅ Prevent insufficient balance exploit
    if balance < bet:
        await chat.send_message("❌ Not enough balance!")
        return

    rolled = spin_number()
    rolled_int = 0 if rolled in ("0", "00") else int(rolled)

    win = False
    payout_multiplier = 0.0

    # ─── Determine Win ─────────────────────
    if st.chosen_numbers:
        if rolled in st.chosen_numbers:
            win = True
            payout_multiplier = compute_multiplier(st)

    elif st.preset_group:
        if rolled not in ("0", "00") and matches_preset(rolled_int, st.preset_group):
            win = True
            payout_multiplier = 2.0

    won_amt = bet * payout_multiplier if win else 0.0

# ─── Update DB ─────────────────────────

# subtract bet
    update_balance(user_id, -bet)

# add winnings if win
    if won_amt > 0:
        update_balance(user_id, won_amt)
        adjust_house_balance(-won_amt, user_id=user_id, reason="roulette_player_win", game_ref="roulette")
    else:
        adjust_house_balance(bet, user_id=user_id, reason="roulette_player_loss", game_ref="roulette")

# track wager
    add_wager(user_id, bet)

# update stats (match your function signature)
    update_stats(user_id, bet)

    new_balance = get_balance(user_id)

    # ─── Build result UI ───────────────────
    caption = result_caption(st, new_balance, won_amt)
    kb = root_kb(st)

    # ─── EDIT SAME MESSAGE ─────────────────
    try:
        if st.message_id:
            await chat.edit_message_caption(
                message_id=st.message_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
            )
        else:
            raise Exception("No stored message_id")

    except Exception:
        # fallback safety
        msg = await chat.send_message(
            caption,
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )
        st.message_id = msg.message_id

    # ─── Reset round state ─────────────────
    st.preset_group = None
    st.reset_numbers()

# ─── Commands ─────────────────────────────────────────────────────────────────
async def roulette_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _, st = session_for(update)
    user_id = update.effective_user.id
    balance = get_balance(user_id)

    # ─── BET PARSING ───────────────────────
    if context.args:
        a = context.args[0].lower()
        if a == "half":
            bet = max(0.01, round(balance / 2, 2))
        elif a == "all":
            bet = max(0.01, round(balance, 2))
        else:
            try:
                bet = float(a)
            except ValueError:
                bet = 1.0

        st.bet_amount = max(0.01, round(bet, 2))
        st.selection_mode = "root"
        st.preset_group = None
        st.reset_numbers()

        # 🔥 SHOW ROULETTE UI IMMEDIATELY
        caption = build_caption(st, balance)

        if os.path.exists(IMAGE_PATH):
            img = convert_image_to_png(IMAGE_PATH)
            msg = await update.effective_chat.send_photo(
                photo=img,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=root_kb(st),
            )
            set_owner(msg.chat_id, msg.message_id, update.effective_user.id)
        else:
            msg = await update.effective_chat.send_message(
                caption,
                parse_mode=ParseMode.HTML,
                reply_markup=root_kb(st),
            )
            set_owner(msg.chat_id, msg.message_id, update.effective_user.id)

        st.message_id = msg.message_id
        return

    # ─── NO AMOUNT → SHOW TEASER ───────────
    st.bet_amount = 1.0
    st.selection_mode = "root"
    st.preset_group = None
    st.reset_numbers()

    mention = user_mention(update)
    text = (
        f"{mention}\n\n"
        "<b>Roulette</b>\n\n"
        "To quickly start the game, type <code>/roul &lt;bet&gt;</code>\n\n"
        "<b>Examples:</b>\n"
        "/roul 10 - bet $10\n"
        "/roul half - bet half of the balance\n"
        "/roul all - go all-in"
    )

    msg = await update.effective_chat.send_message(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=teaser_kb(),
    )
    set_owner(msg.chat_id, msg.message_id, update.effective_user.id)
    st.message_id = msg.message_id


async def edit_message(msg, text, reply_markup=None):
    if msg.photo:
        await msg.edit_caption(
            caption=text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )
    else:
        await msg.edit_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )


# ─── Callback router ──────────────────────────────────────────────────────────
async def cb_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    msg = q.message

    try:
        data = unpack(q.data)
    except Exception:
        await q.answer("Invalid button.")
        return

    if not await check_owner(q, "❌ This is not your game."):
        return

    action = data.get("a")
    _, st = session_for(update)

    # helper: edit caption OR text safely
    async def safe_edit(text, reply_markup=None):
        if msg.photo:
            await msg.edit_caption(
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
        else:
            await msg.edit_text(
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )

    if action == "noop":
        await q.answer()
        return

    if action == "play":
        await q.answer()
        await safe_edit(
            "🎰 <b>Roulette</b>\n\nPlace your bet:",
            root_kb(st),
        )
        return

    if action == "spin":
        await q.answer("Spinning…")
        try:
            await q.message.chat.send_sticker(random_sticker_id())
        except Exception:
            pass
        await settle_round(update, context, st)
        return

    if action == "preset":
        g = data.get("g")
        st.preset_group = None if st.preset_group == g else g
        st.selection_mode = "root"

        await q.answer(text=f"Selected: {st.preset_group or 'none'}")

        await safe_edit(
            build_caption(st, get_balance(update.effective_user.id)),
            root_kb(st),
        )
        return

    if action == "to_numbers":
        st.selection_mode = "grid"
        st.reset_numbers()
        await q.answer()

        await safe_edit(
            build_caption(st, get_balance(update.effective_user.id)),
            InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data=pack("back_root"))]
            ]),
        )
        return

    if action == "pick":
        n = data.get("n")

        if st.preset_group is not None and not st.chosen_numbers:
            st.preset_group = None
            st.reset_numbers()

        if n in st.chosen_numbers:
            st.chosen_numbers.remove(n)
        else:
            if len(st.chosen_numbers) >= MAX_SELECT:
                await q.answer(f"Max {MAX_SELECT} numbers", show_alert=True)
                return
            st.chosen_numbers.add(n)

        await q.answer()
        return

    if action == "back_root":
        st.selection_mode = "root"
        await q.answer()

        await safe_edit(
            build_caption(st, get_balance(update.effective_user.id)),
            root_kb(st),
        )
        return

    await q.answer()
