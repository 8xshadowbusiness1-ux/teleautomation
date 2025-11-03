#!/usr/bin/env python3
import asyncio
import json
import logging
import nest_asyncio
import os
import httpx
from telegram import Update
from telegram.ext import (
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

# ------------------ CONFIG HELPERS ------------------
def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def save_config(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)


# ------------------ LOGIN SYSTEM ------------------
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    phone = cfg.get("phone")

    if not phone or not isinstance(phone, str) or not phone.startswith("+"):
        return await update.message.reply_text(
            "⚠️ Invalid phone number in config.\nFix it like: `+91843xxxxxxx`"
        )

    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()

    try:
        if await client.is_user_authorized():
            cfg["logged_in"] = True
            save_config(cfg)
            await update.message.reply_text("✅ Already logged in.")
            return

        result = await client.send_code_request(phone)
        if not result or not getattr(result, "phone_code_hash", None):
            raise ValueError("No phone_code_hash returned — check phone number and API credentials.")

        cfg["phone_code_hash"] = result.phone_code_hash
        save_config(cfg)
        await update.message.reply_text("📱 OTP sent! Use `/otp <code>` to verify.")
    except Exception as e:
        logger.exception("Login error")
        await update.message.reply_text(f"❌ Login failed: {e}")
    finally:
        await client.disconnect()


async def otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /otp 12345")

    code = context.args[0]
    cfg = load_config()

    phone = cfg.get("phone")
    phone_hash = cfg.get("phone_code_hash")

    if not phone_hash:
        return await update.message.reply_text("⚠️ Missing phone_code_hash. Try `/login` again.")

    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()
    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_hash)
        cfg["logged_in"] = True
        cfg.pop("phone_code_hash", None)
        save_config(cfg)
        await update.message.reply_text("✅ Login successful! Worker can now start.")
    except errors.SessionPasswordNeededError:
        await update.message.reply_text("⚠️ 2FA enabled! Use `/2fa <password>`")
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


# ------------------ STATUS COMMAND ------------------
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


# ------------------ ALL COMMANDS ------------------
async def allcmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 Available Commands:\n\n"
        "🔹 /login — Start login process\n"
        "🔹 /otp <code> — Verify OTP\n"
        "🔹 /2fa <password> — Complete 2FA login\n"
        "🔹 /workerstatus — Check worker progress\n"
        "🔹 /setdelay <min> <max> — Set member add delay\n"
    )
    await update.message.reply_text(text)


# ------------------ SET DELAY ------------------
async def setdelay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    try:
        if len(context.args) < 2:
            return await update.message.reply_text("⚙️ Usage: /setdelay <min> <max>")

        dmin = int(context.args[0])
        dmax = int(context.args[1])
        if dmin <= 0 or dmax <= 0 or dmin > dmax:
            return await update.message.reply_text("⚠️ Invalid delay range.")

        cfg["delay_min"] = dmin
        cfg["delay_max"] = dmax
        save_config(cfg)
        await update.message.reply_text(f"✅ Delay updated to {dmin}-{dmax} seconds.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error setting delay: {e}")


# ------------------ KEEP ALIVE / PING ------------------
async def keep_alive():
    cfg = load_config()
    ping_url = cfg.get("PING_URL")

    while True:
        await asyncio.sleep(600)  # every 10 mins
        if ping_url:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.get(ping_url)
                    logger.info(f"💓 Ping {ping_url} | {r.status_code}")
            except Exception as e:
                logger.warning(f"Ping failed: {e}")
        else:
            logger.info("💓 Heartbeat (no ping URL)")


# ------------------ MAIN APP ------------------
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
        CommandHandler("allcmd", allcmd),
        CommandHandler("setdelay", setdelay),
    ]
    for h in handlers:
        app.add_handler(h)

    logger.info("🚀 Controller bot started successfully.")

    # Startup /allcmd auto message
    async def show_all_commands():
        await asyncio.sleep(2)
        try:
            chat_id = os.getenv("OWNER_ID")
            if chat_id:
                await app.bot.send_message(
                    chat_id=chat_id,
                    text="🤖 Bot Online!\nUse /allcmd to view all commands."
                )
        except Exception as e:
            logger.warning(f"Startup message failed: {e}")

    asyncio.create_task(show_all_commands())
    asyncio.create_task(keep_alive())

    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
