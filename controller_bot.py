#!/usr/bin/env python3
import os, json, logging, asyncio, httpx
from telethon import TelegramClient, errors
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

CONFIG_FILE = "bot_config.json"
PING_URL = "https://teleautomation-by9o.onrender.com"  # your Render URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("controller")

# -------------------- CONFIG HELPERS --------------------
def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

# -------------------- LOGIN SYSTEM --------------------
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()
    try:
        if await client.is_user_authorized():
            cfg["logged_in"] = True
            save_config(cfg)
            await update.message.reply_text("✅ Already logged in!")
        else:
            result = await client.send_code_request(cfg["phone"])
            cfg["phone_code_hash"] = result.phone_code_hash
            save_config(cfg)
            await update.message.reply_text("📲 OTP sent! Use /otp <code>")
    except Exception as e:
        await update.message.reply_text(f"❌ Login failed: {e}")
        logger.error(e)
    await client.disconnect()

async def otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /otp 12345")
    cfg = load_config()
    code = context.args[0]
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()
    try:
        await client.sign_in(
            phone=cfg["phone"],
            code=code,
            phone_code_hash=cfg.get("phone_code_hash", "")
        )
        cfg["logged_in"] = True
        cfg.pop("phone_code_hash", None)
        save_config(cfg)
        await update.message.reply_text("✅ Login successful!")
    except errors.SessionPasswordNeededError:
        await update.message.reply_text("⚠️ 2FA enabled! Use /2fa <password>")
    except Exception as e:
        await update.message.reply_text(f"❌ OTP error: {e}")
        logger.error(e)
    await client.disconnect()

async def twofa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /2fa <password>")
    cfg = load_config()
    password = " ".join(context.args)
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()
    try:
        await client.sign_in(password=password)
        cfg["logged_in"] = True
        save_config(cfg)
        await update.message.reply_text("✅ 2FA login successful!")
    except Exception as e:
        await update.message.reply_text(f"❌ 2FA error: {e}")
        logger.error(e)
    await client.disconnect()

# -------------------- COMMANDS --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot Active!\n\nCommands:\n"
        "/login – Send OTP\n"
        "/otp <code> – Verify login\n"
        "/2fa <pass> – Two-step login\n"
        "/status – Show current status\n"
        "/addsource <id> – Add source group\n"
        "/addtarget <id> – Add target group\n"
        "/setdelay <min> <max> – Change add delay (seconds)\n"
        "/startadd – Start worker\n"
        "/stopadd – Stop worker"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    msg = (
        f"🔐 Logged In: {'✅' if cfg['logged_in'] else '❌'}\n"
        f"⚙️ Adding: {'✅' if cfg['is_adding'] else '❌'}\n"
        f"📤 Sources: {cfg.get('source_groups', [])}\n"
        f"📥 Targets: {cfg.get('target_groups', [])}\n"
        f"⏱ Delay: {cfg.get('delay_min')}–{cfg.get('delay_max')} sec"
    )
    await update.message.reply_text(msg)

async def addsource(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("⚠️ Usage: /addsource -100xxxx")
    cfg = load_config()
    src = context.args[0]
    if src not in cfg.get("source_groups", []):
        cfg.setdefault("source_groups", []).append(src)
        save_config(cfg)
        await update.message.reply_text(f"✅ Source added: {src}")
    else:
        await update.message.reply_text("⚠️ Already added!")

async def addtarget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("⚠️ Usage: /addtarget -100xxxx")
    cfg = load_config()
    tgt = context.args[0]
    if tgt not in cfg.get("target_groups", []):
        cfg.setdefault("target_groups", []).append(tgt)
        save_config(cfg)
        await update.message.reply_text(f"✅ Target added: {tgt}")
    else:
        await update.message.reply_text("⚠️ Already added!")

async def setdelay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        return await update.message.reply_text("⚠️ Usage: /setdelay <min> <max>")
    try:
        dmin, dmax = map(int, context.args)
    except:
        return await update.message.reply_text("⚠️ Enter valid numbers.")
    cfg = load_config()
    cfg["delay_min"], cfg["delay_max"] = dmin, dmax
    save_config(cfg)
    await update.message.reply_text(f"✅ Delay set to {dmin}-{dmax} sec")

async def startadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    if not cfg.get("logged_in"): return await update.message.reply_text("⚠️ Please login first.")
    if cfg.get("is_adding"): return await update.message.reply_text("⚙️ Already running.")
    cfg["is_adding"] = True
    save_config(cfg)
    os.system("nohup python3 worker_add.py &")
    await update.message.reply_text("🚀 Worker started!")

async def stopadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    cfg["is_adding"] = False
    save_config(cfg)
    await update.message.reply_text("🛑 Worker stopped!")

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
    app = ApplicationBuilder().token(token).build()
    handlers = [
        CommandHandler("start", start),
        CommandHandler("login", login),
        CommandHandler("otp", otp),
        CommandHandler("2fa", twofa),
        CommandHandler("status", status),
        CommandHandler("addsource", addsource),
        CommandHandler("addtarget", addtarget),
        CommandHandler("setdelay", setdelay),
        CommandHandler("startadd", startadd),
        CommandHandler("stopadd", stopadd)
    ]
    for h in handlers: app.add_handler(h)
    logger.info("🚀 Controller running...")
    asyncio.get_event_loop().create_task(keep_alive())
    app.run_polling()
