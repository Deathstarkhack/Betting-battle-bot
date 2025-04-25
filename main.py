from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import pymongo
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

client = pymongo.MongoClient(MONGO_URI)
db = client["battle_bot"]
users = db["users"]
admin_data = db["admins"]

def is_admin(user_id):
    return admin_data.find_one({"user_id": user_id}) is not None

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
        await update.message.reply_text("Reply to a user to start a battle.")
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /battle <amount>\nExample: /battle 50")
        return

    amount = int(context.args[0])
    user1 = update.message.from_user
    user2 = update.message.reply_to_message.from_user

    u1_data = get_user(user1)
    u2_data = get_user(user2)

    if u1_data["coins"] < amount or u2_data["coins"] < amount:
        await update.message.reply_text(f"Both users must have at least {amount} coins.")
        return

    start_button = InlineKeyboardButton(
        "Start Battle",
        callback_data=f"begin_{user1.id}_{user2.id}_{amount}"
    )
    reply_markup = InlineKeyboardMarkup([[start_button]])
    await update.message.reply_text(
        f"⚔️ Battle Request ⚔️\n\n{user1.mention_html()} vs {user2.mention_html()}\n\nWager: {amount} coins each.\n\nWaiting for admin approval...",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data.startswith("begin_"):
        if not is_admin(user_id):
            return  # silently ignore

        _, uid1, uid2, amount = query.data.split("_")
        uid1, uid2, amount = int(uid1), int(uid2), int(amount)

        users.update_one({"user_id": uid1}, {"$inc": {"coins": -amount}})
        users.update_one({"user_id": uid2}, {"$inc": {"coins": -amount}})

        u1 = users.find_one({"user_id": uid1})
        u2 = users.find_one({"user_id": uid2})

        keyboard = [
            [
                InlineKeyboardButton(f"Win: @{u1['username']}", callback_data=f"win_{uid1}_{uid2}_{amount}"),
                InlineKeyboardButton("Draw", callback_data=f"draw_{uid1}_{uid2}_{amount}"),
                InlineKeyboardButton(f"Win: @{u2['username']}", callback_data=f"win_{uid2}_{uid1}_{amount}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"⚔️ <b>Battle Started</b> ⚔️\n\n@{u1['username']} vs @{u2['username']}\nWager: {amount} coins each.\nChoose the result:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

    elif query.data.startswith("win_") or query.data.startswith("draw_"):
        if not is_admin(user_id):
            return

        parts = query.data.split("_")
        action, uid1, uid2, amount = parts[0], int(parts[1]), int(parts[2]), int(parts[3])

        if action == "win":
            users.update_one({"user_id": uid1}, {"$inc": {"wins": 1, "coins": amount * 2}})
            users.update_one({"user_id": uid2}, {"$inc": {"losses": 1}})
            winner = users.find_one({"user_id": uid1})
            await query.edit_message_text(f"🏆 <b>Winner:</b> @{winner['username']} wins {amount * 2} coins!", parse_mode="HTML")
        else:
            users.update_one({"user_id": uid1}, {"$inc": {"coins": amount}})
            users.update_one({"user_id": uid2}, {"$inc": {"coins": amount}})
            await query.edit_message_text("🤝 It's a draw! Both players refunded.", parse_mode="HTML")

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

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("Only admins can add other admins.")
        return

    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        if not is_admin(user.id):
            admin_data.insert_one({"user_id": user.id})
            await update.message.reply_text(f"Added @{user.username or user.id} as admin.")
        else:
            await update.message.reply_text("User is already an admin.")
    else:
        await update.message.reply_text("Reply to the user you want to add as admin.")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("Only admins can remove other admins.")
        return

    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        if is_admin(user.id):
            admin_data.delete_one({"user_id": user.id})
            await update.message.reply_text(f"Removed @{user.username or user.id} as admin.")
        else:
            await update.message.reply_text("User is not an admin.")
    else:
        await update.message.reply_text("Reply to the user you want to remove as admin.")

async def admin_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("Only admins can give coins.")
        return

    if not context.args or not context.args[0].lstrip("+-").isdigit():
        await update.message.reply_text("Usage:\n/coins +10 (when replying)\nor /coins @username +10")
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

PORT = int(os.environ.get('PORT', 8080))
WEBHOOK_URL = f"https://promising-morgana-death-ebbe2d2c.koyeb.app/.koyeb.app"  # replace with your actual Koyeb app URL

app = ApplicationBuilder().token(BOT_TOKEN).build()

async def start():
    await app.bot.set_webhook(WEBHOOK_URL)
    await app.initialize()
    await app.start()
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="",
        webhook_url=WEBHOOK_URL,
    )
    await app.updater.idle()

if __name__ == '__main__':
    import asyncio
    asyncio.run(start())
    
# Register commands
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("battle", start_battle))
app.add_handler(CommandHandler("leaderboard", leaderboard))
app.add_handler(CommandHandler("balance", balance))
app.add_handler(CommandHandler("addadmin", add_admin))
app.add_handler(CommandHandler("removeadmin", remove_admin))
app.add_handler(CommandHandler("coins", admin_coins))
app.add_handler(CallbackQueryHandler(button_handler))

if __name__ == "__main__":
    app.run_polling()
