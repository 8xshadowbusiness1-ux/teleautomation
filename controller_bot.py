#!/usr/bin/env python3
import os, json, asyncio, random, logging, httpx, subprocess
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------------------- SETUP ----------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("controller_bot")

CONFIG_FILE = "bot_config.json"
SELF_URL = "https://instaautomation-oe30.onrender.com"  # change to your Render URL
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

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(default_config)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

config = load_config()

# ---------------------- TELETHON LOGIN ----------------------
client = TelegramClient(config["session_name"], config["api_id"], config["api_hash"])

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send OTP"""
    try:
        await update.message.reply_text("📲 Sending OTP to your Telegram account...")
        await client.connect()

        if await client.is_user_authorized():
            config["logged_in"] = True
            save_config(config)
            return await update.message.reply_text("✅ Already logged in!")

        await client.send_code_request(config["phone"])
        await update.message.reply_text("📩 OTP sent! Use /otp <code> to verify.")
    except Exception as e:
        await update.message.reply_text(f"❌ OTP send failed: {e}")

async def otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify OTP"""
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /otp <code>")
    code = context.args[0]
    try:
        await client.connect()
        await client.sign_in(config["phone"], code)
        if not await client.is_user_authorized():
            return await update.message.reply_text("❌ Invalid or expired OTP.")
        config["logged_in"] = True
        save_config(config)
        await update.message.reply_text("✅ Logged in successfully!")
    except SessionPasswordNeededError:
        await update.message.reply_text("🔐 2FA enabled. Use /pass <password>")
    except Exception as e:
        await update.message.reply_text(f"❌ Login error: {e}")

async def passwd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Two-step password"""
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /pass <password>")
    password = " ".join(context.args)
    try:
        await client.sign_in(password=password)
        if await client.is_user_authorized():
            config["logged_in"] = True
            save_config(config)
            await update.message.reply_text("✅ 2-Step verification successful!")
        else:
            await update.message.reply_text("❌ Incorrect password.")
    except Exception as e:
        await update.message.reply_text(f"❌ Password error: {e}")

# ---------------------- CONTROLLER COMMANDS ----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Telegram Automation Controller*\n\n"
        "🔐 Login & Auth:\n"
        "/login - Send OTP\n"
        "/otp <code> - Verify code\n"
        "/pass <password> - 2-Step verification\n\n"
        "⚙️ Control:\n"
        "/addsource <group>\n"
        "/removesource <group>\n"
        "/addtarget <group>\n"
        "/removetarget <group>\n"
        "/setdelay <min> <max>\n"
        "/startadd\n"
        "/stopadd\n"
        "/status\n"
        "/all",
        parse_mode="Markdown"
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
        await update.message.reply_text(f"🗑 Removed source: {gid}")
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
        await update.message.reply_text(f"🗑 Removed target: {gid}")
    else:
        await update.message.reply_text("⚠️ Not found.")

async def set_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /setdelay <min> <max>")
    mn, mx = map(int, context.args)
    cfg = load_config()
    cfg["delay_min"], cfg["delay_max"] = mn, mx
    save_config(cfg)
    await update.message.reply_text(f"⏱ Delay set to {mn}-{mx} sec")

async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    if not cfg["logged_in"]:
        return await update.message.reply_text("❌ Not logged in. Use /login first.")
    if cfg["is_adding"]:
        return await update.message.reply_text("⚠ Already running.")
    cfg["is_adding"] = True
    save_config(cfg)
    subprocess.Popen(["python3", "worker_add.py"])
    await update.message.reply_text("🟢 Started background adding process.")

async def stop_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    cfg["is_adding"] = False
    save_config(cfg)
    await update.message.reply_text("🔴 Adding stopped.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    msg = (
        f"📊 *Status*\n"
        f"Sources: {cfg['source_groups']}\n"
        f"Targets: {cfg['target_groups']}\n"
        f"Delay: {cfg['delay_min']}-{cfg['delay_max']} sec\n"
        f"Adding: {'🟢 ON' if cfg['is_adding'] else '🔴 OFF'}\n"
        f"Logged In: {'✅' if cfg['logged_in'] else '❌'}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def all_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(json.dumps(load_config(), indent=2))

# ---------------------- PING ----------------------
async def ping_loop():
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            try:
                r = await client.get(SELF_URL)
                logger.info(f"🌐 Pinged {SELF_URL} | {r.status_code}")
            except Exception as e:
                logger.warning(f"⚠ Ping failed: {e}")
            await asyncio.sleep(PING_INTERVAL)

async def on_startup(app):
    asyncio.create_task(ping_loop())
    logger.info("✅ Ping task started every 5 min → %s", SELF_URL)

# ---------------------- START BOT ----------------------
if __name__ == "__main__":
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN missing in environment!")
        exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("otp", otp))
    app.add_handler(CommandHandler("pass", passwd))
    app.add_handler(CommandHandler("addsource", add_source))
    app.add_handler(CommandHandler("removesource", remove_source))
    app.add_handler(CommandHandler("addtarget", add_target))
    app.add_handler(CommandHandler("removetarget", remove_target))
    app.add_handler(CommandHandler("setdelay", set_delay))
    app.add_handler(CommandHandler("startadd", start_add))
    app.add_handler(CommandHandler("stopadd", stop_add))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("all", all_settings))

    logger.info("🚀 Controller bot (with login system) started.")
    app.run_polling()
