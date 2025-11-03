import asyncio
import json
import logging
import os
import nest_asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telethon import TelegramClient, errors

# ------------------ SETUP ------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("controller")

CONFIG_PATH = "bot_config.json"
PROGRESS_PATH = "progress.json"

# ------------------ CONFIG HELPERS ------------------
def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)

# ------------------ LOGIN COMMAND ------------------
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Login to Telegram using Telethon"""
    config = load_config()
    client = TelegramClient(config["session_name"], config["api_id"], config["api_hash"])
    await client.connect()

    try:
        if await client.is_user_authorized():
            await update.message.reply_text("✅ Already logged in!")
            await client.disconnect()
            return

        phone = config["phone"]
        await client.send_code_request(phone)
        await update.message.reply_text("📱 OTP sent! Please reply with /otp <code>")
        config["otp_waiting"] = True
        save_config(config)
    except Exception as e:
        await update.message.reply_text(f"❌ Error sending OTP: {e}")
    finally:
        await client.disconnect()


async def otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle OTP verification"""
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /otp 12345")

    code = context.args[0]
    config = load_config()
    client = TelegramClient(config["session_name"], config["api_id"], config["api_hash"])
    await client.connect()

    try:
        await client.sign_in(phone=config["phone"], code=code)
        config["logged_in"] = True
        config.pop("otp_waiting", None)
        save_config(config)
        await update.message.reply_text("✅ Login successful! Worker can now start.")
    except errors.SessionPasswordNeededError:
        await update.message.reply_text("⚠️ 2FA required! Use /2fa <password>")
    except Exception as e:
        await update.message.reply_text(f"❌ OTP error: {e}")
    finally:
        await client.disconnect()


async def twofa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 2FA login"""
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /2fa <password>")

    password = " ".join(context.args)
    config = load_config()
    client = TelegramClient(config["session_name"], config["api_id"], config["api_hash"])
    await client.connect()

    try:
        await client.sign_in(password=password)
        config["logged_in"] = True
        save_config(config)
        await update.message.reply_text("✅ 2FA Login successful!")
    except Exception as e:
        await update.message.reply_text(f"❌ 2FA error: {e}")
    finally:
        await client.disconnect()

# ------------------ WORKER STATUS ------------------
async def workerstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check worker progress"""
    try:
        if not os.path.exists(PROGRESS_PATH):
            raise FileNotFoundError
        with open(PROGRESS_PATH, "r") as f:
            data = json.load(f)

        await update.message.reply_text(f"""
📊 Worker Status:
Source: {data.get('source', '❓')}
Target: {data.get('target', '❓')}
✅ Added: {data.get('added', 0)} members
⏱ Delay: {data.get('delay_min', '?')}–{data.get('delay_max', '?')}s
💓 Uptime: {data.get('uptime', '?')}
""")
    except FileNotFoundError:
        await update.message.reply_text("⚠️ Worker not running or no progress file found.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching status: {e}")

# ------------------ KEEP ALIVE ------------------
async def keep_alive():
    """Heartbeat log every 10 minutes"""
    while True:
        await asyncio.sleep(600)
        logger.info("💓 Controller heartbeat (alive)")

# ------------------ MAIN ------------------
if __name__ == "__main__":
    nest_asyncio.apply()

    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        raise SystemExit("❌ BOT_TOKEN missing in environment variables!")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("otp", otp))
    app.add_handler(CommandHandler("2fa", twofa))
    app.add_handler(CommandHandler("workerstatus", workerstatus))

    async def main():
        asyncio.create_task(keep_alive())
        logger.info("🚀 Controller bot started successfully.")
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()

    asyncio.run(main())
