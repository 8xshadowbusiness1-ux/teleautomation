#!/usr/bin/env python3
import os, json, logging, asyncio, httpx
from telethon import TelegramClient, errors
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# -------------------------------------------------------------------
# CONFIG
CONFIG_FILE = "bot_config.json"
PING_URL = "https://teleautomation-1.onrender.com"  # replace with your Render URL
# -------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("controller")

# Ensure clean flags at startup
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r+") as f:
        cfg = json.load(f)
        cfg["is_adding"] = False
        if "logged_in" not in cfg:
            cfg["logged_in"] = False
        f.seek(0)
        json.dump(cfg, f, indent=2)
        f.truncate()


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


# -------------------------------------------------------------------
# LOGIN SYSTEM
# -------------------------------------------------------------------

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send login code"""
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])

    try:
        await client.connect()
        if await client.is_user_authorized():
            cfg["logged_in"] = True
            save_config(cfg)
            await update.message.reply_text("✅ Already logged in!")
            await client.disconnect()
            return

        result = await client.send_code_request(cfg["phone"])
        cfg["phone_code_hash"] = result.phone_code_hash  # store OTP hash
        save_config(cfg)

        await update.message.reply_text("📲 OTP sent! Please enter it using /otp <code>")
        await client.disconnect()

    except Exception as e:
        await update.message.reply_text(f"❌ Login failed: {e}")
        logger.error(f"Login error: {e}")
        await client.disconnect()


async def otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify OTP"""
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /otp 12345")

    code = context.args[0]
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])

    try:
        await client.connect()
        if "phone_code_hash" not in cfg:
            await update.message.reply_text("⚠️ Please run /login first.")
            await client.disconnect()
            return

        await client.sign_in(
            phone=cfg["phone"],
            code=code,
            phone_code_hash=cfg["phone_code_hash"]
        )
        cfg["logged_in"] = True
        cfg.pop("phone_code_hash", None)
        save_config(cfg)

        await update.message.reply_text("✅ Login successful!")
        await client.disconnect()

    except errors.SessionPasswordNeededError:
        await update.message.reply_text("⚠️ 2FA enabled! Use /2fa <password>")
        await client.disconnect()
    except Exception as e:
        await update.message.reply_text(f"❌ OTP error: {e}")
        logger.error(f"OTP error: {e}")
        await client.disconnect()


async def twofa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 2FA login"""
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /2fa <password>")

    password = " ".join(context.args)
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])

    try:
        await client.connect()
        await client.sign_in(password=password)
        cfg["logged_in"] = True
        save_config(cfg)
        await update.message.reply_text("✅ 2FA login successful!")
        await client.disconnect()
    except Exception as e:
        await update.message.reply_text(f"❌ 2FA error: {e}")
        logger.error(f"2FA error: {e}")
        await client.disconnect()


# -------------------------------------------------------------------
# CORE COMMANDS
# -------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Telegram Adder Bot Ready!\n\n"
        "🧩 Commands:\n"
        "/login – send OTP\n"
        "/otp <code> – verify OTP\n"
        "/2fa <password> – 2-step verification\n"
        "/status – show status\n"
        "/addsource <group_id>\n"
        "/addtarget <group_id>\n"
        "/removesource <group_id>\n"
        "/removetarget <group_id>\n"
        "/startadd – start adding members\n"
        "/stopadd – stop adding\n"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    msg = (
        f"🔐 Logged In: {'✅' if cfg.get('logged_in') else '❌'}\n"
        f"⚙️ Adding: {'✅' if cfg.get('is_adding') else '❌'}\n"
        f"📤 Sources: {cfg.get('source_groups', [])}\n"
        f"📥 Targets: {cfg.get('target_groups', [])}"
    )
    await update.message.reply_text(msg)


async def addsource(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /addsource -100xxxxx")
    cfg = load_config()
    src = context.args[0]
    if src not in cfg["source_groups"]:
        cfg["source_groups"].append(src)
        save_config(cfg)
        await update.message.reply_text(f"✅ Source added: {src}")
    else:
        await update.message.reply_text("⚠️ Already added!")


async def addtarget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /addtarget -100xxxxx")
    cfg = load_config()
    tgt = context.args[0]
    if tgt not in cfg["target_groups"]:
        cfg["target_groups"].append(tgt)
        save_config(cfg)
        await update.message.reply_text(f"✅ Target added: {tgt}")
    else:
        await update.message.reply_text("⚠️ Already added!")


async def removesource(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /removesource -100xxxxx")
    cfg = load_config()
    src = context.args[0]
    if src in cfg["source_groups"]:
        cfg["source_groups"].remove(src)
        save_config(cfg)
        await update.message.reply_text(f"🗑️ Removed source: {src}")
    else:
        await update.message.reply_text("⚠️ Source not found!")


async def removetarget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /removetarget -100xxxxx")
    cfg = load_config()
    tgt = context.args[0]
    if tgt in cfg["target_groups"]:
        cfg["target_groups"].remove(tgt)
        save_config(cfg)
        await update.message.reply_text(f"🗑️ Removed target: {tgt}")
    else:
        await update.message.reply_text("⚠️ Target not found!")


async def startadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    if not cfg.get("logged_in"):
        return await update.message.reply_text("⚠️ Please login first using /login + /otp")

    if cfg.get("is_adding"):
        return await update.message.reply_text("⚙️ Already running!")

    cfg["is_adding"] = True
    save_config(cfg)
    os.system("nohup python3 worker_add.py &")
    await update.message.reply_text("🚀 Adding started!")


async def stopadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    cfg["is_adding"] = False
    save_config(cfg)
    await update.message.reply_text("🛑 Adding stopped!")


# -------------------------------------------------------------------
# KEEP-ALIVE PING
# -------------------------------------------------------------------

async def keep_alive():
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(PING_URL)
                logger.info(f"🌐 Pinged {PING_URL} | {r.status_code}")
        except Exception as e:
            logger.warning(f"Ping failed: {e}")
        await asyncio.sleep(600)  # every 10 min


# -------------------------------------------------------------------
# MAIN BOT RUN
# -------------------------------------------------------------------

if __name__ == "__main__":
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("❌ BOT_TOKEN missing in environment variables!")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("otp", otp))
    app.add_handler(CommandHandler("2fa", twofa))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("addsource", addsource))
    app.add_handler(CommandHandler("addtarget", addtarget))
    app.add_handler(CommandHandler("removesource", removesource))
    app.add_handler(CommandHandler("removetarget", removetarget))
    app.add_handler(CommandHandler("startadd", startadd))
    app.add_handler(CommandHandler("stopadd", stopadd))

    logger.info("🚀 Controller bot (with full login system) started.")
    asyncio.get_event_loop().create_task(keep_alive())
    app.run_polling()
