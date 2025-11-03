import asyncio, json, logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telethon import TelegramClient
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

CONFIG_PATH = "bot_config.json"

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    client = TelegramClient(config["session_name"], config["api_id"], config["api_hash"])
    await client.connect()
    if not await client.is_user_authorized():
        await update.message.reply_text("📱 Enter the OTP sent to your Telegram:")
        phone = config["phone"]
        await client.send_code_request(phone)
        code = await context.bot.wait_for_message(chat_id=update.effective_chat.id)
        await client.sign_in(phone=phone, code=code.text)
    config["logged_in"] = True
    save_config(config)
    await update.message.reply_text("✅ Login successful! Worker will now start.")
    await client.disconnect()

async def workerstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = json.load(open("progress.json"))
        await update.message.reply_text(f"""
📊 Worker Status:
Source: {data.get('source')}
Target: {data.get('target')}
✅ Added: {data.get('added')} members
⏱ Delay: {data.get('delay_min')}–{data.get('delay_max')}s
💓 Uptime: {data.get('uptime')}
""")
    except:
        await update.message.reply_text("⚠️ Worker not active or no progress file found.")

app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
app.add_handler(CommandHandler("login", login))
app.add_handler(CommandHandler("workerstatus", workerstatus))

async def keep_alive():
    while True:
        await asyncio.sleep(60)
        logging.info("💓 Controller heartbeat")

asyncio.get_event_loop().create_task(keep_alive())
app.run_polling()
