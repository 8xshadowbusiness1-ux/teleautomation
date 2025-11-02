#!/usr/bin/env python3
import os
import json
import asyncio
import random
import logging
import httpx
from typing import List
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("controller_bot")

# ---------- CONFIG ----------
CONFIG_FILE = "bot_config.json"

default_config = {
    "api_id": 20339511,
    "api_hash": "400346de83fffd1ef3da5bbaab999d4c",
    "phone": "+91XXXXXXXXXX",
    "session_name": "main_worker",
    "source_groups": [],
    "target_groups": [],
    "delay_min": 10,
    "delay_max": 15,
    "is_adding": False
}

def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        save_config(default_config.copy())
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
    except Exception as e:
        logger.error("Failed to read config, recreating: %s", e)
        cfg = default_config.copy()
        save_config(cfg)
    for k, v in default_config.items():
        cfg.setdefault(k, v)
    return cfg

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

config = load_config()

# ---------- Helpers ----------
def safe_list_str(arr: List[str]) -> str:
    return ", ".join(arr) if arr else "(none)"

# ---------- Telegram Commands ----------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Controller Online!\n\n"
        "Commands:\n"
        "/addsource <id_or_username>\n"
        "/removesource <id_or_username>\n"
        "/addtarget <id_or_username>\n"
        "/removetarget <id_or_username>\n"
        "/setdelay <min> <max>\n"
        "/startadd\n"
        "/stopadd\n"
        "/status\n"
        "/all"
    )

async def add_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /addsource <group_id>")
    gid = context.args[0]
    cfg = load_config()
    if gid in cfg["source_groups"]:
        return await update.message.reply_text("⚠️ Already added.")
    cfg["source_groups"].append(gid)
    save_config(cfg)
    await update.message.reply_text(f"✅ Source added: {gid}")

async def remove_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /removesource <group_id>")
    gid = context.args[0]
    cfg = load_config()
    if gid not in cfg["source_groups"]:
        return await update.message.reply_text("⚠️ Not found.")
    cfg["source_groups"].remove(gid)
    save_config(cfg)
    await update.message.reply_text(f"🗑️ Source removed: {gid}")

async def add_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /addtarget <group_id>")
    gid = context.args[0]
    cfg = load_config()
    if gid in cfg["target_groups"]:
        return await update.message.reply_text("⚠️ Already added.")
    cfg["target_groups"].append(gid)
    save_config(cfg)
    await update.message.reply_text(f"✅ Target added: {gid}")

async def remove_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /removetarget <group_id>")
    gid = context.args[0]
    cfg = load_config()
    if gid not in cfg["target_groups"]:
        return await update.message.reply_text("⚠️ Not found.")
    cfg["target_groups"].remove(gid)
    save_config(cfg)
    await update.message.reply_text(f"🗑️ Target removed: {gid}")

async def set_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        return await update.message.reply_text("⚠️ Usage: /setdelay <min> <max>")
    try:
        mn, mx = int(context.args[0]), int(context.args[1])
        cfg = load_config()
        cfg["delay_min"] = mn
        cfg["delay_max"] = mx
        save_config(cfg)
        await update.message.reply_text(f"⏱️ Delay set to {mn}-{mx}s.")
    except Exception:
        await update.message.reply_text("⚠️ Invalid format. Example: /setdelay 10 20")

async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    if cfg["is_adding"]:
        return await update.message.reply_text("⚠️ Already running.")
    if not cfg["source_groups"] or not cfg["target_groups"]:
        return await update.message.reply_text("⚠️ Add at least one source and one target.")
    cfg["is_adding"] = True
    save_config(cfg)
    await update.message.reply_text("🚀 Starting member adding (demo mode).")

async def stop_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    if not cfg["is_adding"]:
        return await update.message.reply_text("Already stopped.")
    cfg["is_adding"] = False
    save_config(cfg)
    await update.message.reply_text("🛑 Adding stopped manually.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    await update.message.reply_text(
        f"📊 Status: {'🟢 Adding' if cfg['is_adding'] else '🔴 Idle'}\n"
        f"👥 Sources: {safe_list_str(cfg['source_groups'])}\n"
        f"🎯 Targets: {safe_list_str(cfg['target_groups'])}\n"
        f"⏱️ Delay: {cfg['delay_min']}-{cfg['delay_max']} sec"
    )

async def all_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    await update.message.reply_text(json.dumps(cfg, indent=2))

# ---------- Ping Loop ----------
PING_INTERVAL = 600  # 10 minutes
SELF_URL = "https://instaautomation-oe30.onrender.com"  # your URL

async def ping_loop():
    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            try:
                r = await client.get(SELF_URL)
                logger.info("🌐 Pinged %s | status %s", SELF_URL, r.status_code)
            except Exception as e:
                logger.warning("⚠️ Ping failed: %s", e)
            await asyncio.sleep(PING_INTERVAL)

async def on_startup(app):
    asyncio.create_task(ping_loop())
    logger.info("✅ Ping task started (every 10min → %s)", SELF_URL)

# ---------- Main ----------
if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN missing in environment!")
        exit(1)

    logger.info("🤖 Starting Controller Bot...")
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("addsource", add_source))
    app.add_handler(CommandHandler("removesource", remove_source))
    app.add_handler(CommandHandler("addtarget", add_target))
    app.add_handler(CommandHandler("removetarget", remove_target))
    app.add_handler(CommandHandler("setdelay", set_delay))
    app.add_handler(CommandHandler("startadd", start_add))
    app.add_handler(CommandHandler("stopadd", stop_add))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("all", all_settings))

    app.run_polling()
