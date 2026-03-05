# levels.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

LEVELS_DATA = {
    "Bronze": [
        ("Bronze I", 100, 1),
        ("Bronze II", 500, 2),
        ("Bronze III", 1000, 2.5),
        ("Bronze IV", 2500, 7.5),
        ("Bronze V", 5000, 12.5),
    ],
    "Silver": [
        ("Silver I", 10000, 25),
        ("Silver II", 15200, 26),
        ("Silver III", 20500, 26.5),
        ("Silver IV", 26000, 27.5),
        ("Silver V", 32000, 30),
    ],
    "Gold": [
        ("Gold I", 39000, 35),
        ("Gold II", 48000, 45),
        ("Gold III", 58000, 50),
        ("Gold IV", 69000, 55),
        ("Gold V", 81000, 60),
    ],
    "Platinum": [
        ("Platinum I", 94000, 65),
        ("Platinum II", 107500, 67.5),
        ("Platinum III", 122000, 72.5),
        ("Platinum IV", 138000, 80),
        ("Platinum V", 155000, 85),
    ],
    "Diamond": [
        ("Diamond I", 173000, 90),
        ("Diamond II", 192000, 95),
        ("Diamond III", 211500, 97.5),
        ("Diamond IV", 232000, 102),
        ("Diamond V", 253000, 105),
    ],
    "Emerald": [
        ("Emerald I", 275000, 110),
        ("Emerald II", 298000, 115),
        ("Emerald III", 322000, 120),
        ("Emerald IV", 347000, 125),
        ("Emerald V", 373000, 130),
    ],
    "Ruby": [
        ("Ruby I", 400000, 135),
        ("Ruby II", 428000, 140),
        ("Ruby III", 457000, 145),
        ("Ruby IV", 487000, 150),
        ("Ruby V", 518000, 155),
    ],
    "Sapphire": [
        ("Sapphire I", 550000, 160),
        ("Sapphire II", 583000, 165),
        ("Sapphire III", 617000, 170),
        ("Sapphire IV", 652000, 175),
        ("Sapphire V", 688000, 180),
    ],
    "Amethyst": [
        ("Amethyst I", 725000, 185),
        ("Amethyst II", 763000, 190),
        ("Amethyst III", 802000, 195),
        ("Amethyst IV", 842000, 200),
        ("Amethyst V", 883000, 205),
    ],
    "Obsidian": [
        ("Obsidian I", 925000, 210),
        ("Obsidian II", 968000, 215),
        ("Obsidian III", 1012000, 220),
        ("Obsidian IV", 1058000, 230),
        ("Obsidian V", 1107000, 245),
    ],
    "Mythic": [
        ("Mythic I", 1159000, 260),
        ("Mythic II", 1213000, 270),
        ("Mythic III", 1270000, 285),
        ("Mythic IV", 1330000, 300),
        ("Mythic V", 1393000, 315),
    ],
    "Legendary": [
        ("Legendary I", 1458000, 325),
        ("Legendary II", 1525000, 335),
        ("Legendary III", 1595000, 350),
        ("Legendary IV", 1668000, 365),
        ("Legendary V", 1743000, 375),
    ],
    "Ethereal": [
        ("Ethereal I", 1850000, 535),
        ("Ethereal II", 2000000, 750),
        ("Ethereal III", 2175000, 875),
        ("Ethereal IV", 2400000, 1125),
        ("Ethereal V", 2650000, 1250),
    ],
    "Top Tier": [
        ("Top Tier", 3000000, 1750),
    ],
}

LEVEL_ORDER = [
    "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Emerald",
    "Ruby", "Sapphire", "Amethyst", "Obsidian", "Mythic",
    "Legendary", "Ethereal", "Top Tier"
]

LEVEL_NAVIGATION = {
    "Bronze": {"next": "Silver", "prev": None},
    "Silver": {"next": "Gold", "prev": "Bronze"},
    "Gold": {"next": "Platinum", "prev": "Silver"},
    "Platinum": {"next": "Diamond", "prev": "Gold"},
    "Diamond": {"next": "Emerald", "prev": "Platinum"},
    "Emerald": {"next": "Ruby", "prev": "Diamond"},
    "Ruby": {"next": "Sapphire", "prev": "Emerald"},
    "Sapphire": {"next": "Amethyst", "prev": "Ruby"},
    "Amethyst": {"next": "Obsidian", "prev": "Sapphire"},
    "Obsidian": {"next": "Mythic", "prev": "Amethyst"},
    "Mythic": {"next": "Legendary", "prev": "Obsidian"},
    "Legendary": {"next": "Ethereal", "prev": "Mythic"},
    "Ethereal": {"next": "Top Tier", "prev": "Legendary"},
    "Top Tier": {"next": None, "prev": "Ethereal"},
}

async def levels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /levels [TierName]."""
    tier = context.args[0] if context.args else "Bronze"
    if tier not in LEVEL_ORDER:
        tier = "Bronze"
    await _send_level_page(update, tier, edit=False)

async def levels_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback handler for 'levels_*' buttons."""
    q = update.callback_query
    await q.answer()
    data = q.data  # "levels_Silver" or "levels_back"

    if data == "levels_back":
        return await q.message.delete()

    tier = data.split("_", 1)[1]
    if tier not in LEVEL_ORDER:
        tier = "Bronze"
    await _send_level_page(update, tier, edit=True)

async def _send_level_page(update: Update, tier: str, edit: bool):
    """Render one page of levels with bolded wager & bonus."""
    levels = LEVELS_DATA[tier]
    nav    = LEVEL_NAVIGATION[tier]
    prev_t = nav["prev"]
    next_t = nav["next"]

    # Build message body
    lines = [f"🪜 <b>{tier} Tiers</b>\n"]
    for lvl_name, wager, bonus in levels:
        lines.append(
            f"🏅 <b>{lvl_name}</b>\n"
            f"Wager to Reach: <b>${wager:,}</b>\n"
            f"Level Up Bonus: <b>${bonus}</b>\n"
        )
    text = "\n".join(lines).strip()

    # Build keyboard
    kb = []
    nav_row = []
    if prev_t:
        nav_row.append(InlineKeyboardButton(f"⬅️ {prev_t}", callback_data=f"levels_{prev_t}"))
    if next_t:
        nav_row.append(InlineKeyboardButton(f"{next_t} ➡️", callback_data=f"levels_{next_t}"))
    if nav_row:
        kb.append(nav_row)
    kb.append([InlineKeyboardButton("⬅️ Back", callback_data="levels_back")])
    markup = InlineKeyboardMarkup(kb)

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup)
