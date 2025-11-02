#!/usr/bin/env python3
import os
import json
import asyncio
import logging
import httpx
import subprocess
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------------------- SETUP ----------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("controller_bot")

CONFIG_FILE = "bot_config.json"
SELF_URL = "https://instaautomation-oe30.onrender.com"  # your Render URL
PING_INTERVAL = 300  # every 5 minutes

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

# ---------------------- CONFIG HANDLERS ----------------------
def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(default_config)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

config = load_config()

# ---------------------- COMMAND HANDLERS ----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Telegram Automation Controller*\n\n"
        "/login - Send OTP\n"
        "/otp <code> - Verify OTP\n"
        "/pass <password> - Two-Step password\n"
        "/addsource <group_id>\n"
        "/removesource <group_id>\n"
        "/addtarget <group_id>\n"
        "/removetarget <group_id>\n"
        "/setdelay <min> <max>\n"
        "/startadd - Begin auto adding\n"
        "/stopadd - Stop adding\n"
        "/status - Current status\n"
        "/all - Full config",
        parse_mode="Markdown"
    )

async def add_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /addsource <group_id>")
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
        return await update.message.reply_text("Usage: /addtarget <group_id>")
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
        return await update.message.reply_text("Usage: /removesource <group_id>")
    gid = context.args[0]
    cfg = load_config()
    if gid in cfg["source_groups"]:
        cfg["source_groups"].remove(gid)
        save_config(cfg)
        await update.message.reply_text(f"🗑 Removed source: {gid}")
    else:
        await update.message.reply_text("⚠️ Not found.")

async def remove_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /removetarget <group_id>")
    gid = context.args[0]
    cfg = load_config()
    if gid in cfg["target_groups"]:
        cfg["target_groups"].remove(gid)
        save_config(cfg)
        await update.message.reply_text(f"🗑 Removed target: {gid}")
    else:
        await update.message.reply_text("⚠️ Not found.")

async def set_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /setdelay <min> <max>")
    try:
        mn, mx = int(context.args[0]), int(context.args[1])
        cfg = load_config()
        cfg["delay_min"], cfg["delay_max"] = mn, mx
        save_config(cfg)
        await update.message.reply_text(f"⏱ Delay set to {mn}-{mx} sec")
    except:
        await update.message.reply_text("⚠ Invalid format")

async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    if cfg["is_adding"]:
        return await update.message.reply_text("⚠ Already running.")
    cfg["is_adding"] = True
    save_config(cfg)
    subprocess.Popen(["python3", "worker_add.py"])
    await update.message.reply_text("🟢 Started adding members in background!")

async def stop_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    cfg["is_adding"] = False
    save_config(cfg)
    await update.message.reply_text("🔴 Adding stopped. Worker will exit soon.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    msg = (
        f"📊 *Status*\n"
        f"Sources: {cfg['source_groups']}\n"
        f"Targets: {cfg['target_groups']}\n"
        f"Delay: {cfg['delay_min']}-{cfg['delay_max']} sec\n"
        f"Adding: {'🟢 ON' if cfg['is_adding'] else '🔴 OFF'}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def all_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    await update.message.reply_text(json.dumps(cfg, indent=2))

# ---------------------- KEEP ALIVE ----------------------
async def ping_loop():
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            try:
                r = await client.get(SELF_URL)
                logger.info(f"🌐 Pinged {SELF_URL} | {r.status_code}")
            except Exception as e:
                logger.warning(f"Ping failed: {e}")
            await asyncio.sleep(PING_INTERVAL)

async def on_startup(app):
    asyncio.create_task(ping_loop())
    logger.info("✅ Ping task started every 5 min → %s", SELF_URL)

# ---------------------- START BOT ----------------------
if __name__ == "__main__":
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not found in env!")
        exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addsource", add_source))
    app.add_handler(CommandHandler("removesource", remove_source))
    app.add_handler(CommandHandler("addtarget", add_target))
    app.add_handler(CommandHandler("removetarget", remove_target))
    app.add_handler(CommandHandler("setdelay", set_delay))
    app.add_handler(CommandHandler("startadd", start_add))
    app.add_handler(CommandHandler("stopadd", stop_add))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("all", all_settings))

    logger.info("🚀 Controller bot started successfully.")
    app.run_polling()
