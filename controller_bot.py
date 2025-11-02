import os, json
from pathlib import Path
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import logging

logging.basicConfig(level=logging.INFO)
CONFIG_PATH = Path("config.json")

def load_cfg():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps({
            "managers": {},
            "workers": {},
            "pending_otp": {},
            "otp_codes": {},
            "otp_passwords": {},
            "otp_status": {}
        }, indent=2))
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
        "Available commands:\n\n"
        "/start — Register as manager\n"
        "/setdelay <MIN-MAX>\n"
        "/setgroups <source> <target>\n"
        "/assignworker <worker>\n"
        "/startmulti <w1,w2,...>\n"
        "/startadd — Begin adding\n"
        "/stopadd — Stop adding\n"
        "/status — Manager status\n"
        "/addworker <name> <api_id> <api_hash>\n"
        "/setworkercred <name> <api_id> <api_hash>\n"
        "/setworkerphone <name> <phone>\n"
        "/removeworker <name>\n"
        "/listworkers — Show all workers\n"
        "/checkworker <name>\n"
        "/verifyworker <name> <phone>\n"
        "/submitotp <name> <code>\n"
        "/submit2fa <name> <password> — Submit 2-Step Verification password\n"
        "/switchworker <name>\n"
        "/help_safe — Show safety rules"
    )
    await update.message.reply_text(text)

async def setdelay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /setdelay MIN-MAX (e.g. /setdelay 10-15)")
        return
    try:
        mn, mx = map(int, context.args[0].split("-"))
        if mn <= 0 or mx < mn:
            raise ValueError
    except:
        await update.message.reply_text("Invalid format. Example: /setdelay 10-15")
        return
    cfg = load_cfg()
    uid = str(update.effective_user.id)
    cfg["managers"][uid]["delay_min_minutes"] = mn
    cfg["managers"][uid]["delay_max_minutes"] = mx
    save_cfg(cfg)
    await update.message.reply_text(f"Delay set to {mn}-{mx} minutes.")

async def setgroups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setgroups <source> <target>")
        return
    src, tgt = context.args[0], context.args[1]
    cfg = load_cfg()
    uid = str(update.effective_user.id)
    cfg["managers"][uid]["source"] = src
    cfg["managers"][uid]["target"] = tgt
    save_cfg(cfg)
    await update.message.reply_text(f"Source: `{src}`\nTarget: `{tgt}`")

async def assignworker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /assignworker <worker_name>")
        return
    worker = context.args[0]
    cfg = load_cfg()
    uid = str(update.effective_user.id)
    if worker not in cfg["workers"]:
        await update.message.reply_text("Worker not found.")
        return
    cfg["managers"][uid]["workers"] = [worker]
    save_cfg(cfg)
    await update.message.reply_text(f"Assigned worker `{worker}` to you.")

async def startmulti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /startmulti worker1,worker2")
        return
    workers = [w.strip() for w in " ".join(context.args).split(",") if w.strip()]
    cfg = load_cfg()
    uid = str(update.effective_user.id)
    missing = [w for w in workers if w not in cfg["workers"]]
    if missing:
        await update.message.reply_text(f"Workers not found: {missing}")
        return
    cfg["managers"][uid]["workers"] = workers
    cfg["managers"][uid]["active"] = True
    save_cfg(cfg)
    await update.message.reply_text(f"Assigned {workers} and started adding.")

async def startadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    cfg = load_cfg()
    cfg["managers"][uid]["active"] = True
    save_cfg(cfg)
    await update.message.reply_text("✅ Started adding (active=true).")

async def stopadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    cfg = load_cfg()
    cfg["managers"][uid]["active"] = False
    save_cfg(cfg)
    await update.message.reply_text("🛑 Stopped adding (active=false).")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    cfg = load_cfg()
    if uid not in cfg["managers"]:
        await update.message.reply_text("Send /start first.")
        return
    m = cfg["managers"][uid]
    txt = (
        f"Worker(s): {m.get('workers')}\n"
        f"Delay: {m.get('delay_min_minutes')}-{m.get('delay_max_minutes')} min\n"
        f"Source: {m.get('source')}\n"
        f"Target: {m.get('target')}\n"
        f"Active: {m.get('active')}"
    )
    await update.message.reply_text(txt)

# ---------- Worker management ----------
async def addworker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /addworker <name> <api_id> <api_hash>")
        return
    name, api_id, api_hash = context.args[:3]
    cfg = load_cfg()
    cfg["workers"][name] = {
        "session_name": f"{name}_session",
        "api_id": api_id,
        "api_hash": api_hash,
        "phone": None,
    }
    save_cfg(cfg)
    await update.message.reply_text(f"Worker `{name}` added successfully.")

async def setworkercred(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /setworkercred <name> <api_id> <api_hash>")
        return
    name, api_id, api_hash = context.args[:3]
    cfg = load_cfg()
    if name not in cfg["workers"]:
        await update.message.reply_text("Worker not found.")
        return
    cfg["workers"][name]["api_id"] = api_id
    cfg["workers"][name]["api_hash"] = api_hash
    save_cfg(cfg)
    await update.message.reply_text(f"✅ Credentials updated for {name}")

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
    await update.message.reply_text(f"📞 Phone set for {name}")

# ---------- OTP / 2FA ----------
async def verifyworker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /verifyworker <worker_name> <phone_number>")
        return
    name, phone = context.args[0], context.args[1]
    cfg = load_cfg()
    cfg["pending_otp"][name] = phone
    cfg["otp_status"][name] = "requested"
    save_cfg(cfg)
    await update.message.reply_text(f"🔐 OTP request registered for {name}. Worker will send code.")

async def submitotp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /submitotp <worker_name> <code>")
        return
    name, code = context.args[0], context.args[1]
    cfg = load_cfg()
    cfg["otp_codes"][name] = code
    save_cfg(cfg)
    await update.message.reply_text(f"✅ OTP submitted for {name}. Worker will complete login if running.")

# ✅ FIXED: 2FA PASSWORD COMMAND (proper async version)
async def submit2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /submit2fa <worker_name> <password>")
        return
    name, password = context.args[0], context.args[1]
    cfg = load_cfg()
    cfg.setdefault("otp_passwords", {})[name] = password
    save_cfg(cfg)
    await update.message.reply_text(f"🔐 2FA password saved for {name}. Worker will auto-complete login if running.")

# ---------- setup & run ----------
if __name__ == "__main__":
    BOT_TOKEN = "8254353086:AAEMim12HX44q0XYaFWpbB3J7cxm4VWprEc"

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register all handlers
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
    app.add_handler(CommandHandler("verifyworker", verifyworker))
    app.add_handler(CommandHandler("submitotp", submitotp))
    app.add_handler(CommandHandler("submit2fa", submit2fa))  # ✅ added correctly
    print("✅ Controller bot started successfully! Waiting for Telegram commands...")
    app.run_polling()
