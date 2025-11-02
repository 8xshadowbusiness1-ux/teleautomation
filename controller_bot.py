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
SELF_URL = "https://instaautomation-oe30.onrender.com"  # your Render URL
PING_INTERVAL = 1800  # every 30 min (safe from 429)

default_config = {
    "api_id": 22676464,
    "api_hash": "b52406ee2c61546d8b560e2d009052d3",
    "phone": "+917671914528",
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
# Login & Verification
# ----------------------------
async def login_worker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await client.connect()
        await update.message.reply_text("📲 Sending OTP to your Telegram number...")
        if await client.is_user_authorized():
            config["logged_in"] = True
            save_config(config)
            return await update.message.reply_text("✅ Already logged in!")
        await client.send_code_request(config["phone"])
        await update.message.reply_text("📩 OTP sent! Enter with /otp <code>")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def verify_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /otp <code>")
    otp = context.args[0]
    try:
        await client.connect()
        await client.sign_in(config["phone"], otp)
        if not await client.is_user_authorized():
            return await update.message.reply_text("❌ Invalid OTP or expired.")
        config["logged_in"] = True
        save_config(config)
        await update.message.reply_text("✅ Logged in successfully!")
    except SessionPasswordNeededError:
        await update.message.reply_text("🔐 2-Step Verification enabled. Use /pass <password>")
    except Exception as e:
        await update.message.reply_text(f"❌ OTP Error: {e}")

async def verify_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /pass <your_password>")
    password = " ".join(context.args)
    try:
        await client.sign_in(password=password)
        if await client.is_user_authorized():
            config["logged_in"] = True
            save_config(config)
            await update.message.reply_text("✅ 2-Step Verification successful!")
        else:
            await update.message.reply_text("❌ Wrong password.")
    except Exception as e:
        await update.message.reply_text(f"❌ Password Error: {e}")

# ----------------------------
# Command Functions
# ----------------------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Telegram Automation Controller\n\n"
        "🧩 Login Commands:\n"
        "/login → Send OTP\n"
        "/otp <code> → Verify OTP\n"
        "/pass <password> → 2FA password\n\n"
        "🎯 Group Controls:\n"
        "/addsource <group>\n/removesource <group>\n"
        "/addtarget <group>\n/removetarget <group>\n"
        "/setdelay <min> <max>\n\n"
        "⚙️ Controls:\n"
        "/startadd → Start adding\n"
        "/stopadd → Stop adding\n"
        "/status → Check status\n"
        "/all → Full config"
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
        await update.message.reply_text("⚠️ Invalid input.")

async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    cfg["is_adding"] = True
    save_config(cfg)
    await update.message.reply_text("✅ Member adding started!")
    asyncio.create_task(run_adding_loop(update))

async def stop_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    cfg["is_adding"] = False
    save_config(cfg)
    await update.message.reply_text("🛑 Member adding stopped!")

async def run_adding_loop(update: Update):
    """Dummy simulation of adding process (for debug)"""
    await update.message.reply_text("⚙️ Simulating member adding... (loop)")
    while load_config().get("is_adding"):
        delay = random.randint(config["delay_min"], config["delay_max"])
        logger.info(f"⏳ Waiting {delay}s before next add...")
        await asyncio.sleep(delay)
        # future: perform Telethon add-member action here
    logger.info("🔴 Adding loop stopped.")

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
# Ping Keep Alive
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
    logger.info("✅ Ping loop active every 30 min.")

# ----------------------------
# Run Application
# ----------------------------
if __name__ == "__main__":
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN missing in environment!")
        exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()

    handlers = {
        "start": start_cmd,
        "login": login_worker,
        "otp": verify_otp,
        "pass": verify_password,
        "addsource": add_source,
        "removesource": remove_source,
        "addtarget": add_target,
        "removetarget": remove_target,
        "setdelay": set_delay,
        "startadd": start_add,
        "stopadd": stop_add,
        "status": status,
        "all": all_settings,
    }

    for cmd, func in handlers.items():
        app.add_handler(CommandHandler(cmd, func))

    logger.info("🚀 Controller Bot (Login + Add + Ping) started.")
    app.run_polling()
