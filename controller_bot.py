#!/usr/bin/env python3
import asyncio, json, logging, os, nest_asyncio, httpx
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
from telethon import TelegramClient, errors

# ------------------ LOGGING ------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("controller")

# ------------------ CONFIG ------------------
CONFIG_PATH = "bot_config.json"
PROGRESS_PATH = "progress.json"
PING_URL = "https://teleautomation-zkhq.onrender.com"  # ✅ apna latest Render URL

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)

# ------------------ COMMANDS ------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot is online! Use /login to start Telegram session.")

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()

    try:
        if await client.is_user_authorized():
            await update.message.reply_text("✅ Already logged in.")
            await client.disconnect()
            return
        await client.send_code_request(cfg["phone"])
        await update.message.reply_text("📱 OTP sent! Use /otp <code> to verify.")
        cfg["otp_pending"] = True
        save_config(cfg)
    except Exception as e:
        await update.message.reply_text(f"❌ Login error: {e}")
    finally:
        await client.disconnect()

async def otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /otp 12345")

    cfg = load_config()
    code = context.args[0]
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()
    try:
        await client.sign_in(phone=cfg["phone"], code=code)
        cfg["logged_in"] = True
        cfg.pop("otp_pending", None)
        save_config(cfg)
        await update.message.reply_text("✅ Login successful!")
    except errors.SessionPasswordNeededError:
        await update.message.reply_text("⚠️ 2FA enabled! Use /2fa <password>")
    except Exception as e:
        await update.message.reply_text(f"❌ OTP error: {e}")
    finally:
        await client.disconnect()

async def twofa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /2fa <password>")
    password = " ".join(context.args)
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()
    try:
        await client.sign_in(password=password)
        cfg["logged_in"] = True
        save_config(cfg)
        await update.message.reply_text("✅ 2FA login successful!")
    except Exception as e:
        await update.message.reply_text(f"❌ 2FA error: {e}")
    finally:
        await client.disconnect()

async def workerstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(PROGRESS_PATH):
        return await update.message.reply_text("⚠️ Worker not active or no data found.")
    try:
        data = json.load(open(PROGRESS_PATH))
        msg = (
            f"📊 Worker Status:\n"
            f"Source: {data.get('source')}\n"
            f"Target: {data.get('target')}\n"
            f"✅ Added: {data.get('added', 0)} members\n"
            f"⏱ Delay: {data.get('delay_min')}–{data.get('delay_max')}s\n"
            f"💓 Uptime: {data.get('uptime', '?')}"
        )
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error reading progress: {e}")

# ------------------ KEEP ALIVE ------------------
async def keep_alive():
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.get(PING_URL)
                logger.info(f"💓 Ping {PING_URL} | {res.status_code}")
        except Exception as e:
            logger.warning(f"Ping failed: {e}")
        await asyncio.sleep(600)

# ------------------ MAIN ------------------
if __name__ == "__main__":
    nest_asyncio.apply()

    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("❌ BOT_TOKEN missing in environment variables!")

    app = ApplicationBuilder().token(token).build()

    # ✅ Add all handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("otp", otp))
    app.add_handler(CommandHandler("2fa", twofa))
    app.add_handler(CommandHandler("workerstatus", workerstatus))

    # ✅ Background ping task
    asyncio.get_event_loop().create_task(keep_alive())

    logger.info("🚀 Controller bot started successfully.")
    app.run_polling(stop_signals=None)
