import logging
import asyncio
from flask import Flask
from threading import Thread
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# MongoDB Setup
client = MongoClient("mongodb+srv://criminalboyz10:l6RLBnBtohoyjPgh@cluster0.d9ifbhj.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client["battlebot"]
users = db["users"]
admins = db["admins"]

# Add yourself as admin
if not admins.find_one({"user_id": 5925363190}):
    admins.insert_one({"user_id": 5925363190})

def is_admin(user_id):
    return admins.find_one({"user_id": user_id}) is not None

def get_or_create_user(user_id, username):
    user = users.find_one({"user_id": user_id})
    if not user:
        user = {"user_id": user_id, "username": username, "coins": 100}
        users.insert_one(user)
    return user

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id, user.username)
    await update.message.reply_text("Welcome to BattleBot! Use /battle <amount> @opponent to start.")

async def battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    if len(args) != 2 or not args[0].isdigit():
        await update.message.reply_text("Usage: /battle <amount> @opponent")
        return

    amount = int(args[0])
    if not update.message.entities:
        return await update.message.reply_text("Tag an opponent using @username.")

    mentioned_user = update.message.parse_entities().get("mention")
    if not mentioned_user:
        return await update.message.reply_text("Please mention a valid opponent.")

    initiator = get_or_create_user(user.id, user.username)
    opponent_username = args[1].replace("@", "")
    opponent = users.find_one({"username": opponent_username})
    if not opponent:
        return await update.message.reply_text("Opponent is not registered. Ask them to use /start first.")

    if initiator["coins"] < amount or opponent["coins"] < amount:
        return await update.message.reply_text("Both players must have enough coins.")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Start Battle", callback_data=f"start_{user.id}_{opponent['user_id']}_{amount}")],
    ])

    await update.message.reply_text(
        f"Battle Request!\n{user.mention_html()} vs @{opponent_username}\nStake: {amount} coins",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("start_"):
        parts = data.split("_")
        initiator_id = int(parts[1])
        opponent_id = int(parts[2])
        amount = int(parts[3])

        if not is_admin(query.from_user.id):
            return await query.edit_message_text("Only admins can start the battle.")

        winner_id = initiator_id  # For now, set initiator as winner. Random logic can be added.

        loser_id = opponent_id if winner_id == initiator_id else initiator_id
        users.update_one({"user_id": winner_id}, {"$inc": {"coins": amount}})
        users.update_one({"user_id": loser_id}, {"$inc": {"coins": -amount}})

        winner = users.find_one({"user_id": winner_id})
        loser = users.find_one({"user_id": loser_id})

        await query.edit_message_text(
            f"Battle Result:\nWinner: @{winner['username']} (+{amount})\nLoser: @{loser['username']} (-{amount})"
        )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_users = users.find().sort("coins", -1).limit(5)
    msg = "🏆 Leaderboard:\n"
    for i, u in enumerate(top_users, start=1):
        msg += f"{i}. @{u['username']} - {u['coins']} coins\n"
    await update.message.reply_text(msg)

# Flask server for Koyeb health check
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=8000)

async def run_bot():
    bot_app = ApplicationBuilder().token("YOUR_BOT_TOKEN_HERE").build()

    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("battle", battle))
    bot_app.add_handler(CommandHandler("leaderboard", leaderboard))
    bot_app.add_handler(CallbackQueryHandler(handle_callback))

    await bot_app.run_polling()

if __name__ == "__main__":
    Thread(target=run_flask).start()
    asyncio.run(run_bot())
