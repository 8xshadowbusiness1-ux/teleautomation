import asyncio
import os
import json
import random
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telethon import TelegramClient

# ==============================
# CONFIG PATH
# ==============================
CONFIG_FILE = "bot_config.json"

# Default config
config = {
    "api_id": 20339511,  # Apna API ID
    "api_hash": "400346de83fffd1ef3da5bbaab999d4c",  # Apna API hash
    "phone": "+919158759397",
    "session_name": "main_worker",
    "source_groups": [],
    "target_groups": [],
    "delay_min": 10,
    "delay_max": 15,
    "is_adding": False
}

# Load previous config if exists
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        try:
            config.update(json.load(f))
        except:
            pass


# ==============================
# TELETHON CLIENT
# ==============================
client = TelegramClient(config["session_name"], config["api_id"], config["api_hash"])


# ==============================
# SAVE CONFIG FUNCTION
# ==============================
def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


# ==============================
# BOT COMMANDS
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot Connected Successfully!\n\n"
        "Available Commands:\n"
        "/addsource <group_id> - Add source group\n"
        "/removesource <group_id> - Remove source group\n"
        "/addtarget <group_id> - Add target group\n"
        "/removetarget <group_id> - Remove target group\n"
        "/setdelay <min> <max> - Set add delay (in seconds)\n"
        "/startadd - Start adding members\n"
        "/stopadd - Stop adding\n"
        "/status - Check status\n"
        "/all - Show all settings"
    )


async def add_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /addsource <group_id>")
        return
    gid = context.args[0]
    if gid not in config["source_groups"]:
        config["source_groups"].append(gid)
        save_config()
        await update.message.reply_text(f"✅ Source group added: {gid}")
    else:
        await update.message.reply_text("⚠️ Already added.")


async def remove_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /removesource <group_id>")
        return
    gid = context.args[0]
    if gid in config["source_groups"]:
        config["source_groups"].remove(gid)
        save_config()
        await update.message.reply_text(f"🗑️ Removed source group: {gid}")
    else:
        await update.message.reply_text("⚠️ Not found in list.")


async def add_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /addtarget <group_id>")
        return
    gid = context.args[0]
    if gid not in config["target_groups"]:
        config["target_groups"].append(gid)
        save_config()
        await update.message.reply_text(f"✅ Target group added: {gid}")
    else:
        await update.message.reply_text("⚠️ Already added.")


async def remove_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /removetarget <group_id>")
        return
    gid = context.args[0]
    if gid in config["target_groups"]:
        config["target_groups"].remove(gid)
        save_config()
        await update.message.reply_text(f"🗑️ Removed target group: {gid}")
    else:
        await update.message.reply_text("⚠️ Not found in list.")


async def set_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        config["delay_min"] = int(context.args[0])
        config["delay_max"] = int(context.args[1])
        save_config()
        await update.message.reply_text(f"⏱️ Delay set to {config['delay_min']}-{config['delay_max']} seconds.")
    except:
        await update.message.reply_text("⚠️ Usage: /setdelay <min> <max>")


async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if config["is_adding"]:
        await update.message.reply_text("⚠️ Already adding members...")
        return

    if not config["source_groups"] or not config["target_groups"]:
        await update.message.reply_text("⚠️ Please add at least one source and one target group first.")
        return

    config["is_adding"] = True
    save_config()
    await update.message.reply_text("🚀 Starting member adding...")

    async with client:
        try:
            for src in config["source_groups"]:
                source = await client.get_participants(src)
                for user in source:
                    if not config["is_adding"]:
                        await update.message.reply_text("🛑 Stopped.")
                        break
                    for tgt in config["target_groups"]:
                        try:
                            await client.add_participant(tgt, user)
                            wait_time = random.randint(config["delay_min"], config["delay_max"])
                            await update.message.reply_text(f"✅ Added {user.first_name} → {tgt} | Waiting {wait_time}s...")
                            await asyncio.sleep(wait_time)
                        except Exception as e:
                            await update.message.reply_text(f"⚠️ Error adding {user.id} to {tgt}: {e}")
                            await asyncio.sleep(3)
        except Exception as e:
            await update.message.reply_text(f"❌ Main error: {e}")

    config["is_adding"] = False
    save_config()
    await update.message.reply_text("✅ Adding process finished.")


async def stop_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config["is_adding"] = False
    save_config()
    await update.message.reply_text("🛑 Adding stopped manually.")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_text = "🟢 Active" if config["is_adding"] else "🔴 Idle"
    await update.message.reply_text(
        f"📊 Status: {status_text}\n"
        f"👥 Sources: {len(config['source_groups'])}\n"
        f"🎯 Targets: {len(config['target_groups'])}\n"
        f"⏱️ Delay: {config['delay_min']} - {config['delay_max']} sec"
    )


async def all_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⚙️ Current Config:\n\n"
        f"👥 Source Groups: {config['source_groups']}\n"
        f"🎯 Target Groups: {config['target_groups']}\n"
        f"⏱️ Delay: {config['delay_min']}-{config['delay_max']} sec\n"
        f"Status: {'🟢 Adding' if config['is_adding'] else '🔴 Stopped'}"
    )


# ==============================
# MAIN BOT SETUP
# ==============================
if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN missing!")
        exit(1)

    print("🤖 Starting Telegram Controller Bot...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addsource", add_source))
    app.add_handler(CommandHandler("removesource", remove_source))
    app.add_handler(CommandHandler("addtarget", add_target))
    app.add_handler(CommandHandler("removetarget", remove_target))
    app.add_handler(CommandHandler("setdelay", set_delay))
    app.add_handler(CommandHandler("startadd", start_add))
    app.add_handler(CommandHandler("stopadd", stop_add))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("all", all_settings))

    app.run_polling()
