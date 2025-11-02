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
# Setup
# ----------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("controller_bot")

CONFIG_FILE = "bot_config.json"
SELF_URL = "https://instaautomation-oe30.onrender.com"  # Your Render URL
PING_INTERVAL = 600  # every 10 minutes

# ----------------------------
# Default config
# ----------------------------
default_config = {
    "api_id": 20339511,
    "api_hash": "400346de83fffd1ef3da5bbaab999d4c",
    "phone": "+919158759397",
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

# ----------------------------
# Login Commands
# ----------------------------
async def login_worker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send OTP for Telegram login"""
    try:
        await update.message.reply_text("📲 Sending OTP to your Telegram account...")
        await client.connect()

        if await client.is_user_authorized():
            await update.message.reply_text("✅ Already logged in!")
            config["logged_in"] = True
            save_config(config)
            return

        await client.send_code_request(config["phone"])
        await update.message.reply_text("📩 OTP sent! Please enter using /otp <code>")
    except Exception as e:
        await update.message.reply_text(f"❌ Error sending OTP: {e}")

async def verify_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify OTP sent to Telegram"""
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /otp <code>")
    otp = context.args[0]
    try:
        await client.connect()
        await client.sign_in(config["phone"], otp)
        if not await client.is_user_authorized():
            return await update.message.reply_text("❌ Invalid or expired OTP.")
        config["logged_in"] = True
        save_config(config)
        await update.message.reply_text("✅ Logged in successfully!")
    except SessionPasswordNeededError:
        await update.message.reply_text("🔐 2-Step Verification ON. Use /pass <password>")
    except Exception as e:
        await update.message.reply_text(f"❌ OTP error: {e}")

async def verify_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle two-step verification password"""
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /pass <your_password>")
    password = " ".join(context.args)
    try:
        await client.sign_in(password=password)
        if await client.is_user_authorized():
            config["logged_in"] = True
            save_config(config)
            await update.message.reply_text("✅ 2-Step verification successful! Logged in.")
        else:
            await update.message.reply_text("❌ Password incorrect.")
    except Exception as e:
        await update.message.reply_text(f"❌ Password error: {e}")

# ----------------------------
# Controller Commands
# ----------------------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Telegram Automation Controller Online!\n\n"
        "Commands:\n"
        "/login - Send OTP to your Telegram number\n"
        "/otp <code> - Verify OTP\n"
        "/pass <password> - Two-Step Verification password\n"
        "/addsource <group>\n"
        "/removesource <group>\n"
        "/addtarget <group>\n"
        "/removetarget <group>\n"
        "/setdelay <min> <max>\n"
        "/startadd\n"
        "/stopadd\n"
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
        await update.message.reply_text(f"✅ Source added: {gid}")
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
        await update.message.reply_text(f"✅ Target added: {gid}")
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
    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /setdelay <min> <max>")
    try:
        mn = int(context.args[0])
        mx = int(context.args[1])
        cfg = load_config()
        cfg["delay_min"] = mn
        cfg["delay_max"] = mx
        save_config(cfg)
        await update.message.reply_text(f"⏱️ Delay set: {mn}-{mx} sec")
    except:
        await update.message.reply_text("⚠️ Invalid format")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    await update.message.reply_text(
        f"📊 Status: {'🟢 Adding' if cfg['is_adding'] else '🔴 Idle'}\n"
        f"👥 Sources: {cfg['source_groups']}\n"
        f"🎯 Targets: {cfg['target_groups']}\n"
        f"⏱️ Delay: {cfg['delay_min']}-{cfg['delay_max']} sec\n"
        f"🔐 Logged In: {'✅' if cfg['logged_in'] else '❌'}"
    )

async def all_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    await update.message.reply_text(json.dumps(cfg, indent=2))

# ----------------------------
# Ping (keep alive)
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
    logger.info("✅ Ping task started every 10 min → %s", SELF_URL)

# ----------------------------
# Start Bot
# ----------------------------
if __name__ == "__main__":
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN missing in environment!")
        exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("login", login_worker))
    app.add_handler(CommandHandler("otp", verify_otp))
    app.add_handler(CommandHandler("pass", verify_password))
    app.add_handler(CommandHandler("addsource", add_source))
    app.add_handler(CommandHandler("removesource", remove_source))
    app.add_handler(CommandHandler("addtarget", add_target))
    app.add_handler(CommandHandler("removetarget", remove_target))
    app.add_handler(CommandHandler("setdelay", set_delay))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("all", all_settings))

    logger.info("🚀 Controller Bot (Login + Worker + Ping) started.")
    app.run_polling()
