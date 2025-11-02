#!/usr/bin/env python3
import os
import json
import asyncio
import random
import logging
import httpx
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ----------------------------
# Basic Setup
# ----------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("controller_bot")

CONFIG_FILE = "bot_config.json"
SELF_URL = "https://instaautomation-oe30.onrender.com"  # <-- your Render URL
PING_INTERVAL = 600  # 10 minutes


# ----------------------------
# Default Config
# ----------------------------
default_config = {
    "api_id": 20339511,
    "api_hash": "400346de83fffd1ef3da5bbaab999d4c",
    "phone": "+91XXXXXXXXXX",
    "session_name": "worker_main",
    "source_groups": [],
    "target_groups": [],
    "delay_min": 10,
    "delay_max": 15,
    "is_adding": False,
    "logged_in": False
}


def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(default_config)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


config = load_config()


# ----------------------------
# Telethon Client
# ----------------------------
client = TelegramClient(config["session_name"], config["api_id"], config["api_hash"])


async def login_worker(update: Update = None):
    """Login worker using phone number & OTP"""
    try:
        if update:
            await update.message.reply_text("📲 Sending OTP to your Telegram number...")

        await client.connect()
        if not await client.is_user_authorized():
            await client.send_code_request(config["phone"])
            if update:
                await update.message.reply_text("📩 Enter the OTP you received using /otp <code>")
            return False

        if update:
            await update.message.reply_text("✅ Already logged in.")
        config["logged_in"] = True
        save_config(config)
        return True

    except Exception as e:
        if update:
            await update.message.reply_text(f"❌ Login error: {e}")
        return False


async def verify_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify OTP entered by user"""
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /otp <code>")
        return
    otp = context.args[0]
    try:
        await client.connect()
        await client.sign_in(config["phone"], otp)
        if not await client.is_user_authorized():
            await update.message.reply_text("❌ OTP invalid or expired.")
            return
        config["logged_in"] = True
        save_config(config)
        await update.message.reply_text("✅ Login successful!")
    except SessionPasswordNeededError:
        await update.message.reply_text("🔒 2-Step Verification is ON. Please enter password with /pass <your_password>")
    except Exception as e:
        await update.message.reply_text(f"❌ Error verifying OTP: {e}")


async def verify_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 2FA password"""
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /pass <password>")
        return
    password = " ".join(context.args)
    try:
        await client.sign_in(password=password)
        if await client.is_user_authorized():
            config["logged_in"] = True
            save_config(config)
            await update.message.reply_text("✅ Logged in successfully (2FA passed)!")
        else:
            await update.message.reply_text("❌ Password incorrect.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


# ----------------------------
# Controller Commands
# ----------------------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Telegram Automation System Ready!\n\n"
        "Commands:\n"
        "/login - Send OTP for worker login\n"
        "/otp <code> - Verify OTP\n"
        "/pass <password> - 2FA password (if needed)\n"
        "/addsource <group>\n"
        "/removesource <group>\n"
        "/addtarget <group>\n"
        "/removetarget <group>\n"
        "/setdelay <min> <max>\n"
        "/startadd - Begin member adding\n"
        "/stopadd - Stop\n"
        "/status\n"
        "/all"
    )


async def add_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /addsource <group>")
    gid = context.args[0]
    cfg = load_config()
    if gid not in cfg["source_groups"]:
        cfg["source_groups"].append(gid)
        save_config(cfg)
        await update.message.reply_text(f"✅ Added source: {gid}")
    else:
        await update.message.reply_text("⚠️ Already exists.")


async def add_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /addtarget <group>")
    gid = context.args[0]
    cfg = load_config()
    if gid not in cfg["target_groups"]:
        cfg["target_groups"].append(gid)
        save_config(cfg)
        await update.message.reply_text(f"✅ Added target: {gid}")
    else:
        await update.message.reply_text("⚠️ Already exists.")


async def remove_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /removesource <group>")
    gid = context.args[0]
    cfg = load_config()
    if gid in cfg["source_groups"]:
        cfg["source_groups"].remove(gid)
        save_config(cfg)
        await update.message.reply_text(f"🗑️ Removed source: {gid}")
    else:
        await update.message.reply_text("⚠️ Not found.")


async def remove_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /removetarget <group>")
    gid = context.args[0]
    cfg = load_config()
    if gid in cfg["target_groups"]:
        cfg["target_groups"].remove(gid)
        save_config(cfg)
        await update.message.reply_text(f"🗑️ Removed target: {gid}")
    else:
        await update.message.reply_text("⚠️ Not found.")


async def set_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        mn = int(context.args[0])
        mx = int(context.args[1])
        cfg = load_config()
        cfg["delay_min"] = mn
        cfg["delay_max"] = mx
        save_config(cfg)
        await update.message.reply_text(f"⏱️ Delay set to {mn}-{mx}s.")
    except:
        await update.message.reply_text("⚠️ Usage: /setdelay <min> <max>")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    await update.message.reply_text(
        f"📊 Status: {'🟢 Adding' if cfg['is_adding'] else '🔴 Idle'}\n"
        f"👥 Sources: {cfg['source_groups']}\n"
        f"🎯 Targets: {cfg['target_groups']}\n"
        f"⏱️ Delay: {cfg['delay_min']}-{cfg['delay_max']} sec\n"
        f"🔐 Logged In: {'✅' if cfg['logged_in'] else '❌'}"
    )


# ----------------------------
# Pinger
# ----------------------------
async def ping_loop():
    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            try:
                r = await client.get(SELF_URL)
                logger.info("🌐 Pinged %s | %s", SELF_URL, r.status_code)
            except Exception as e:
                logger.warning("⚠️ Ping failed: %s", e)
            await asyncio.sleep(PING_INTERVAL)


async def on_startup(app):
    asyncio.create_task(ping_loop())
    logger.info("✅ Ping system started every 10min → %s", SELF_URL)


# ----------------------------
# Run Bot
# ----------------------------
if __name__ == "__main__":
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN missing in environment!")
        exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("login", lambda u, c: login_worker(u)))
    app.add_handler(CommandHandler("otp", verify_otp))
    app.add_handler(CommandHandler("pass", verify_password))
    app.add_handler(CommandHandler("addsource", add_source))
    app.add_handler(CommandHandler("removesource", remove_source))
    app.add_handler(CommandHandler("addtarget", add_target))
    app.add_handler(CommandHandler("removetarget", remove_target))
    app.add_handler(CommandHandler("setdelay", set_delay))
    app.add_handler(CommandHandler("status", status))

    logger.info("🚀 Controller + Worker started.")
    app.run_polling()
