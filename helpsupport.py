# helpsupport.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# /news command
async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_menu")]
    ]
    await update.message.reply_text(
        "News and updates are posted here: @DemoUpdates",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_menu")]
    ]
    text = (
        "❓ <b>Help</b>\n\n"
        "1. Make sure you have a balance. You can deposit by entering the /balance command.\n"
        "2. Go to one of our groups in @DemoDirectory\n"
        "3. Enter the /dice command and you are ready!\n\n"
        "🎮 <b>What games can I play?</b>\n"
        "• 🎲 Dice — /dice\n"
        "• 🎳 Bowling — /bowl\n"
        "• 🎯 Darts — /darts\n"
        "• 🏈 Football — /ball\n"
        "• 🏀 Basketball — /bask\n"
        "• 🪙 Coinflip — /coin\n"
        "• 🎰 Slot machine — /slots\n"
        "• 🎡 Roulette — /roulette\n"
        "• 🤖 Dice Prediction — /predict\n"
        "• 🃏 Blackjack — /blackjack\n"
        "• 💣 Mines — /mines\n"
        "• 📌 Plinko — /plinko\n"
        "• 🐒 Monkey Tower — /tower\n"
        "• 🚗 Crossy Road — /crossyroad\n"
        "• 🎡 Wheel (NEW!) — /wheel"
    )
    await update.message.reply_html(text, reply_markup=InlineKeyboardMarkup(keyboard))

# Back button handler
async def back_to_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.delete()
