import os
import asyncio
from flask import Flask
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    CallbackQueryHandler
)

# Load environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")
ADMIN_IDS = [5925363190]  # You are the admin

# MongoDB setup
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["battlebot"]
users_col = db["users"]
admins_col = db["admins"]

# Flask app for health checks
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

# Helper functions
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def get_user(user_id):
    return users_col.find_one({"user_id": user_id}) or {}

def update_user(user_id, username):
    users_col.update_one(
        {"user_id": user_id},
        {"$set": {"username": username}, "$setOnInsert": {"coins": 100}},
        upsert=True
    )

def adjust_coins(user_id, amount):
    users_col.update_one({"user_id": user_id}, {"$inc": {"coins": amount}})

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    update_user(user.id, user.username)
    await update.message.reply_text(f"Welcome, {user.first_name}! You've been registered.")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    coins = user.get("coins", 0)
    await update.message.reply_text(f"You have {coins} coins.")

async def battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /battle <@opponent> <amount>")
        return

    opponent_username = context.args[0].lstrip("@")
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Invalid coin amount.")
        return

    challenger = update.effective_user
    update_user(challenger.id, challenger.username)
    challenger_data = get_user(challenger.id)

    if challenger_data.get("coins", 0) < amount:
        await update.message.reply_text("You don't have enough coins.")
        return

    # Ask admin to start battle
    keyboard = [
        [InlineKeyboardButton("Start Battle", callback_data=f"startbattle_{challenger.id}_{opponent_username}_{amount}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Admin, please approve this battle between {challenger.mention_html()} and @{opponent_username} for {amount} coins.",
                                    parse_mode="HTML", reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("Only an admin can start the battle.")
        return

    if query.data.startswith("startbattle_"):
        _, challenger_id, opponent_username, amount = query.data.split("_")
        challenger_id = int(challenger_id)
        amount = int(amount)

        opponent = users_col.find_one({"username": opponent_username})
        if not opponent or opponent.get("coins", 0) < amount:
            await query.edit_message_text(f"Opponent @{opponent_username} doesn't have enough coins.")
            return

        # Simple win logic: admin chooses
        keyboard = [
            [
                InlineKeyboardButton("Challenger Wins", callback_data=f"win_{challenger_id}_{opponent['_id']}_{amount}"),
                InlineKeyboardButton("Opponent Wins", callback_data=f"win_{opponent['_id']}_{challenger_id}_{amount}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Battle started! Choose the winner.", reply_markup=reply_markup)

    elif query.data.startswith("win_"):
        winner_id, loser_id, amount = map(int, query.data.split("_")[1:])
        adjust_coins(winner_id, int(amount))
        adjust_coins(loser_id, -int(amount))
        await query.edit_message_text(f"Winner: [{winner_id}]\nLoser: [{loser_id}]\nCoins updated.")

# Telegram Bot Setup
async def run_bot():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("balance", balance))
    app_bot.add_handler(CommandHandler("battle", battle))
    app_bot.add_handler(CallbackQueryHandler(handle_callback))

    await app_bot.initialize()
    await app_bot.start()
    print("Bot started")
    await app_bot.updater.start_polling()
    await app_bot.updater.idle()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot())
    app.run(host="0.0.0.0", port=8000)
