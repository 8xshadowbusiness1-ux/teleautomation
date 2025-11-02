# controller_bot.py
import os, json
from pathlib import Path
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import logging

logging.basicConfig(level=logging.INFO)
CONFIG_PATH = Path("config.json")

def load_cfg():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps({"managers": {}, "workers": {}, "pending_otp": {}, "otp_codes": {}, "otp_status": {}}, indent=2))
    return json.loads(CONFIG_PATH.read_text())

def save_cfg(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

# ---------- Utility ----------
def ensure_manager(uid):
    cfg = load_cfg()
    if str(uid) not in cfg["managers"]:
        cfg["managers"][str(uid)] = {
            "workers": [],
            "delay_min_minutes": 10,
            "delay_max_minutes": 15,
            "source": None,
            "target": None,
            "active": False
        }
        save_cfg(cfg)
    return cfg

# ---------- Commands ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cfg = ensure_manager(user.id)
    await update.message.reply_text(
        f"Hi {user.first_name}! Your manager id: {user.id}\n\n"
        "Use /allcommands to see all commands with usage."
    )

async def allcommands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Available commands (usage shown):\n\n"
        "/start — register as manager (returns your manager id)\n\n"
        "/allcommands — show this help\n\n"
        "/setdelay <MIN-MAX> — Set random delay in minutes. Example:\n"
        "    /setdelay 10-15\n\n"
        "/setgroups <source> <target> — Set source and target groups. Example:\n"
        "    /setgroups @source_group @target_group\n\n"
        "/assignworker <worker_name> — Assign single worker (legacy). Example:\n"
        "    /assignworker worker1\n\n"
        "/startmulti <worker1,worker2,...> — Assign these workers to you and set active=true. Example:\n"
        "    /startmulti worker1,worker2\n\n"
        "/startadd — Set active=true (workers assigned to you will pick it up)\n\n"
        "/stopadd — Set active=false (stop workers)\n\n"
        "/status — Show your manager config/status\n\n"
        "/addworker <name> <api_id> <api_hash> — Add a worker to config. Example:\n"
        "    /addworker worker3 123456 0123456789abcdef0123456789abcdef\n\n"
        "/setworkercred <name> <api_id> <api_hash> — Update worker credentials\n\n"
        "/setworkerphone <name> <phone_number> — Set worker phone for OTP flows. Example:\n"
        "    /setworkerphone worker3 +9198xxxxxxx\n\n"
        "/removeworker <name> — Remove worker from config\n\n"
        "/listworkers — List configured workers\n\n"
        "/checkworker <name> — Check if session file exists & authorization (light check)\n\n"
        "/verifyworker <name> <phone_number> — Trigger OTP send (worker machine will pick it up)\n\n"
        "/submitotp <name> <code> — Submit OTP code (manager supplies code to bot)\n\n"
        "/switchworker <name> — Shortcut to assign single worker to manager\n\n"
        "/help_safe — Show privacy/safety rules (no links sent if privacy error)\n\n"
        "----\nNote: Bot updates config.json. Worker scripts must be running on worker machines (python worker_adder.py <worker_name>) to pick up changes and complete OTP sign-in."
    )
    await update.message.reply_text(text)

async def setdelay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /setdelay MIN-MAX (minutes). Example: /setdelay 10-15")
        return
    try:
        mn, mx = map(int, context.args[0].split("-"))
        if mn <=0 or mx < mn:
            raise ValueError
    except:
        await update.message.reply_text("Invalid format. Use like: /setdelay 10-15")
        return
    cfg = load_cfg()
    uid = str(user.id)
    if uid not in cfg["managers"]:
        await update.message.reply_text("Send /start first.")
        return
    cfg["managers"][uid]["delay_min_minutes"] = mn
    cfg["managers"][uid]["delay_max_minutes"] = mx
    save_cfg(cfg)
    await update.message.reply_text(f"Delay set to {mn}-{mx} minutes.")

async def setgroups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setgroups <source> <target>")
        return
    src = context.args[0]; tgt = context.args[1]
    cfg = load_cfg()
    uid = str(user.id)
    if uid not in cfg["managers"]:
        await update.message.reply_text("Send /start first.")
        return
    cfg["managers"][uid]["source"] = src
    cfg["managers"][uid]["target"] = tgt
    save_cfg(cfg)
    await update.message.reply_text(f"Source set to `{src}`\nTarget set to `{tgt}`")

async def assignworker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /assignworker <worker_name>")
        return
    worker = context.args[0]
    cfg = load_cfg()
    uid = str(user.id)
    if worker not in cfg["workers"]:
        await update.message.reply_text("Worker not found. Use /listworkers.")
        return
    cfg["managers"][uid]["workers"] = [worker]
    save_cfg(cfg)
    await update.message.reply_text(f"Assigned worker `{worker}` to you.")

async def startmulti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /startmulti worker1,worker2")
        return
    workers = [w.strip() for w in " ".join(context.args).split(",") if w.strip()]
    cfg = load_cfg()
    uid = str(user.id)
    missing = [w for w in workers if w not in cfg["workers"]]
    if missing:
        await update.message.reply_text(f"Workers not found: {missing}. Add them first with /addworker.")
        return
    cfg["managers"][uid]["workers"] = workers
    cfg["managers"][uid]["active"] = True
    save_cfg(cfg)
    await update.message.reply_text(f"Assigned workers {workers} and set active=true. Workers will pick up and start adding.")

async def startadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cfg = load_cfg()
    uid = str(user.id)
    if uid not in cfg["managers"]:
        await update.message.reply_text("Send /start first.")
        return
    cfg["managers"][uid]["active"] = True
    save_cfg(cfg)
    await update.message.reply_text("Started adding (active=true). Workers will pick this up.")

async def stopadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cfg = load_cfg()
    uid = str(user.id)
    if uid not in cfg["managers"]:
        await update.message.reply_text("Send /start first.")
        return
    cfg["managers"][uid]["active"] = False
    save_cfg(cfg)
    await update.message.reply_text("Stopped adding (active=false).")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cfg = load_cfg()
    uid = str(user.id)
    if uid not in cfg["managers"]:
        await update.message.reply_text("Send /start first.")
        return
    m = cfg["managers"][uid]
    text = (
        f"Worker(s): {m.get('workers')}\n"
        f"Delay: {m.get('delay_min_minutes')}-{m.get('delay_max_minutes')} minutes\n"
        f"Source: {m.get('source')}\n"
        f"Target: {m.get('target')}\n"
        f"Active: {m.get('active')}\n"
    )
    await update.message.reply_text(text)

# ---------- Worker management ----------
async def addworker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /addworker <name> <api_id> <api_hash>")
        return
    name = context.args[0]
    api_id = context.args[1]
    api_hash = context.args[2]
    cfg = load_cfg()
    if name in cfg["workers"]:
        await update.message.reply_text("Worker exists. Use /setworkercred to update.")
        return
    cfg["workers"][name] = {
        "session_name": f"{name}_session",
        "api_id": api_id,
        "api_hash": api_hash,
        "phone": None,
        "notes": ""
    }
    save_cfg(cfg)
    await update.message.reply_text(f"Worker `{name}` added. Now run worker_adder.py on worker machine and login to create session.")

async def setworkercred(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /setworkercred <name> <api_id> <api_hash>")
        return
    name, api_id, api_hash = context.args[0], context.args[1], context.args[2]
    cfg = load_cfg()
    if name not in cfg["workers"]:
        await update.message.reply_text("Worker not found.")
        return
    cfg["workers"][name]["api_id"] = api_id
    cfg["workers"][name]["api_hash"] = api_hash
    save_cfg(cfg)
    await update.message.reply_text(f"Credentials updated for {name}.")

async def setworkerphone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setworkerphone <name> <phone>")
        return
    name, phone = context.args[0], context.args[1]
    cfg = load_cfg()
    if name not in cfg["workers"]:
        await update.message.reply_text("Worker not found.")
        return
    cfg["workers"][name]["phone"] = phone
    save_cfg(cfg)
    await update.message.reply_text(f"Phone set for {name}. Use /verifyworker to start OTP flow.")

async def removeworker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /removeworker <name>")
        return
    name = context.args[0]
    cfg = load_cfg()
    if name not in cfg["workers"]:
        await update.message.reply_text("Worker not found.")
        return
    # remove from any manager lists
    for m in cfg["managers"].values():
        if "workers" in m and name in m["workers"]:
            m["workers"].remove(name)
    del cfg["workers"][name]
    save_cfg(cfg)
    await update.message.reply_text(f"Worker {name} removed.")

async def listworkers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_cfg()
    if not cfg["workers"]:
        await update.message.reply_text("No workers configured.")
        return
    lines = []
    for name, w in cfg["workers"].items():
        api_ok = "yes" if w.get("api_id") and w.get("api_hash") else "no"
        phone = w.get("phone") or "not set"
        lines.append(f"{name} — session: {w.get('session_name')} — api_set: {api_ok} — phone: {phone}")
    await update.message.reply_text("\n".join(lines))

async def checkworker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /checkworker <name>")
        return
    name = context.args[0]
    cfg = load_cfg()
    if name not in cfg["workers"]:
        await update.message.reply_text("Worker not found.")
        return
    w = cfg["workers"][name]
    session_file = Path(f"{w.get('session_name')}.session")
    lines = [f"Worker: {name}", f"Session file: {w.get('session_name')}.session"]
    if session_file.exists():
        lines.append("Session file: ✅ exists")
        try:
            from telethon import TelegramClient
            api_id = int(w.get("api_id")) if w.get("api_id") else None
            api_hash = w.get("api_hash")
            if not api_id or not api_hash:
                lines.append("Credentials in config: ❌ missing (can't fully verify)")
            else:
                client = TelegramClient(w.get("session_name"), api_id, api_hash)
                client.connect()
                if client.is_user_authorized():
                    me = client.get_me()
                    uname = getattr(me, "username", None)
                    lines.append(f"Authorized: ✅ (id: {getattr(me,'id','?')}, username: {uname or 'N/A'})")
                else:
                    lines.append("Authorized: ❌ (session exists but not authorized)")
                client.disconnect()
        except Exception as e:
            lines.append(f"Telethon check failed: {e}")
    else:
        lines.append("Session file: ❌ not found. Run worker_adder.py on the worker machine and login (phone+OTP).")
    await update.message.reply_text("\n".join(lines))

# ---------- OTP workflow ----------
async def verifyworker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /verifyworker <worker_name> <phone_number>
    Triggers OTP send by worker script.
    """
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /verifyworker <worker_name> <phone_number>")
        return
    name = context.args[0]
    phone = context.args[1]
    cfg = load_cfg()
    if name not in cfg["workers"]:
        await update.message.reply_text("Worker not found.")
        return
    cfg["pending_otp"][name] = phone
    cfg["otp_status"][name] = "requested"
    save_cfg(cfg)
    await update.message.reply_text(f"OTP request registered for {name}. Worker must be running to send code.")

async def submitotp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /submitotp <worker_name> <code>
    Submit OTP code received on phone to let the worker complete sign-in.
    """
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /submitotp <worker_name> <code>")
        return
    name = context.args[0]; code = context.args[1]
    cfg = load_cfg()
    if name not in cfg["workers"]:
        await update.message.reply_text("Worker not found.")
        return
    cfg["otp_codes"][name] = code
    save_cfg(cfg)
    await update.message.reply_text("OTP submitted. Worker will pick it and complete sign-in (if running).")

async def switchworker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await assignworker(update, context)

async def help_safe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Privacy & safety rules:\n"
        "- If worker fails to add a user due to privacy (UserPrivacyRestricted), the bot WILL NOT send user's link or username to manager.\n"
        "- Bot will log 'privacy_restricted' or 'skipped due to privacy' only.\n"
        "- Keep delays high and avoid mass invites to prevent bans.\n"
    )
    await update.message.reply_text(text)

# ---------- setup & run ----------
if __name__ == "__main__":
    # 👇 Example token (for demonstration only)
    BOT_TOKEN = "8254353086:AAEMim12HX44q0XYaFWpbB3J7cxm4VWprEc"

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register handlers (same as above)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("allcommands", allcommands))
    app.add_handler(CommandHandler("setdelay", setdelay))
    app.add_handler(CommandHandler("setgroups", setgroups))
    app.add_handler(CommandHandler("assignworker", assignworker))
    app.add_handler(CommandHandler("startmulti", startmulti))
    app.add_handler(CommandHandler("startadd", startadd))
    app.add_handler(CommandHandler("stopadd", stopadd))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("addworker", addworker))
    app.add_handler(CommandHandler("setworkercred", setworkercred))
    app.add_handler(CommandHandler("setworkerphone", setworkerphone))
    app.add_handler(CommandHandler("removeworker", removeworker))
    app.add_handler(CommandHandler("listworkers", listworkers))
    app.add_handler(CommandHandler("checkworker", checkworker))
    app.add_handler(CommandHandler("verifyworker", verifyworker))
    app.add_handler(CommandHandler("submitotp", submitotp))
    app.add_handler(CommandHandler("switchworker", switchworker))
    app.add_handler(CommandHandler("help_safe", help_safe))

    print("✅ Controller bot started successfully! Waiting for Telegram messages...")
    app.run_polling()
