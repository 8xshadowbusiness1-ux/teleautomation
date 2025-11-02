#!/usr/bin/env python3
import os, json, logging, asyncio, httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

CONFIG_FILE = "bot_config.json"
PING_URL = "https://instaautomation-oe30.onrender.com"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("controller")

# Reset flags on each boot
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r+") as f:
        cfg = json.load(f)
        cfg["logged_in"] = False
        cfg["is_adding"] = False
        f.seek(0)
        json.dump(cfg, f, indent=2)
        f.truncate()


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Telegram Automation Controller Ready!\nUse /login, /otp, /status, /startadd, /stopadd, /addsource, /addtarget.")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    msg = (
        f"🔐 Logged In: {'✅' if cfg.get('logged_in') else '❌'}\n"
        f"➕ Adding: {'✅' if cfg.get('is_adding') else '❌'}\n"
        f"📤 Source Groups: {cfg.get('source_groups', [])}\n"
        f"📥 Target Groups: {cfg.get('target_groups', [])}"
    )
    await update.message.reply_text(msg)


async def addsource(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /addsource -1001234567890")
    cfg = load_config()
    src = context.args[0]
    if src not in cfg["source_groups"]:
        cfg["source_groups"].append(src)
        save_config(cfg)
        await update.message.reply_text(f"✅ Added source group: {src}")
    else:
        await update.message.reply_text("⚠️ Already added!")


async def addtarget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /addtarget -1009876543210")
    cfg = load_config()
    tgt = context.args[0]
    if tgt not in cfg["target_groups"]:
        cfg["target_groups"].append(tgt)
        save_config(cfg)
        await update.message.reply_text(f"✅ Added target group: {tgt}")
    else:
        await update.message.reply_text("⚠️ Already added!")


async def removetarget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /removetarget -100xxxxx")
    cfg = load_config()
    tgt = context.args[0]
    if tgt in cfg["target_groups"]:
        cfg["target_groups"].remove(tgt)
        save_config(cfg)
        await update.message.reply_text(f"🗑️ Removed target group: {tgt}")
    else:
        await update.message.reply_text("⚠️ Target not found!")


async def removesource(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /removesource -100xxxxx")
    cfg = load_config()
    src = context.args[0]
    if src in cfg["source_groups"]:
        cfg["source_groups"].remove(src)
        save_config(cfg)
        await update.message.reply_text(f"🗑️ Removed source group: {src}")
    else:
        await update.message.reply_text("⚠️ Source not found!")


async def startadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    if cfg.get("is_adding"):
        if not os.path.exists(f"{cfg['session_name']}.session"):
            cfg["is_adding"] = False
            save_config(cfg)
        else:
            return await update.message.reply_text("⚠️ Already running!")
    cfg["is_adding"] = True
    save_config(cfg)
    os.system("nohup python3 worker_add.py &")
    await update.message.reply_text("🚀 Adding process started!")


async def stopadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    cfg["is_adding"] = False
    save_config(cfg)
    await update.message.reply_text("🛑 Adding stopped!")


# Ping loop to keep alive
async def keep_alive():
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(PING_URL)
                logger.info(f"🌐 Pinged {PING_URL} | {r.status_code}")
        except Exception as e:
            logger.warning(f"Ping failed: {e}")
        await asyncio.sleep(600)  # every 10 min


if __name__ == "__main__":
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("addsource", addsource))
    app.add_handler(CommandHandler("addtarget", addtarget))
    app.add_handler(CommandHandler("removesource", removesource))
    app.add_handler(CommandHandler("removetarget", removetarget))
    app.add_handler(CommandHandler("startadd", startadd))
    app.add_handler(CommandHandler("stopadd", stopadd))

    logger.info("🚀 Controller bot (with fixes) started.")
    asyncio.get_event_loop().create_task(keep_alive())
    app.run_polling()
