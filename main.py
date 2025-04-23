import os import asyncio from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes import pymongo from flask import Flask from threading import Thread

BOT_TOKEN = os.getenv("BOT_TOKEN") MONGO_URI = os.getenv("MONGO_URI")

client = pymongo.MongoClient(MONGO_URI) db = client["battle_bot"] users = db["users"] admin_data = db["admins"]

--- Flask Server for Koyeb ---

app_web = Flask(name)

@app_web.route("/") def home(): return "Bot is running."

def run_flask(): app_web.run(host="0.0.0.0", port=8000)

--- Utility Functions ---

def is_admin(user_id): return admin_data.find_one({"user_id": user_id}) is not None

def get_user(user_obj): user_id = user_obj.id username = user_obj.username or f"id_{user_id}" user = users.find_one({"user_id": user_id}) if not user: users.insert_one({ "user_id": user_id, "username": username, "coins": 5, "wins": 0, "losses": 0 }) user = users.find_one({"user_id": user_id}) else: users.update_one({"user_id": user_id}, {"$set": {"username": username}}) return user

--- Bot Handlers ---

current_battles = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): user = get_user(update.effective_user) await update.message.reply_text(f"Welcome {user['username']}! You have {user['coins']} coins.")

async def start_battle(update: Update, context: ContextTypes.DEFAULT_TYPE): if len(context.args) != 2: return await update.message.reply_text("Usage: /battle <amount> <@opponent>")

initiator = update.effective_user
initiator_data = get_user(initiator)
try:
    amount = int(context.args[0])
except ValueError:
    return await update.message.reply_text("Amount must be a number.")

if initiator_data['coins'] < amount:
    return await update.message.reply_text("You don't have enough coins.")

if not update.message.entities or len(update.message.entities) < 2:
    return await update.message.reply_text("Tag your opponent with @username.")

opponent_username = context.args[1].lstrip('@')
opponent = users.find_one({"username": opponent_username})
if not opponent:
    return await update.message.reply_text("Opponent not found in database.")

if opponent['coins'] < amount:
    return await update.message.reply_text("Opponent doesn't have enough coins.")

key = f"{initiator.id}_{opponent['user_id']}"
current_battles[key] = {
    "initiator": initiator_data,
    "opponent": opponent,
    "amount": amount
}

buttons = [[InlineKeyboardButton("Start Battle", callback_data=f"start_{key}")]]
await update.message.reply_text(
    f"Battle Request: {initiator_data['username']} vs {opponent['username']} for {amount} coins.",
    reply_markup=InlineKeyboardMarkup(buttons)
)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE): query = update.callback_query await query.answer()

user_id = query.from_user.id
if not is_admin(user_id):
    return await query.edit_message_text("Only an admin can start battles.")

data = query.data
if data.startswith("start_"):
    key = data[6:]
    battle = current_battles.get(key)
    if not battle:
        return await query.edit_message_text("Battle not found or expired.")

    winner = battle['initiator'] if os.urandom(1)[0] % 2 == 0 else battle['opponent']
    loser = battle['opponent'] if winner == battle['initiator'] else battle['initiator']

    users.update_one({"user_id": winner['user_id']}, {"$inc": {"coins": battle['amount'], "wins": 1}})
    users.update_one({"user_id": loser['user_id']}, {"$inc": {"coins": -battle['amount'], "losses": 1}})

    await query.edit_message_text(
        f"Battle Result: {winner['username']} won and earned {battle['amount']} coins!"
    )

    del current_battles[key]

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE): top = users.find().sort("coins", -1).limit(10) msg = "Leaderboard:\n" for idx, user in enumerate(top, start=1): msg += f"{idx}. {user['username']} - {user['coins']} coins\n" await update.message.reply_text(msg)

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE): if str(update.effective_user.id) != "5925363190": return await update.message.reply_text("Unauthorized.")

if not context.args:
    return await update.message.reply_text("Usage: /addadmin <user_id>")

admin_data.insert_one({"user_id": int(context.args[0])})
await update.message.reply_text("Admin added.")

--- Main Bot Function ---

async def run_bot(): bot_app = ApplicationBuilder().token(BOT_TOKEN).build()

bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("battle", start_battle))
bot_app.add_handler(CommandHandler("leaderboard", leaderboard))
bot_app.add_handler(CommandHandler("addadmin", add_admin))
bot_app.add_handler(CallbackQueryHandler(button_handler))

await bot_app.run_polling()

--- Start Flask + Bot Together ---

if name == "main": Thread(target=run_flask).start() asyncio.run(run_bot())

