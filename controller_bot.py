#!/usr/bin/env python3
import os, json, logging, asyncio, httpx
from telethon import TelegramClient, errors
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

CONFIG_FILE = "bot_config.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("controller")


# ------------------ CONFIG HELPERS ------------------
def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


# ------------------ LOGIN FLOW ------------------
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    phone = cfg.get("phone")

    if not phone or not isinstance(phone, str) or not phone.startswith("+"):
        return await update.message.reply_text("⚠️ Invalid phone number in config (use +91...).")

    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()

    try:
        if await client.is_user_authorized():
            cfg["logged_in"] = True
            save_config(cfg)
            await update.message.reply_text("✅ Already logged in!")
            return

        result = await client.send_code_request(phone)
        if not result or not getattr(result, "phone_code_hash", None):
            raise ValueError("No phone_code_hash returned from Telegram API.")

        cfg["phone_code_hash"] = result.phone_code_hash
        save_config(cfg)
        await update.message.reply_text("📲 OTP sent! Use /otp <code>")
    except Exception as e:
        await update.message.reply_text(f"❌ Login failed: {e}")
        logger.error(e)
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
        logger.error(e)
    finally:
        await client.disconnect()


# ------------------ COMMANDS ------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 Telegram Automation Bot Ready!\n\n"
        "Commands:\n"
        "/login – Send OTP\n"
        "/otp <code> – Verify OTP\n"
        "/2fa <pass> – Complete 2FA login\n"
        "/status – Show status\n"
        "/addsource <group_id>\n"
        "/addtarget <group_id>\n"
        "/setdelay <min> <max>\n"
        "/startadd – Start worker\n"
        "/stopadd – Stop worker\n"
        "/workerstatus – Check worker progress"
    )
    await update.message.reply_text(text)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    msg = (
        f"🔐 Logged In: {'✅' if cfg.get('logged_in') else '❌'}\n"
        f"⚙️ Adding: {'✅' if cfg.get('is_adding') else '❌'}\n"
        f"📤 Sources: {cfg.get('source_groups', [])}\n"
        f"📥 Targets: {cfg.get('target_groups', [])}\n"
        f"⏱ Delay: {cfg.get('delay_min', 15)}–{cfg.get('delay_max', 30)} sec"
    )
    await update.message.reply_text(msg)


async def addsource(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /addsource -100xxxx")
    cfg = load_config()
    src = context.args[0]
    if src not in cfg.get("source_groups", []):
        cfg.setdefault("source_groups", []).append(src)
        save_config(cfg)
        await update.message.reply_text(f"✅ Source added: {src}")
    else:
        await update.message.reply_text("⚠️ Already added!")


async def addtarget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /addtarget -100xxxx")
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
        if dmin <= 0 or dmax <= 0 or dmin > dmax:
            return await update.message.reply_text("⚠️ Invalid delay range.")
    except:
        return await update.message.reply_text("⚠️ Enter valid numbers.")
    cfg = load_config()
    cfg["delay_min"], cfg["delay_max"] = dmin, dmax
    save_config(cfg)
    await update.message.reply_text(f"✅ Delay set: {dmin}–{dmax} sec")


async def startadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    if not cfg.get("logged_in"):
        return await update.message.reply_text("⚠️ Login first via /login + /otp")
    if cfg.get("is_adding"):
        return await update.message.reply_text("⚙️ Already running.")
    cfg["is_adding"] = True
    save_config(cfg)
    os.system("nohup python3 worker_bot.py &")
    await update.message.reply_text("🚀 Adding started!")


async def stopadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    cfg["is_adding"] = False
    save_config(cfg)
    await update.message.reply_text("🛑 Adding stopped!")


async def workerstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists("progress.json"):
        return await update.message.reply_text("⚠️ Worker not active or no progress found.")
    data = json.load(open("progress.json"))
    msg = (
        f"📊 Worker Status:\n"
        f"Source: {data.get('source')}\n"
        f"Target: {data.get('target')}\n"
        f"✅ Added: {data.get('added', 0)} members\n"
        f"⏱ Delay: {data.get('delay_min')}–{data.get('delay_max')}s\n"
        f"💓 Uptime: {data.get('uptime', '?')}"
    )
    await update.message.reply_text(msg)


# ------------------ KEEP ALIVE ------------------
async def keep_alive():
    cfg = load_config()
    ping_url = cfg.get("PING_URL")
    while True:
        await asyncio.sleep(600)
        try:
            if ping_url:
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.get(ping_url)
                    logger.info(f"💓 Ping {ping_url} | {r.status_code}")
            else:
                logger.info("💓 Heartbeat running.")
        except Exception as e:
            logger.warning(f"Ping failed: {e}")


# ------------------ MAIN ------------------
if __name__ == "__main__":
    token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("otp", otp))
    app.add_handler(CommandHandler("2fa", twofa))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("addsource", addsource))
    app.add_handler(CommandHandler("addtarget", addtarget))
    app.add_handler(CommandHandler("setdelay", setdelay))
    app.add_handler(CommandHandler("startadd", startadd))
    app.add_handler(CommandHandler("stopadd", stopadd))
    app.add_handler(CommandHandler("workerstatus", workerstatus))

    logger.info("🚀 Controller started.")
    asyncio.get_event_loop().create_task(keep_alive())
    app.run_polling()
