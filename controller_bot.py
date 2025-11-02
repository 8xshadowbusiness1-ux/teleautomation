#!/usr/bin/env python3
import os, json, logging, asyncio, httpx
from telethon import TelegramClient, errors
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

CONFIG_FILE = "bot_config.json"
PING_URL = "https://instaautomation-oe30.onrender.com"  # replace with your Render URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("controller")

# Reset flags on boot
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


# -------------------- LOGIN SYSTEM --------------------
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send login code"""
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])

    try:
        await client.connect()
        if await client.is_user_authorized():
            await update.message.reply_text("✅ Already logged in!")
            cfg["logged_in"] = True
            save_config(cfg)
            await client.disconnect()
            return

        await client.send_code_request(cfg["phone"])
        await update.message.reply_text("📲 OTP sent! Please enter using /otp <code>")
        save_config(cfg)
        await client.disconnect()

    except Exception as e:
        await update.message.reply_text(f"❌ Login failed: {e}")
        logger.error(e)
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
        await client.sign_in(phone=cfg["phone"], code=code)
        await update.message.reply_text("✅ Login successful!")
        cfg["logged_in"] = True
        save_config(cfg)
        await client.disconnect()
    except errors.SessionPasswordNeededError:
        await update.message.reply_text("⚠️ 2FA enabled! Use /2fa <password>")
        await client.disconnect()
    except Exception as e:
        await update.message.reply_text(f"❌ OTP error: {e}")
        logger.error(e)
        await client.disconnect()


async def twofa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """2FA password login"""
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /2fa <your_password>")

    password = " ".join(context.args)
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])

    try:
        await client.connect()
        await client.sign_in(password=password)
        await update.message.reply_text("✅ 2FA login successful!")
        cfg["logged_in"] = True
        save_config(cfg)
        await client.disconnect()
    except Exception as e:
        await update.message.reply_text(f"❌ 2FA error: {e}")
        logger.error(e)
        await client.disconnect()


# -------------------- CORE COMMANDS --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Controller Ready!\n\n"
        "🧩 Commands:\n"
        "/login – send OTP\n"
        "/otp <code> – verify OTP\n"
        "/2fa <pass> – handle two-step\n"
        "/status – check status\n"
        "/addsource <id>\n"
        "/addtarget <id>\n"
        "/removesource <id>\n"
        "/removetarget <id>\n"
        "/startadd – begin adding\n"
        "/stopadd – stop adding"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    msg = (
        f"🔐 Logged In: {'✅' if cfg.get('logged_in') else '❌'}\n"
        f"➕ Adding: {'✅' if cfg.get('is_adding') else '❌'}\n"
        f"📤 Sources: {cfg.get('source_groups', [])}\n"
        f"📥 Targets: {cfg.get('target_groups', [])}"
    )
    await update.message.reply_text(msg)


async def addsource(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /addsource -100xxxx")
    cfg = load_config()
    src = context.args[0]
    if src not in cfg["source_groups"]:
        cfg["source_groups"].append(src)
        save_config(cfg)
        await update.message.reply_text(f"✅ Source added: {src}")
    else:
        await update.message.reply_text("⚠️ Already added.")


async def addtarget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /addtarget -100xxxx")
    cfg = load_config()
    tgt = context.args[0]
    if tgt not in cfg["target_groups"]:
        cfg["target_groups"].append(tgt)
        save_config(cfg)
        await update.message.reply_text(f"✅ Target added: {tgt}")
    else:
        await update.message.reply_text("⚠️ Already added.")


async def startadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    if not cfg.get("logged_in"):
        return await update.message.reply_text("⚠️ Please login first using /login + /otp")

    if cfg.get("is_adding"):
        return await update.message.reply_text("⚠️ Already running!")

    cfg["is_adding"] = True
    save_config(cfg)
    os.system("nohup python3 worker_add.py &")
    await update.message.reply_text("🚀 Adding started!")


async def stopadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    cfg["is_adding"] = False
    save_config(cfg)
    await update.message.reply_text("🛑 Adding stopped!")


# -------------------- KEEP ALIVE --------------------
async def keep_alive():
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(PING_URL)
                logger.info(f"🌐 Pinged {PING_URL} | {r.status_code}")
        except Exception as e:
            logger.warning(f"Ping failed: {e}")
        await asyncio.sleep(600)


# -------------------- MAIN --------------------
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
    app.add_handler(CommandHandler("startadd", startadd))
    app.add_handler(CommandHandler("stopadd", stopadd))

    logger.info("🚀 Controller bot (with login system) started.")
    asyncio.get_event_loop().create_task(keep_alive())
    app.run_polling()
