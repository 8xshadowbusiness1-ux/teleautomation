#!/usr/bin/env python3
import asyncio
import json
import logging
import os
import httpx
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from telethon import TelegramClient, errors

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("controller")

CONFIG_PATH = "bot_config.json"
PROGRESS_PATH = "progress.json"

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)

# ---------------- LOGIN FLOW ----------------
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()
    try:
        if await client.is_user_authorized():
            cfg["logged_in"] = True
            save_config(cfg)
            await update.message.reply_text("✅ Already logged in.")
            return

        phone = cfg["phone"]
        res = await client.send_code_request(phone)
        # save phone_code_hash so /otp can use it
        cfg["phone_code_hash"] = getattr(res, "phone_code_hash", "")
        save_config(cfg)
        await update.message.reply_text("📲 OTP sent! Use /otp <code>")
    except Exception as e:
        logger.exception("Login error")
        await update.message.reply_text(f"❌ Login failed: {e}")
    finally:
        await client.disconnect()

async def otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /otp <code>")

    code = context.args[0]
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()
    try:
        phone = cfg["phone"]
        phone_code_hash = cfg.get("phone_code_hash", "")
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        cfg["logged_in"] = True
        cfg.pop("phone_code_hash", None)
        save_config(cfg)
        await update.message.reply_text("✅ OTP verified — logged in.")
    except errors.SessionPasswordNeededError:
        await update.message.reply_text("⚠️ 2FA required. Use /2fa <password>")
    except Exception as e:
        logger.exception("OTP error")
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
        await update.message.reply_text("✅ 2FA login successful.")
    except Exception as e:
        logger.exception("2FA error")
        await update.message.reply_text(f"❌ 2FA error: {e}")
    finally:
        await client.disconnect()

# ---------------- CONTROLLER COMMANDS ----------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # show /allcmd automatically as you requested
    await allcmd(update, context)

async def allcmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 Controller commands:\n"
        "/login — request OTP\n"
        "/otp <code> — verify OTP\n"
        "/2fa <password> — 2FA login\n"
        "/status — show config status\n"
        "/addsource <group_id>\n"
        "/removesource <group_id>\n"
        "/addtarget <group_id>\n"
        "/removetarget <group_id>\n"
        "/setdelay <min> <max>\n"
        "/startadd — start worker\n"
        "/stopadd — stop worker\n"
        "/workerstatus — show worker progress\n"
        "/allcmd — this help\n"
    )
    await update.message.reply_text(msg)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    msg = (
        f"🔐 Logged In: {'✅' if cfg.get('logged_in') else '❌'}\n"
        f"⚙️ Adding: {'✅' if cfg.get('is_adding') else '❌'}\n"
        f"Sources: {cfg.get('source_groups', [])}\n"
        f"Targets: {cfg.get('target_groups', [])}\n"
        f"Delay: {cfg.get('delay_min', '?')}–{cfg.get('delay_max', '?')}s\n"
        f"Cache TTL: {cfg.get('cache_ttl_seconds', 3600)}s\n"
        f"Ping URL: {cfg.get('PING_URL', os.getenv('PING_URL', 'none'))}"
    )
    await update.message.reply_text(msg)

async def addsource(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /addsource -100xxxx")
    cfg = load_config()
    src = context.args[0]
    cfg.setdefault("source_groups", [])
    if src not in cfg["source_groups"]:
        cfg["source_groups"].append(src)
        save_config(cfg)
        await update.message.reply_text(f"✅ Source added: {src}")
    else:
        await update.message.reply_text("⚠️ Already present")

async def removesource(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /removesource -100xxxx")
    cfg = load_config()
    src = context.args[0]
    if src in cfg.get("source_groups", []):
        cfg["source_groups"].remove(src)
        save_config(cfg)
        await update.message.reply_text(f"✅ Source removed: {src}")
    else:
        await update.message.reply_text("⚠️ Not found")

async def addtarget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /addtarget -100xxxx")
    cfg = load_config()
    tgt = context.args[0]
    cfg.setdefault("target_groups", [])
    if tgt not in cfg["target_groups"]:
        cfg["target_groups"].append(tgt)
        save_config(cfg)
        await update.message.reply_text(f"✅ Target added: {tgt}")
    else:
        await update.message.reply_text("⚠️ Already present")

async def removetarget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("⚠️ Usage: /removetarget -100xxxx")
    cfg = load_config()
    tgt = context.args[0]
    if tgt in cfg.get("target_groups", []):
        cfg["target_groups"].remove(tgt)
        save_config(cfg)
        await update.message.reply_text(f"✅ Target removed: {tgt}")
    else:
        await update.message.reply_text("⚠️ Not found")

async def setdelay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        return await update.message.reply_text("⚠️ Usage: /setdelay <min> <max>")
    try:
        dmin, dmax = map(int, context.args)
    except:
        return await update.message.reply_text("⚠️ Enter valid integers")
    cfg = load_config()
    cfg["delay_min"] = dmin
    cfg["delay_max"] = dmax
    save_config(cfg)
    await update.message.reply_text(f"✅ Delay set to {dmin}–{dmax}s")

async def startadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    if not cfg.get("logged_in"):
        return await update.message.reply_text("⚠️ Please login first (/login + /otp).")
    if cfg.get("is_adding"):
        return await update.message.reply_text("⚙️ Worker already running.")
    cfg["is_adding"] = True
    save_config(cfg)
    # start worker in background
    os.system("nohup python3 worker_add.py > logs/worker.log 2>&1 &")
    await update.message.reply_text("🚀 Worker started.")

async def stopadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    if not cfg.get("is_adding"):
        return await update.message.reply_text("⚠️ Worker not running.")
    cfg["is_adding"] = False
    save_config(cfg)
    await update.message.reply_text("🛑 Stop signal set. Worker will halt soon.")

async def workerstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(PROGRESS_PATH):
        return await update.message.reply_text("⚠️ No progress file found.")
    try:
        data = json.load(open(PROGRESS_PATH))
        msg = (
            f"📊 Worker Status:\n"
            f"Source: {data.get('source')}\n"
            f"Target: {data.get('target')}\n"
            f"✅ Added: {data.get('added', 0)}\n"
            f"Delay: {data.get('delay_min')}–{data.get('delay_max')}s\n"
            f"Cache age: {data.get('cache_age_seconds', '?')}s\n"
            f"Uptime: {data.get('uptime', '?')}"
        )
        await update.message.reply_text(msg)
    except Exception as e:
        logger.exception("Reading progress failed")
        await update.message.reply_text(f"❌ Error: {e}")

# ---------------- KEEP ALIVE PING ----------------
async def keep_alive():
    while True:
        try:
            cfg = load_config()
            url = cfg.get("PING_URL") or os.getenv("PING_URL")
            if url:
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.get(url)
                    logger.info(f"🌐 Ping {url} | {r.status_code}")
            else:
                logger.debug("No PING_URL set; skipping ping.")
        except Exception as e:
            logger.warning(f"Ping failed: {e}")
        await asyncio.sleep(600)  # 10 minutes

# ---------------- MAIN ----------------
async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("❌ BOT_TOKEN not set in env")
    app = ApplicationBuilder().token(token).build()

    handlers = [
        CommandHandler("start", start_cmd),
        CommandHandler("allcmd", allcmd),
        CommandHandler("login", login),
        CommandHandler("otp", otp),
        CommandHandler("2fa", twofa),
        CommandHandler("status", status),
        CommandHandler("addsource", addsource),
        CommandHandler("removesource", removesource),
        CommandHandler("addtarget", addtarget),
        CommandHandler("removetarget", removetarget),
        CommandHandler("setdelay", setdelay),
        CommandHandler("startadd", startadd),
        CommandHandler("stopadd", stopadd),
        CommandHandler("workerstatus", workerstatus),
    ]
    for h in handlers:
        app.add_handler(h)

    logger.info("🚀 Controller bot started successfully.")
    asyncio.create_task(keep_alive())
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
