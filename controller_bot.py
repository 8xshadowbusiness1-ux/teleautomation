#!/usr/bin/env python3
import asyncio
import json
import logging
import nest_asyncio
import os
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from telethon import TelegramClient, errors

# ------------------ LOGGING ------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("controller")

CONFIG_PATH = "bot_config.json"
PROGRESS_PATH = "progress.json"

# ------------------ CONFIG ------------------
def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def save_config(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)


# ------------------ LOGIN ------------------
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()

    try:
        if await client.is_user_authorized():
            await update.message.reply_text("✅ Already logged in.")
            await client.disconnect()
            return

        phone = cfg["phone"]
        await client.send_code_request(phone)
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

    code = context.args[0]
    cfg = load_config()
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


# ------------------ STATUS ------------------
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
        await asyncio.sleep(600)
        logger.info("💓 Controller heartbeat (alive)")


# ------------------ MAIN ------------------
async def main():
    nest_asyncio.apply()

    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("❌ BOT_TOKEN missing in environment variables!")

    app = ApplicationBuilder().token(token).build()

    handlers = [
        CommandHandler("login", login),
        CommandHandler("otp", otp),
        CommandHandler("2fa", twofa),
        CommandHandler("workerstatus", workerstatus),
    ]
    for h in handlers:
        app.add_handler(h)

    logger.info("🚀 Controller bot started successfully.")
    asyncio.create_task(keep_alive())

    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
