#!/usr/bin/env python3
import asyncio, json, logging, os, httpx, nest_asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telethon import TelegramClient, errors

CONFIG_FILE = "bot_config.json"
PING_URL = "https://your-render-url.onrender.com"  # replace with your Render URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("controller")

# ---------- CONFIG HELPERS ----------
def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

# ---------- LOGIN SYSTEM ----------
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()
    try:
        if await client.is_user_authorized():
            cfg["logged_in"] = True
            save_config(cfg)
            await update.message.reply_text("✅ Already logged in.")
        else:
            result = await client.send_code_request(cfg["phone"])
            cfg["phone_code_hash"] = result.phone_code_hash
            save_config(cfg)
            await update.message.reply_text("📲 OTP sent! Use /otp <code>")
    except Exception as e:
        await update.message.reply_text(f"❌ Login failed: {e}")
    finally:
        await client.disconnect()

async def otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /otp 12345")

    code = context.args[0]
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()
    try:
        await client.sign_in(cfg["phone"], code, cfg.get("phone_code_hash", ""))
        cfg["logged_in"] = True
        cfg.pop("phone_code_hash", None)
        save_config(cfg)
        await update.message.reply_text("✅ Login successful!")
    except errors.SessionPasswordNeededError:
        await update.message.reply_text("⚠️ 2FA enabled! Use /2fa <password>")
    except Exception as e:
        await update.message.reply_text(f"❌ OTP error: {e}")
    finally:
        await client.disconnect()

async def twofa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /2fa <password>")
    password = " ".join(context.args)
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()
    try:
        await client.sign_in(password=password)
        cfg["logged_in"] = True
        save_config(cfg)
        await update.message.reply_text("✅ 2FA login successful!")
    except Exception as e:
        await update.message.reply_text(f"❌ 2FA error: {e}")
    finally:
        await client.disconnect()

# ---------- BOT COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Telegram Adder Controller\n\n"
        "/login – Send OTP\n"
        "/otp <code> – Verify login\n"
        "/2fa <password> – 2-Step Auth\n"
        "/setdelay <min> <max> – Set add delay\n"
        "/status – Show bot status\n"
        "/startadd – Begin adding\n"
        "/stopadd – Stop adding"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    msg = (
        f"🔐 Logged In: {'✅' if cfg.get('logged_in') else '❌'}\n"
        f"⚙️ Adding: {'✅' if cfg.get('is_adding') else '❌'}\n"
        f"⏱ Delay: {cfg.get('delay_min', 15)}–{cfg.get('delay_max', 30)} sec\n"
        f"📤 Sources: {cfg.get('source_groups', [])}\n"
        f"📥 Targets: {cfg.get('target_groups', [])}"
    )
    await update.message.reply_text(msg)

async def setdelay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        return await update.message.reply_text("⚠️ Usage: /setdelay <min> <max>")
    try:
        dmin, dmax = map(int, context.args)
        cfg = load_config()
        cfg["delay_min"], cfg["delay_max"] = dmin, dmax
        save_config(cfg)
        await update.message.reply_text(f"✅ Delay updated: {dmin}–{dmax}s")
    except:
        await update.message.reply_text("❌ Invalid input. Use numbers only.")

async def startadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    if not cfg.get("logged_in"):
        return await update.message.reply_text("⚠️ Please login first.")
    if cfg.get("is_adding"):
        return await update.message.reply_text("⚙️ Already running.")
    cfg["is_adding"] = True
    save_config(cfg)
    os.system("nohup python3 worker_bot.py &")
    await update.message.reply_text("🚀 Worker started!")

async def stopadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    cfg["is_adding"] = False
    save_config(cfg)
    await update.message.reply_text("🛑 Worker stopped.")

# ---------- KEEP-ALIVE ----------
async def keep_alive():
    while True:
        try:
            async with httpx.AsyncClient() as c:
                await c.get(PING_URL)
                logger.info("💓 Ping OK (keep alive)")
        except Exception as e:
            logger.warning(f"Ping failed: {e}")
        await asyncio.sleep(600)

# ---------- MAIN ----------
async def main():
    nest_asyncio.apply()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("❌ BOT_TOKEN missing!")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("otp", otp))
    app.add_handler(CommandHandler("2fa", twofa))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("setdelay", setdelay))
    app.add_handler(CommandHandler("startadd", startadd))
    app.add_handler(CommandHandler("stopadd", stopadd))

    logger.info("🚀 Controller started (with keep-alive + delay control)")
    asyncio.create_task(keep_alive())
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
