import os, json, logging, asyncio
from pathlib import Path
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- Optional: Prevent asyncio loop issues on Render ---
import nest_asyncio
nest_asyncio.apply()

# --- Logging setup ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Config file ---
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

# --- Utility ---
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

# --- Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_manager(user.id)
    await update.message.reply_text(
        f"👋 Hi {user.first_name}! You're now registered as manager.\n\n"
        "Use /allcommands to see all available commands."
    )

async def allcommands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📜 Available Commands:\n\n"
        "/start — Register as manager\n"
        "/setdelay <MIN-MAX> — e.g. /setdelay 10-15\n"
        "/setgroups <source> <target>\n"
        "/assignworker <worker>\n"
        "/startmulti <w1,w2,...>\n"
        "/startadd — Begin adding\n"
        "/stopadd — Stop adding\n"
        "/status — Show status\n"
        "/addworker <name> <api_id> <api_hash>\n"
        "/setworkercred <name> <api_id> <api_hash>\n"
        "/setworkerphone <name> <phone>\n"
        "/verifyworker <name> <phone>\n"
        "/submitotp <name> <code>\n"
        "/submit2fa <name> <password>\n"
        "/removeworker <name>\n"
        "/listworkers\n"
        "/help_safe — Safety info"
    )
    await update.message.reply_text(text)

async def setdelay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /setdelay MIN-MAX (e.g. /setdelay 10-15)")
    try:
        mn, mx = map(int, context.args[0].split("-"))
        if mn <= 0 or mx < mn:
            raise ValueError
    except:
        return await update.message.reply_text("Invalid format. Example: /setdelay 10-15")

    cfg = load_cfg()
    uid = str(update.effective_user.id)
    if uid not in cfg["managers"]:
        ensure_manager(uid)
    cfg["managers"][uid]["delay_min_minutes"] = mn
    cfg["managers"][uid]["delay_max_minutes"] = mx
    save_cfg(cfg)
    await update.message.reply_text(f"✅ Delay set to {mn}-{mx} minutes.")

async def setgroups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /setgroups <source> <target>")
    src, tgt = context.args[0], context.args[1]
    cfg = load_cfg()
    uid = str(update.effective_user.id)
    cfg["managers"][uid]["source"] = src
    cfg["managers"][uid]["target"] = tgt
    save_cfg(cfg)
    await update.message.reply_text(f"Source: `{src}`\nTarget: `{tgt}`")

async def assignworker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /assignworker <worker>")
    worker = context.args[0]
    cfg = load_cfg()
    uid = str(update.effective_user.id)
    if worker not in cfg["workers"]:
        return await update.message.reply_text("❌ Worker not found. Use /addworker first.")
    cfg["managers"][uid]["workers"] = [worker]
    save_cfg(cfg)
    await update.message.reply_text(f"✅ Worker `{worker}` assigned to you.")

async def startmulti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /startmulti worker1,worker2")
    workers = [w.strip() for w in " ".join(context.args).split(",") if w.strip()]
    cfg = load_cfg()
    uid = str(update.effective_user.id)
    missing = [w for w in workers if w not in cfg["workers"]]
    if missing:
        return await update.message.reply_text(f"❌ Missing workers: {missing}")
    cfg["managers"][uid]["workers"] = workers
    cfg["managers"][uid]["active"] = True
    save_cfg(cfg)
    await update.message.reply_text(f"✅ Assigned workers {workers} and started adding.")

async def startadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    cfg = load_cfg()
    cfg["managers"][uid]["active"] = True
    save_cfg(cfg)
    await update.message.reply_text("✅ Adding started (active=true).")

async def stopadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    cfg = load_cfg()
    cfg["managers"][uid]["active"] = False
    save_cfg(cfg)
    await update.message.reply_text("🛑 Adding stopped (active=false).")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    cfg = load_cfg()
    if uid not in cfg["managers"]:
        return await update.message.reply_text("Send /start first.")
    m = cfg["managers"][uid]
    msg = (
        f"📊 Manager status:\n"
        f"Workers: {m.get('workers')}\n"
        f"Delay: {m.get('delay_min_minutes')}-{m.get('delay_max_minutes')} min\n"
        f"Source: {m.get('source')}\n"
        f"Target: {m.get('target')}\n"
        f"Active: {m.get('active')}"
    )
    await update.message.reply_text(msg)

# --- Worker Management ---
async def addworker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        return await update.message.reply_text("Usage: /addworker <name> <api_id> <api_hash>")
    name, api_id, api_hash = context.args[:3]
    cfg = load_cfg()
    cfg["workers"][name] = {
        "session_name": f"{name}_session",
        "api_id": api_id,
        "api_hash": api_hash,
        "phone": None,
    }
    save_cfg(cfg)
    await update.message.reply_text(f"✅ Worker `{name}` added successfully.")

async def setworkercred(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        return await update.message.reply_text("Usage: /setworkercred <name> <api_id> <api_hash>")
    name, api_id, api_hash = context.args[:3]
    cfg = load_cfg()
    if name not in cfg["workers"]:
        return await update.message.reply_text("❌ Worker not found.")
    cfg["workers"][name]["api_id"] = api_id
    cfg["workers"][name]["api_hash"] = api_hash
    save_cfg(cfg)
    await update.message.reply_text(f"🔐 Credentials updated for {name}")

async def setworkerphone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /setworkerphone <name> <phone>")
    name, phone = context.args[0], context.args[1]
    cfg = load_cfg()
    if name not in cfg["workers"]:
        return await update.message.reply_text("❌ Worker not found.")
    cfg["workers"][name]["phone"] = phone
    save_cfg(cfg)
    await update.message.reply_text(f"📱 Phone set for {name}")

# --- OTP / 2FA ---
async def verifyworker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /verifyworker <worker> <phone>")
    name, phone = context.args[0], context.args[1]
    cfg = load_cfg()
    cfg["pending_otp"][name] = phone
    cfg["otp_status"][name] = "requested"
    save_cfg(cfg)
    await update.message.reply_text(f"📩 OTP request registered for {name}.")

async def submitotp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /submitotp <worker> <code>")
    name, code = context.args[0], context.args[1]
    cfg = load_cfg()
    cfg["otp_codes"][name] = code
    save_cfg(cfg)
    await update.message.reply_text(f"✅ OTP submitted for {name}.")

async def submit2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /submit2fa <worker> <password>")
    name, password = context.args[0], context.args[1]
    cfg = load_cfg()
    cfg.setdefault("otp_passwords", {})[name] = password
    save_cfg(cfg)
    await update.message.reply_text(f"🔐 2FA password saved for {name}. Worker will auto-complete login.")

# --- Safety Help ---
async def help_safe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ Privacy & Safety Rules:\n"
        "- Users with privacy settings can't be added.\n"
        "- Bot never sends user links or usernames.\n"
        "- Use realistic delays to avoid Telegram bans."
    )

# --- Run Bot ---
BOT_TOKEN = os.environ.get("BOT_TOKEN") or "8254353086:AAEMim12HX44q0XYaFWpbB3J7cxm4VWprEc"
app = ApplicationBuilder().token(BOT_TOKEN).build()

async def main():
    await app.bot.delete_webhook(drop_pending_updates=True)

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
    app.add_handler(CommandHandler("submit2fa", submit2fa))
    app.add_handler(CommandHandler("help_safe", help_safe))

    print("✅ Controller bot started successfully! Waiting for Telegram commands...")
    await app.run_polling(close_loop=False)

if __name__ == "__main__":
    asyncio.run(main())
