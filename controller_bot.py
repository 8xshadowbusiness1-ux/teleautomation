#!/usr/bin/env python3
import asyncio, json, logging, nest_asyncio, os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telethon import TelegramClient, errors

# ---------- LOG ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("controller")

CONFIG_PATH = "bot_config.json"
PROGRESS_PATH = "progress.json"


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def save_config(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)


# ---------- COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot online!\nCommands:\n"
        "/login – send OTP\n"
        "/otp <code>\n"
        "/2fa <password>\n"
        "/workerstatus – check worker"
    )


async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()
    try:
        if await client.is_user_authorized():
            await update.message.reply_text("✅ Already logged in.")
        else:
            await client.send_code_request(cfg["phone"])
            cfg["otp_pending"] = True
            save_config(cfg)
            await update.message.reply_text("📱 OTP sent! Use /otp <code>")
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
        await update.message.reply_text("⚠️ 2FA required! Use /2fa <password>")
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
        return await update.message.reply_text("⚠️ No progress file found.")
    data = json.load(open(PROGRESS_PATH))
    msg = (
        f"📊 Worker Status\n"
        f"Source: {data.get('source')}\n"
        f"Target: {data.get('target')}\n"
        f"✅ Added: {data.get('added', 0)}\n"
        f"⏱ Delay: {data.get('delay_min')}–{data.get('delay_max')}s\n"
        f"💓 Uptime: {data.get('uptime', '?')}"
    )
    await update.message.reply_text(msg)


# ---------- KEEP-ALIVE ----------
async def keep_alive():
    while True:
        await asyncio.sleep(600)
        logger.info("💓 Controller heartbeat")


# ---------- MAIN ----------
async def main():
    nest_asyncio.apply()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("❌ BOT_TOKEN missing!")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("otp", otp))
    app.add_handler(CommandHandler("2fa", twofa))
    app.add_handler(CommandHandler("workerstatus", workerstatus))

    asyncio.create_task(keep_alive())
    logger.info("🚀 Controller bot started and polling...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
