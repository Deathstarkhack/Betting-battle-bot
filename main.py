from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import pymongo
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_IDS = [5925363190]  # Replace with your Telegram ID

client = pymongo.MongoClient(MONGO_URI)
db = client["battle_bot"]
users = db["users"]

def get_user(user_obj):
    user_id = user_obj.id
    username = user_obj.username or f"id_{user_id}"
    user = users.find_one({"user_id": user_id})
    if not user:
        users.insert_one({
            "user_id": user_id,
            "username": username,
            "coins": 5,
            "wins": 0,
            "losses": 0
        })
        user = users.find_one({"user_id": user_id})
    else:
        users.update_one({"user_id": user_id}, {"$set": {"username": username}})
    return user

async def start_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone's message to start a battle!")
        return

    user1 = update.message.from_user
    user2 = update.message.reply_to_message.from_user

    u1_data = get_user(user1)
    u2_data = get_user(user2)

    wager = 5
    if u1_data["coins"] < wager or u2_data["coins"] < wager:
        await update.message.reply_text("Both players need at least 5 coins to battle!")
        return

    # Deduct wager immediately
    users.update_one({"user_id": user1.id}, {"$inc": {"coins": -wager}})
    users.update_one({"user_id": user2.id}, {"$inc": {"coins": -wager}})

    keyboard = [
        [
            InlineKeyboardButton("Win: " + user1.first_name, callback_data=f"win_{user1.id}_{user2.id}"),
            InlineKeyboardButton("Draw", callback_data=f"draw_{user1.id}_{user2.id}"),
            InlineKeyboardButton("Win: " + user2.first_name, callback_data=f"win_{user2.id}_{user1.id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = f"⚔️ <b>Battle Initiated!</b> ⚔️\n\n{user1.mention_html()} VS {user2.mention_html()}\n\nEach wagered {wager} coins!\nChoose the result:"
    await update.message.reply_html(msg, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("Only admins can choose the result.")
        return

    data = query.data.split("_")
    action, winner_id, loser_id = data[0], int(data[1]), int(data[2])
    wager = 5
    if action == "win":
        users.update_one({"user_id": winner_id}, {"$inc": {"wins": 1, "coins": wager * 2}})
        users.update_one({"user_id": loser_id}, {"$inc": {"losses": 1}})
        await query.edit_message_text("Result: Victory granted! Winner takes all the coins!")
    elif action == "draw":
        users.update_one({"user_id": winner_id}, {"$inc": {"coins": wager}})
        users.update_one({"user_id": loser_id}, {"$inc": {"coins": wager}})
        await query.edit_message_text("Result: It's a draw! Coins refunded.")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = users.find().sort("wins", -1).limit(10)
    msg = "🏆 <b>Leaderboard</b> 🏆\n"
    for idx, user in enumerate(top, 1):
        uname = f"@{user['username']}" if user.get("username") else f"ID {user['user_id']}"
        msg += f"{idx}. {uname} — Wins: {user['wins']}, Coins: {user['coins']}\n"
    await update.message.reply_html(msg)

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.message.from_user)
    msg = f"You have {user['coins']} coins.\nWins: {user['wins']}, Losses: {user['losses']}"
    await update.message.reply_text(msg)

async def admin_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS:
        await update.message.reply_text("Only admins can use this command.")
        return

    if not context.args or not context.args[0].lstrip("+-").isdigit():
        await update.message.reply_text("Usage:\n/coins @username +10\nor reply to user with /coins +10")
        return

    amount = int(context.args[0])
    target_user = None

    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        target_user = users.find_one({"user_id": target.id})
    else:
        entities = update.message.entities
        mention = next((e for e in entities if e.type == "mention"), None)
        if mention:
            username = update.message.text[mention.offset + 1: mention.offset + mention.length]
            target_user = users.find_one({"username": username})

    if not target_user:
        await update.message.reply_text("User not found in database.")
        return

    users.update_one({"user_id": target_user["user_id"]}, {"$inc": {"coins": amount}})
    msg = f"{'Gave' if amount > 0 else 'Took'} {abs(amount)} coins {'to' if amount > 0 else 'from'} @{target_user['username']}"
    await update.message.reply_text(msg)

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("battle", start_battle))
app.add_handler(CommandHandler("leaderboard", leaderboard))
app.add_handler(CommandHandler("balance", balance))
app.add_handler(CommandHandler("coins", admin_coins))
app.add_handler(CallbackQueryHandler(button_handler))

if __name__ == "__main__":
    app.run_polling()
