import asyncio
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)
from pymongo import MongoClient
import os

# === MongoDB Setup ===
MONGO_URI = "mongodb+srv://criminalboyz10:l6RLBnBtohoyjPgh@cluster0.d9ifbhj.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
users = db["users"]
admins = db["admins"]
battles = db["battles"]

# === Flask Server for Koyeb ===
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

# === Helper Functions ===
def is_admin(user_id):
    return admins.find_one({"user_id": user_id}) is not None

def get_or_create_user(user_id, username):
    user = users.find_one({"user_id": user_id})
    if not user:
        user = {"user_id": user_id, "username": username, "coins": 100}
        users.insert_one(user)
    return user

def update_user_coins(user_id, coins):
    users.update_one({"user_id": user_id}, {"$set": {"coins": coins}})

def add_admin(user_id, username):
    admins.update_one({"user_id": user_id}, {"$set": {"username": username}}, upsert=True)

# === Telegram Bot ===
TOKEN = "7677492647:AAEnswiLDx0A2zVD9cIUOM-Jv_xlm_mY_Ns"  # Replace with your bot token
bot_app = ApplicationBuilder().token(TOKEN).build()

# === Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_create_user(update.effective_user.id, update.effective_user.username)
    await update.message.reply_text(f"Welcome, {user['username']}! You have {user['coins']} coins.")

async def add_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == 5925363190:
        add_admin(update.effective_user.id, update.effective_user.username)
        await update.message.reply_text("You are now an admin.")
    else:
        await update.message.reply_text("You're not authorized to do this.")

async def battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1 or not context.message.reply_to_message:
        await update.message.reply_text("Use /battle <coins> in reply to a user.")
        return
    try:
        coins = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid coin amount.")
        return

    user1 = update.effective_user
    user2 = context.message.reply_to_message.from_user
    u1 = get_or_create_user(user1.id, user1.username)
    u2 = get_or_create_user(user2.id, user2.username)

    if u1["coins"] < coins or u2["coins"] < coins:
        await update.message.reply_text("Both players must have enough coins.")
        return

    battles.update_one(
        {"user1": user1.id, "user2": user2.id},
        {"$set": {
            "user1": user1.id,
            "user2": user2.id,
            "coins": coins
        }},
        upsert=True
    )

    keyboard = [
        [InlineKeyboardButton("Start Battle", callback_data=f"start|{user1.id}|{user2.id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Battle request:\n{user1.mention_html()} vs {user2.mention_html()}\nWager: {coins} coins",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("start"):
        _, uid1, uid2 = data.split("|")
        uid1, uid2 = int(uid1), int(uid2)
        battle = battles.find_one({"user1": uid1, "user2": uid2})

        if not battle:
            await query.edit_message_text("Battle not found.")
            return

        keyboard = [
            [InlineKeyboardButton("Winner: User 1", callback_data=f"win|{uid1}|{uid2}")],
            [InlineKeyboardButton("Winner: User 2", callback_data=f"win|{uid2}|{uid1}")],
            [InlineKeyboardButton("Draw", callback_data=f"draw|{uid1}|{uid2}")]
        ]
        markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"Battle Started!\n<u>User 1</u>: <code>{uid1}</code>\n<u>User 2</u>: <code>{uid2}</code>",
            reply_markup=markup,
            parse_mode="HTML"
        )

    elif data.startswith("win"):
        winner, loser = map(int, data.split("|")[1:])
        battle = battles.find_one({"user1": winner, "user2": loser}) or battles.find_one({"user1": loser, "user2": winner})
        coins = battle["coins"]
        users.update_one({"user_id": winner}, {"$inc": {"coins": coins}})
        users.update_one({"user_id": loser}, {"$inc": {"coins": -coins}})
        await query.edit_message_text(f"Winner is <code>{winner}</code>! (+{coins} coins)", parse_mode="HTML")

    elif data.startswith("draw"):
        uid1, uid2 = map(int, data.split("|")[1:])
        await query.edit_message_text("Battle ended in a draw.")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = list(users.find().sort("coins", -1).limit(10))
    text = "<b>Leaderboard:</b>\n"
    for i, user in enumerate(top, 1):
        text += f"{i}. @{user['username']} - {user['coins']} coins\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def give_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Admins only.")
        return
    if len(context.args) != 2 or not context.message.reply_to_message:
        await update.message.reply_text("Use /give <coins> as reply.")
        return
    try:
        coins = int(context.args[0])
    except:
        await update.message.reply_text("Invalid coin amount.")
        return
    target = context.message.reply_to_message.from_user
    user = get_or_create_user(target.id, target.username)
    users.update_one({"user_id": target.id}, {"$inc": {"coins": coins}})
    await update.message.reply_text(f"Gave {coins} coins to @{user['username']}.")

# === Register Handlers ===
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("addadmin", add_admin_cmd))
bot_app.add_handler(CommandHandler("battle", battle))
bot_app.add_handler(CommandHandler("leaderboard", leaderboard))
bot_app.add_handler(CommandHandler("give", give_coins))
bot_app.add_handler(CallbackQueryHandler(handle_buttons))

# === Run Both Bot and Flask ===
async def run_bot():
    await bot_app.run_polling()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(run_bot())
    app.run(host="0.0.0.0", port=8000)
