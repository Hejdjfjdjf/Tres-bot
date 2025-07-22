import os
import json
import time
import logging
import subprocess
from flask import Flask, request
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
ADMIN_ID = 6725242566  # Your Telegram user ID
TOKEN = "7793156898:AAFWQBuONHJBj4yzFYy824CXI8hj411_i_8"  # Your bot token
HOSTING_FILE = "hosting.json"
POINTS_FILE = "points.json"
PROCESSES_FILE = "processes.json"
USER_SCRIPTS_DIR = "user_scripts"  # Directory to store user scripts
REFERRALS_FILE = "referrals.json"  # File to track referrals

# Conversation states
SELECT_SCRIPT, SET_TOKEN = range(2)

# Ensure directories exist
os.makedirs(USER_SCRIPTS_DIR, exist_ok=True)
for file in [HOSTING_FILE, POINTS_FILE, PROCESSES_FILE, REFERRALS_FILE]:
    if not os.path.exists(file):
        with open(file, 'w') as f:
            if file in [PROCESSES_FILE, REFERRALS_FILE]:
                json.dump({}, f)
            else:
                json.dump({"next_id": 1, "data": {}}, f)

# Utility functions
def load_data(file_name):
    try:
        with open(file_name, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        if file_name in [PROCESSES_FILE, REFERRALS_FILE]:
            return {}
        return {"next_id": 1, "data": {}}

def save_data(file_name, data):
    with open(file_name, 'w') as f:
        json.dump(data, f)

def get_user_points(user_id):
    points_data = load_data(POINTS_FILE)
    return points_data["data"].get(str(user_id), 0)

def add_user_points(user_id, points):
    points_data = load_data(POINTS_FILE)
    points_data["data"][str(user_id)] = points_data["data"].get(str(user_id), 0) + points
    save_data(POINTS_FILE, points_data)

def get_user_scripts(user_id):
    user_dir = os.path.join(USER_SCRIPTS_DIR, str(user_id))
    if not os.path.exists(user_dir):
        return []
    return [f for f in os.listdir(user_dir) if f.endswith('.py')]

def track_referral(referrer_id, referred_id):
    referrals_data = load_data(REFERRALS_FILE)
    if str(referrer_id) not in referrals_data:
        referrals_data[str(referrer_id)] = []
    
    if str(referred_id) not in referrals_data[str(referrer_id)]:
        referrals_data[str(referrer_id)].append(str(referred_id))
        save_data(REFERRALS_FILE, referrals_data)
        return True
    return False

def count_active_referrals(user_id):
    referrals_data = load_data(REFERRALS_FILE)
    return len(referrals_data.get(str(user_id), []))

# [Previous functions remain exactly the same...]

async def invite_for_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_username = (await context.bot.get_me()).username
    invite_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    referrals_count = count_active_referrals(user_id)
    points = get_user_points(user_id)
    
    # Calculate potential earnings
    if referrals_count == 0:
        potential = "10 points (first referral)"
    else:
        potential = f"5 points each (you have {referrals_count} referrals)"
    
    await update.message.reply_text(
        f"📨 *Invite Friends & Earn Points* 📨\n\n"
        f"🔗 Your unique referral link:\n`{invite_link}`\n\n"
        f"📊 *Your Stats*\n"
        f"• Active referrals: {referrals_count}\n"
        f"• Your points: {points}\n\n"
        "💰 *Rewards System*\n"
        f"• First successful referral: 10 points\n"
        f"• Each additional referral: 5 points\n"
        f"• Current earnings per referral: {potential}\n\n"
        "✅ Points are added immediately when users join using your link!\n"
        "⚠️ Self-referrals are not counted",
        parse_mode="Markdown"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].startswith('ref_'):
        referrer_id = int(context.args[0][4:])
        referred_id = update.effective_user.id
        
        if referrer_id != referred_id:
            # Track the referral
            is_new = track_referral(referrer_id, referred_id)
            
            # Award points (10 for first, 5 for subsequent)
            if is_new:
                referrals_count = count_active_referrals(referrer_id)
                points_to_add = 10 if referrals_count == 1 else 5
                add_user_points(referrer_id, points_to_add)
                
                # Get referrer's new points balance
                referrer_points = get_user_points(referrer_id)
                
                await update.message.reply_text(
                    f"🎉 Thanks for joining via referral!\n"
                    f"🏆 {points_to_add} points have been awarded to your referrer "
                    f"(they now have {referrer_points} points total)."
                )
    
    await hosting_menu(update, context)

# Admin commands
async def admin_add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Only admin can use this command!")
        return
    
    try:
        user_id = int(context.args[0])
        points = int(context.args[1])
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Usage: /addpoints <user_id> <points>")
        return
    
    add_user_points(user_id, points)
    await update.message.reply_text(f"✅ Added {points} points to user {user_id}")

async def admin_list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Only admin can use this command!")
        return
    
    points_data = load_data(POINTS_FILE)
    message = "👥 User Points:\n\n"
    for user_id, points in points_data["data"].items():
        message += f"🆔 {user_id}: {points} points\n"
    
    await update.message.reply_text(message)

# Hosting system
async def hosting_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 My Rentals", callback_data="hosting_my")],
        [InlineKeyboardButton("💻 Rent Hosting", callback_data="hosting_rent")],
        [InlineKeyboardButton("💰 My Points", callback_data="hosting_points")],
        [InlineKeyboardButton("📜 Hosting Info", callback_data="hosting_info")],
        [InlineKeyboardButton("⏱️ Uptime", callback_data="uptime_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(
            "🤖 *Bot Hosting Rental System* 🤖\n\n"
            "Host your Telegram bots with our reliable service!\n"
            "Rent hosting using points earned from invites.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        await update.callback_query.edit_message_text(
            "🤖 *Bot Hosting Rental System* 🤖\n\n"
            "Host your Telegram bots with our reliable service!\n"
            "Rent hosting using points earned from invites.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

async def uptime_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Calculate uptime for each rental
    hosting_data = load_data(HOSTING_FILE)
    processes_data = load_data(PROCESSES_FILE)
    
    user_rentals = [
        r for r in hosting_data["data"].values() 
        if r["user_id"] == query.from_user.id and r["process_id"]
    ]
    
    if not user_rentals:
        await query.edit_message_text(
            "❌ You have no active bot processes running.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="hosting_back")]])
        )
        return
    
    message = "⏱️ *Bot Uptime Information* ⏱️\n\n"
    for rental in user_rentals:
        if str(rental["process_id"]) in processes_data:
            start_time = processes_data[str(rental["process_id"])]["start_time"]
            uptime_seconds = int(time.time() - start_time)
            uptime_str = f"{uptime_seconds // 86400}d {(uptime_seconds % 86400) // 3600}h {(uptime_seconds % 3600) // 60}m"
            
            message += (
                f"🔹 *Bot:* @{rental['bot_username']}\n"
                f"🆔 *ID:* `{rental['id']}`\n"
                f"⏱️ *Uptime:* {uptime_str}\n"
                f"🚀 *Started:* {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M')}\n\n"
            )
    
    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="hosting_back")]])
    )

async def hosting_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "hosting_my":
        await show_my_rentals(query)
    elif query.data == "hosting_rent":
        await rent_hosting_menu(query)
    elif query.data == "hosting_points":
        await show_my_points(query)
    elif query.data == "hosting_info":
        await hosting_info(query)
    elif query.data == "uptime_info":
        await uptime_info(query, context)
    elif query.data.startswith("hosting_confirm_"):
        await confirm_rental(query, int(query.data.split("_")[2]))
    elif query.data.startswith("hosting_final_"):
        await process_rental(query, int(query.data.split("_")[2]))
    elif query.data == "hosting_back":
        await hosting_menu(query, context)

async def show_my_rentals(query):
    hosting_data = load_data(HOSTING_FILE)
    user_rentals = [
        r for r in hosting_data["data"].values() 
        if r["user_id"] == query.from_user.id
    ]
    
    if not user_rentals:
        await query.edit_message_text(
            "❌ You have no active rentals.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="hosting_back")]])
        )
        return
    
    message = "🤖 *Your Active Rentals* 🤖\n\n"
    for rental in user_rentals:
        expires = datetime.fromtimestamp(rental["end_time"]).strftime('%Y-%m-%d %H:%M')
        remaining = max(0, rental["end_time"] - time.time())
        days = int(remaining // 86400)
        hours = int((remaining % 86400) // 3600)
        
        message += (
            f"🔹 *ID:* `{rental['id']}`\n"
            f"⏳ *Expires:* {expires}\n"
            f"⏳ *Remaining:* {days}d {hours}h\n"
            f"🤖 *Bot:* {'Not set' if not rental['bot_token'] else '@'+rental['bot_username']}\n"
            f"📜 *Script:* {'Not set' if not rental['bot_script'] else rental['bot_script']}\n\n"
        )
    
    keyboard = [
        [InlineKeyboardButton("📥 Get Script/DB", callback_data="get_files")],
        [InlineKeyboardButton("↩️ Back", callback_data="hosting_back")]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def get_bot_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    hosting_data = load_data(HOSTING_FILE)
    user_rentals = [
        r for r in hosting_data["data"].values() 
        if r["user_id"] == query.from_user.id and r["bot_script"]
    ]
    
    if not user_rentals:
        await query.edit_message_text(
            "❌ You have no active bots with scripts.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="hosting_back")]])
        )
        return
    
    keyboard = []
    for rental in user_rentals:
        keyboard.append([
            InlineKeyboardButton(
                f"📥 {rental['bot_username']} (ID: {rental['id']})",
                callback_data=f"get_files_{rental['id']}"
            )
        ])
    keyboard.append([InlineKeyboardButton("↩️ Back", callback_data="hosting_back")])
    
    await query.edit_message_text(
        "📥 Select a bot to download files:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def send_bot_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    rental_id = query.data.split("_")[2]
    hosting_data = load_data(HOSTING_FILE)
    
    if rental_id not in hosting_data["data"]:
        await query.edit_message_text("❌ Rental not found!")
        return
    
    rental = hosting_data["data"][rental_id]
    if rental["user_id"] != query.from_user.id:
        await query.edit_message_text("❌ This isn't your rental!")
        return
    
    # Send script file
    script_path = os.path.join(USER_SCRIPTS_DIR, str(query.from_user.id), rental["bot_script"])
    if os.path.exists(script_path):
        with open(script_path, 'rb') as f:
            await context.bot.send_document(
                chat_id=query.from_user.id,
                document=f,
                caption=f"📜 Script for bot @{rental['bot_username']}"
            )
    else:
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=f"❌ Script file not found for bot @{rental['bot_username']}"
        )
    
    # Check for database files (example - adjust as needed)
    db_path = os.path.join(USER_SCRIPTS_DIR, str(query.from_user.id), f"{rental['bot_username']}.db")
    if os.path.exists(db_path):
        with open(db_path, 'rb') as f:
            await context.bot.send_document(
                chat_id=query.from_user.id,
                document=f,
                caption=f"🗃️ Database for bot @{rental['bot_username']}"
            )
    else:
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=f"ℹ️ No database file found for bot @{rental['bot_username']}"
        )
    
    await query.edit_message_text(
        "✅ Files sent to your private chat!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="hosting_back")]])
    )

async def rent_hosting_menu(query):
    keyboard = [
        [InlineKeyboardButton("1 Day - 10 points", callback_data="hosting_confirm_1")],
        [InlineKeyboardButton("7 Days - 50 points", callback_data="hosting_confirm_7")],
        [InlineKeyboardButton("30 Days - 200 points", callback_data="hosting_confirm_30")],
        [InlineKeyboardButton("↩️ Back", callback_data="hosting_back")]
    ]
    await query.edit_message_text(
        "📅 *Select Rental Duration* 📅\n\n"
        "1️⃣ 1 Day - 10 points\n"
        "7️⃣ 7 Days - 50 points\n"
        "3️⃣0 Days - 200 points\n\n"
        "💡 Earn points by inviting users with /invite",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def confirm_rental(query, days):
    points_cost = {1: 10, 7: 50, 30: 200}[days]
    user_points = get_user_points(query.from_user.id)
    
    if user_points < points_cost:
        await query.edit_message_text(
            f"❌ Not enough points! You need {points_cost} but have {user_points}.\n"
            "Use /invite to earn more points.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="hosting_back")]])
        )
        return
    
    keyboard = [
        [InlineKeyboardButton(f"✅ Rent for {days} Days", callback_data=f"hosting_final_{days}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="hosting_back")]
    ]
    await query.edit_message_text(
        f"⚠️ *Confirm Rental* ⚠️\n\n"
        f"Duration: {days} day(s)\n"
        f"Cost: {points_cost} points\n"
        f"Your points: {user_points}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def process_rental(query, days):
    points_cost = {1: 10, 7: 50, 30: 200}[days]
    user_id = query.from_user.id
    user_points = get_user_points(user_id)
    
    if user_points < points_cost:
        await query.edit_message_text("❌ Error: Points balance changed. Try again.")
        return
    
    # Deduct points
    points_data = load_data(POINTS_FILE)
    points_data["data"][str(user_id)] = user_points - points_cost
    save_data(POINTS_FILE, points_data)
    
    # Create rental
    hosting_data = load_data(HOSTING_FILE)
    rental_id = str(hosting_data["next_id"])
    
    hosting_data["data"][rental_id] = {
        "id": rental_id,
        "user_id": user_id,
        "start_time": time.time(),
        "end_time": time.time() + (days * 86400),
        "duration_days": days,
        "bot_token": None,
        "bot_username": None,
        "bot_script": None,
        "active": True,
        "process_id": None
    }
    hosting_data["next_id"] += 1
    save_data(HOSTING_FILE, hosting_data)
    
    await query.edit_message_text(
        f"🎉 *Rental Activated!* 🎉\n\n"
        f"🔹 ID: `{rental_id}`\n"
        f"⏳ Expires: {datetime.fromtimestamp(time.time() + (days * 86400)).strftime('%Y-%m-%d %H:%M')}\n\n"
        "To setup your bot:\n"
        "1. Upload your bot script with /uploadscript\n"
        "2. Use /setbot <rental_id> to configure\n\n"
        "Need help? Contact admin.",
        parse_mode="Markdown"
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document uploads for bot scripts"""
    document = update.message.document
    if not document:
        await update.message.reply_text("❌ Please send a Python script file (.py)")
        return
    
    if not document.file_name.lower().endswith('.py'):
        await update.message.reply_text("❌ Only Python (.py) files are accepted!")
        return
    
    # Create user directory if not exists
    user_dir = os.path.join(USER_SCRIPTS_DIR, str(update.effective_user.id))
    os.makedirs(user_dir, exist_ok=True)
    
    # Download the file
    file = await context.bot.get_file(document.file_id)
    file_path = os.path.join(user_dir, document.file_name)
    await file.download_to_drive(file_path)
    
    await update.message.reply_text(
        f"✅ Script '{document.file_name}' uploaded successfully!\n"
        f"📂 Saved to: {file_path}\n\n"
        "You can now use /setbot to configure your bot with this script.",
        parse_mode="Markdown"
    )

async def list_scripts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scripts = get_user_scripts(update.effective_user.id)
    if not scripts:
        await update.message.reply_text("❌ You have no scripts uploaded. Use /uploadscript first.")
        return
    
    script_list = "\n".join(f"📜 {script}" for script in scripts)
    await update.message.reply_text(
        f"📂 Your available scripts:\n{script_list}\n\n"
        "Use /setbot <rental_id> <script_name> to configure your bot.",
        parse_mode="Markdown"
    )

async def set_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rental_id = context.args[0]
        script_name = context.args[1] if len(context.args) > 1 else None
    except IndexError:
        await update.message.reply_text("❌ Usage: /setbot <rental_id> [script_name]")
        return
    
    # Get rental info
    hosting_data = load_data(HOSTING_FILE)
    if rental_id not in hosting_data["data"]:
        await update.message.reply_text("❌ Rental ID not found!")
        return
    
    rental = hosting_data["data"][rental_id]
    if rental["user_id"] != update.effective_user.id:
        await update.message.reply_text("❌ This rental isn't yours!")
        return
    
    if time.time() > rental["end_time"]:
        await update.message.reply_text("❌ This rental has expired!")
        return
    
    # If script name not provided, ask user to select one
    if not script_name:
        scripts = get_user_scripts(update.effective_user.id)
        if not scripts:
            await update.message.reply_text("❌ You have no scripts uploaded. Use /uploadscript first.")
            return
        
        keyboard = [[InlineKeyboardButton(script, callback_data=f"select_script_{rental_id}_{script}")] for script in scripts]
        await update.message.reply_text(
            "📂 Select a script to use:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Validate script exists
    script_path = os.path.join(USER_SCRIPTS_DIR, str(update.effective_user.id), script_name)
    if not os.path.exists(script_path):
        await update.message.reply_text("❌ Script not found in your storage!")
        return
    
    # Ask for bot token
    context.user_data['rental_id'] = rental_id
    context.user_data['script_path'] = script_path
    await update.message.reply_text("🔑 Please enter your bot token (from @BotFather):")
    return SET_TOKEN

async def set_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_token = update.message.text
    
    # Validate token format
    if not (bot_token.count(':') == 1 and len(bot_token) > 30):
        await update.message.reply_text("❌ Invalid bot token format!")
        return SET_TOKEN
    
    rental_id = context.user_data['rental_id']
    script_path = context.user_data['script_path']
    
    # Get bot info
    try:
        from telegram import Bot
        bot = Bot(token=bot_token)
        bot_user = await bot.get_me()
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to verify token: {str(e)}")
        return SET_TOKEN
    
    # Update rental
    hosting_data = load_data(HOSTING_FILE)
    rental = hosting_data["data"][rental_id]
    
    # Stop existing process if any
    if rental["process_id"]:
        try:
            os.kill(rental["process_id"], 9)
            processes = load_data(PROCESSES_FILE)
            if str(rental["process_id"]) in processes:
                del processes[str(rental["process_id"])]
                save_data(PROCESSES_FILE, processes)
        except:
            pass
    
    # Start the bot process
    try:
        process = subprocess.Popen(
            ["python", script_path, bot_token],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Save process ID
        processes = load_data(PROCESSES_FILE)
        processes[str(process.pid)] = {
            "rental_id": rental_id,
            "start_time": time.time()
        }
        save_data(PROCESSES_FILE, processes)
        
        rental["bot_token"] = bot_token
        rental["bot_username"] = bot_user.username
        rental["bot_script"] = os.path.basename(script_path)
        rental["process_id"] = process.pid
        save_data(HOSTING_FILE, hosting_data)
        
        await update.message.reply_text(
            f"✅ Bot setup complete!\n\n"
            f"🤖 Bot: @{bot_user.username}\n"
            f"📜 Script: {os.path.basename(script_path)}\n\n"
            "Your bot is now running!",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to start bot: {str(e)}")
    
    return ConversationHandler.END

async def script_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    _, rental_id, script_name = query.data.split('_', 2)
    script_path = os.path.join(USER_SCRIPTS_DIR, str(query.from_user.id), script_name)
    
    context.user_data['rental_id'] = rental_id
    context.user_data['script_path'] = script_path
    
    await query.edit_message_text("🔑 Please enter your bot token (from @BotFather):")
    return SET_TOKEN

async def hosting_info(query):
    await query.edit_message_text(
        "🤖 *Hosting Information* 🤖\n\n"
        "• 24/7 hosting with auto-restarts\n"
        "• Supports Python Telegram bots\n"
        "• Simple setup process\n\n"
        "💰 *Pricing*:\n"
        "• 1 Day = 10 points\n"
        "• 7 Days = 50 points\n"
        "• 30 Days = 200 points\n\n"
        "🔄 *Earn Points*:\n"
        "• Get 10 points for your first referral\n"
        "• Get 5 points for each additional referral\n\n"
        "⚙️ *Setup*:\n"
        "1. Rent hosting with /hosting\n"
        "2. Upload script with /uploadscript\n"
        "3. Configure with /setbot\n"
        "4. Manage scripts with /listscripts",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="hosting_back")]])
    )

async def show_my_points(query):
    points = get_user_points(query.from_user.id)
    referrals = count_active_referrals(query.from_user.id)
    
    await query.edit_message_text(
        f"💰 *Your Points*: {points}\n"
        f"👥 *Active Referrals*: {referrals}\n\n"
        "Earn more by inviting users with /invite\n"
        "• 10 points for first referral\n"
        "• 5 points for each additional referral",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="hosting_back")]])
    )

async def invite_for_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_username = (await context.bot.get_me()).username
    invite_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    referrals_count = count_active_referrals(user_id)
    points = get_user_points(user_id)
    
    await update.message.reply_text(
        f"📨 *Invite Friends & Earn Points* 📨\n\n"
        f"🔗 Your referral link:\n{invite_link}\n\n"
        f"📊 *Stats*\n"
        f"• Active referrals: {referrals_count}\n"
        f"• Your points: {points}\n\n"
        "💰 *Rewards*\n"
        "• 10 points for first successful referral\n"
        "• 5 points for each additional referral\n\n"
        "Points are added immediately when users join using your link!",
        parse_mode="Markdown"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].startswith('ref_'):
        referrer_id = int(context.args[0][4:])
        referred_id = update.effective_user.id
        
        if referrer_id != referred_id:
            # Track the referral
            is_new = track_referral(referrer_id, referred_id)
            
            # Award points (10 for first, 5 for subsequent)
            if is_new:
                referrals_count = count_active_referrals(referrer_id)
                points_to_add = 10 if referrals_count == 1 else 5
                add_user_points(referrer_id, points_to_add)
                
                await update.message.reply_text(
                    f"🎉 Thanks for joining via referral!\n"
                    f"{points_to_add} points have been awarded to your referrer."
                )
    
    await hosting_menu(update, context)

def main():
    app = Application.builder().token(TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("hosting", hosting_menu))
    app.add_handler(CommandHandler("invite", invite_for_points))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CommandHandler("listscripts", list_scripts))
    app.add_handler(CommandHandler("addpoints", admin_add_points))
    app.add_handler(CommandHandler("listusers", admin_list_users))

    # Setbot conversation handler
    setbot_conv = ConversationHandler(
        entry_points=[CommandHandler("setbot", set_bot)],
        states={
            SET_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_token)],
        },
        fallbacks=[],
    )
    app.add_handler(setbot_conv)

    # Callback handlers
    app.add_handler(CallbackQueryHandler(hosting_button_handler, pattern="^hosting_"))
    app.add_handler(CallbackQueryHandler(script_selected, pattern="^select_script_"))
    app.add_handler(CallbackQueryHandler(uptime_info, pattern="^uptime_info$"))
    app.add_handler(CallbackQueryHandler(get_bot_files, pattern="^get_files$"))
    app.add_handler(CallbackQueryHandler(send_bot_files, pattern="^get_files_"))

    # Start the bot
    app.run_polling()

if __name__ == '__main__':
    main()