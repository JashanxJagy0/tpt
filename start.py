# start.py
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
from models import get_balance
from bonus import bonus_menu  # existing bonus menu

# ===== Helper: Get LTC/USD Rate =====
def get_ltc_usd_rate():
    """Fetch current LTC price in USD (CoinGecko API)."""
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "litecoin", "vs_currencies": "usd"},
            timeout=5
        )
        data = resp.json()
        return float(data["litecoin"]["usd"])
    except Exception:
        return 0  # fallback if API fails

# ===== Main Menu Sender =====
async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, balance=None):
    user = update.effective_user
    if balance is None:
        balance = get_balance(user.id)

    # LTC conversion
    ltc_rate = get_ltc_usd_rate()
    ltc_value = (balance / ltc_rate) if ltc_rate > 0 else 0

    menu_text = "🏠 <b>Menu</b>\n\n"
    menu_text += f"Your balance: <b>${balance:,.2f}</b> ({ltc_value:,.5f} LTC)\n\n"
    menu_text += "Choose the action:"

    keyboard = [
        [InlineKeyboardButton("🎮 Play", callback_data="play")],
        [
            InlineKeyboardButton("💳 Deposit", callback_data="deposit"),
            InlineKeyboardButton("🏛 Withdraw", callback_data="withdraw")
        ],
        [
            InlineKeyboardButton("🎁 Bonuses", callback_data="bonuses"),
            InlineKeyboardButton("📚 More Content", callback_data="more_content")
        ],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
    ]

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=menu_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=menu_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ===== /start Command =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    balance = get_balance(user.id)

    # Welcome text
    welcome_text = (
        "📣 <b>Greetings!</b>\n\n"
        "Dice Gamble is the most popular bot for live games with other people!\n"
        "Our main group with an active community is @MaxGambleChat\n\n"
        "📜 <b>How To Start?</b>\n"
        "1. Make sure you have a balance. You can deposit by entering the <code>/balance</code> command.\n"
        "2. Go to one of our groups in @MaxDirectory directory\n"
        "3. Enter the <code>/dice</code> command and you are ready!\n\n"
        "🎮 <b>What games can I play?</b>\n"
        "🎲 Dice - /dice\n"
        "🎳 Bowling - /bowl\n"
        "🎯 Darts - /darts\n"
        "⚽ Football - /ball\n"
        "🏀 Basketball - /bask\n"
        "🪙 Coinflip - /coin\n"
        "🎰 Slot machine - /slots\n"
        "🎲 Dice Prediction - /predict\n"
        "🃏 Blackjack - /blackjack\n"
        "💣 Mines - /mines\n"
        "🎯 Plinko - /plinko\n"
        "🐒 Monkey Tower - /tower\n"
        "🎡 Roulette - /roulette\n"
        "🦘 Crossy Road (NEW!) - /crossyroad\n"
        "• More is coming! - /news\n\n"
        "Enjoy the games! 🍀"
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=welcome_text,
        parse_mode="HTML"
    )

    # Send menu after welcome
    await send_main_menu(update, context, balance)

# ===== Play Menu =====
async def play_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    text = "🎮 <b>Game Menu</b>\nChoose the game you want to play:"

    kb = [
        [InlineKeyboardButton("🎲 Dice", callback_data="game_dice")],
        [InlineKeyboardButton("🎰 Slots", callback_data="game_slots")],
        [InlineKeyboardButton("🎲 Dice Prediction", callback_data="game_predict")],
        [InlineKeyboardButton("🐒 Monkey Tower", callback_data="game_tower")],
        [InlineKeyboardButton("🏛 Roulette", callback_data="game_roulette")],
        [InlineKeyboardButton("🎡 Wheel", callback_data="game_wheel")],
        [InlineKeyboardButton("🃏 Blackjack", callback_data="game_blackjack")],
        [InlineKeyboardButton("💣 Mines", web_app=WebAppInfo(url="https://yourdomain.com/mines.html"))],
        [InlineKeyboardButton("📍 Plinko", callback_data="game_plinko")],
        [InlineKeyboardButton("🦘 Crossy Road", callback_data="game_crossy")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]
    ]
    await q.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

# ===== More Content Menu =====
async def more_content_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    text = "📚 <b>More Content</b>"
    kb = [
        [
            InlineKeyboardButton("📊 Your Statistics", callback_data="stats"),
            InlineKeyboardButton("📅 Matches History", callback_data="matches_history")
        ],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")],
        [InlineKeyboardButton("🎟 Raffle", callback_data="raffle")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]
    ]
    await q.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

# ===== Deposit Menu =====
async def deposit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    text = "💳 <b>Deposit</b>\nChoose your preferred deposit method:"
    kb = [
        [InlineKeyboardButton("Litecoin", callback_data="dep_ltc")],
        [InlineKeyboardButton("Bitcoin", callback_data="dep_btc"),
         InlineKeyboardButton("Ethereum", callback_data="dep_eth")],
        [InlineKeyboardButton("Solana", callback_data="dep_solana"),
         InlineKeyboardButton("TON", callback_data="dep_ton")],
        [InlineKeyboardButton("USDT ERC-20", callback_data="dep_usdt"),
         InlineKeyboardButton("USDC ERC-20", callback_data="dep_usdc")],
        [InlineKeyboardButton("Monero", callback_data="dep_xmr"),
         InlineKeyboardButton("Tron", callback_data="dep_trx")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]
    ]
    await q.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

# ===== Withdraw Menu =====
async def withdraw_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    text = (
        "🐒 <b>Litecoin withdrawal</b>\n\n"
        "Note:\n"
        "• Minimum withdrawal amount: 0.002 LTC ≈ $0.26 USD\n"
        "• Network: Litecoin\n"
        "• Network fee: 1.5%\n\n"
        "Please send your Litecoin address"
    )
    kb = [[InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]]
    await q.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

# ===== Back Button =====p
async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_main_menu(update, context)
