import os
import asyncio
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from pymongo import MongoClient

# --- Setup ---
TOKEN = os.getenv("BOT_TOKEN", "your-telegram-bot-token")
MONGO_URI = os.getenv("MONGO_URI", "your-mongodb-uri")

client = MongoClient(MONGO_URI)
db = client["battle_bot"]
users = db["users"]
admin_data = db["admins"]

app = Flask(__name__)

# --- Utility functions ---

def is_admin(user_id):
    return admin_data.find_one({"user_id": user_id}) is not None

def get_or_create_user(user_id, username):
    user = users.find_one({"user_id": user_id})
    if not user:
        users.insert_one({"user_id": user_id, "username": username, "coins": 100})
    return users.find_one({"user_id": user_id})

def update_coins(user_id, amount):
    users.update_one({"user_id": user_id}, {"$inc": {"coins": amount}})

def get_leaderboard():
    top_users = users.find().sort("coins", -1).limit(10)
    return "\n".join([f"{u['username']}: {u['coins']} coins" for u in top_users])

# --- Bot commands ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id, user.username)
    await update.message.reply_text("Welcome to the Battle Bot!")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_create_user(update.effective_user.id, update.effective_user.username)
    await update.message.reply_text(f"You have {user['coins']} coins.")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_leaderboard()
    await update.message.reply_text(f"🏆 Leaderboard 🏆\n{text}")

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("Only admins can use this command.")
    
    if not update.message.reply_to_message:
        return await update.message.reply_text("Reply to the user you want to make admin.")
    
    admin_data.insert_one({"user_id": update.message.reply_to_message.from_user.id})
    await update.message.reply_text("User has been added as an admin.")

async def add_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("Only admins can use this command.")
    
    if len(context.args) != 1 or not context.args[0].isdigit():
        return await update.message.reply_text("Usage: /addcoins <amount>")
    
    amount = int(context.args[0])
    if not update.message.reply_to_message:
        return await update.message.reply_text("Reply to the user to add coins.")
    
    update_coins(update.message.reply_to_message.from_user.id, amount)
    await update.message.reply_text("Coins added.")

battle_requests = {}

async def battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user1 = update.effective_user
    if len(context.args) != 2:
        return await update.message.reply_text("Usage: /battle <amount> @opponent")

    try:
        amount = int(context.args[0])
    except ValueError:
        return await update.message.reply_text("Invalid coin amount.")

    if not update.message.entities:
        return await update.message.reply_text("Mention an opponent using @username.")

    opponent = None
    for entity in update.message.entities:
        if entity.type == "mention":
            mention = update.message.text[entity.offset:entity.offset + entity.length]
            opponent = mention.replace("@", "")

    if not opponent:
        return await update.message.reply_text("Opponent not found.")

    user1_data = get_or_create_user(user1.id, user1.username)
    opponent_data = users.find_one({"username": opponent})

    if not opponent_data:
        return await update.message.reply_text("Opponent not registered.")

    if user1_data["coins"] < amount or opponent_data["coins"] < amount:
        return await update.message.reply_text("Both players must have enough coins.")

    battle_id = f"{user1.id}_{opponent_data['user_id']}_{amount}"
    battle_requests[battle_id] = (user1_data["user_id"], opponent_data["user_id"], amount)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Start Battle", callback_data=f"start_{battle_id}")]
    ])
    await update.message.reply_text(
        f"⚔️ {user1.username} vs {opponent_data['username']} for {amount} coins each!",
        reply_markup=keyboard
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("start_"):
        battle_id = data.replace("start_", "")
        if not is_admin(query.from_user.id):
            return await query.edit_message_text("Only admins can start battles.")

        if battle_id not in battle_requests:
            return await query.edit_message_text("Battle request not found.")

        user1_id, user2_id, amount = battle_requests.pop(battle_id)
        winner = user1_id if os.urandom(1)[0] % 2 == 0 else user2_id
        loser = user2_id if winner == user1_id else user1_id

        update_coins(winner, amount)
        update_coins(loser, -amount)

        user1 = users.find_one({"user_id": user1_id})
        user2 = users.find_one({"user_id": user2_id})
        winner_user = users.find_one({"user_id": winner})

        await query.edit_message_text(
            f"⚔️ {user1['username']} vs {user2['username']} ⚔️\n"
            f"🏆 Winner: {winner_user['username']} (+{amount} coins)"
        )

# --- Web server for Koyeb ---
@app.route("/")
def home():
    return "Bot is running!"

# --- Main ---
async def run_bot():
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("balance", balance))
    bot_app.add_handler(CommandHandler("leaderboard", leaderboard))
    bot_app.add_handler(CommandHandler("addadmin", add_admin))
    bot_app.add_handler(CommandHandler("addcoins", add_coins))
    bot_app.add_handler(CommandHandler("battle", battle))
    bot_app.add_handler(CallbackQueryHandler(handle_callback))

    await bot_app.run_polling()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(run_bot())
    app.run(host="0.0.0.0", port=8000)
