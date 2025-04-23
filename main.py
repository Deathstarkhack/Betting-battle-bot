import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, CallbackQueryHandler
import pymongo
import os

# Bot token and Mongo URI
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

# Connect to MongoDB
client = pymongo.MongoClient(MONGO_URI)
db = client['battle_bot']
users = db['users']

# Set your Telegram ID as admin
ADMINS = [5925363190]

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Helper to ensure user exists
def ensure_user(user_id, username):
    if users.find_one({"_id": user_id}) is None:
        users.insert_one({"_id": user_id, "username": username, "coins": 100})

# Start command
async def start(update: Update, context: CallbackContext.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username)
    await update.message.reply_text("Welcome to the Battle Bot!")

# /battle command
async def battle(update: Update, context: CallbackContext.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username)

    if not context.args:
        return await update.message.reply_text("Usage: /battle <coins>")

    try:
        amount = int(context.args[0])
    except ValueError:
        return await update.message.reply_text("Please provide a valid number.")

    user_data = users.find_one({"_id": user.id})
    if user_data["coins"] < amount:
        return await update.message.reply_text("Not enough coins!")

    context.user_data["battle_amount"] = amount
    context.user_data["challenger_id"] = user.id
    context.user_data["challenger_name"] = user.username

    keyboard = [
        [InlineKeyboardButton("Start Battle", callback_data="start_battle")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"User @{user.username} wants to battle with {amount} coins.\nWaiting for admin approval...",
        reply_markup=reply_markup
    )

# Admin button handlers
async def button_handler(update: Update, context: CallbackContext.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if user_id not in ADMINS:
        return await query.edit_message_text("Only admins can start battles.")

    if query.data == "start_battle":
        challenger = context.user_data.get("challenger_name", "Unknown")
        amount = context.user_data.get("battle_amount", 0)

        keyboard = [
            [InlineKeyboardButton("Winner: Challenger", callback_data="winner_challenger")],
            [InlineKeyboardButton("Draw", callback_data="draw")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"Battle started between @{challenger}!\nAmount: {amount} coins.\nChoose winner:",
            reply_markup=reply_markup
        )

    elif query.data == "winner_challenger":
        challenger_id = context.user_data.get("challenger_id")
        amount = context.user_data.get("battle_amount", 0)
        users.update_one({"_id": challenger_id}, {"$inc": {"coins": amount}})
        await query.edit_message_text("Battle ended. Winner is Challenger. Coins rewarded!")

    elif query.data == "draw":
        await query.edit_message_text("Battle ended in a draw. No coins changed.")

# Entry point
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("battle", battle))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling()
