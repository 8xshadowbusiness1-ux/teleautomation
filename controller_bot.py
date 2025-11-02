import asyncio
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telethon import TelegramClient
import random
import time

# === TELETHON LOGIN DETAILS ===
API_ID = 20339511  # apna actual API ID
API_HASH = "400346de83fffd1ef3da5bbaab999d4c"  # apna actual API hash
PHONE = "+91XXXXXXXXXX"  # apna Telegram number
SESSION_NAME = "worker_main"

# === GLOBAL FLAGS ===
is_adding = False
delay_min = 10
delay_max = 15
source_group = "@tutorial_group"
target_group = "@project_group"

# === TELETHON CLIENT INIT ===
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# === BOT COMMANDS ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot connected successfully!\n\nCommands:\n"
        "/startadd - Start adding members\n"
        "/stopadd - Stop adding\n"
        "/setdelay <min> <max> - Set delay between adds\n"
        "/status - Check current status\n"
        "/all - Show all settings"
    )

async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_adding
    if is_adding:
        await update.message.reply_text("⚠️ Already adding members...")
        return

    is_adding = True
    await update.message.reply_text("🚀 Starting member adding process...")

    async with client:
        try:
            source = await client.get_participants(source_group)
            for user in source:
                if not is_adding:
                    await update.message.reply_text("🛑 Adding stopped.")
                    break
                try:
                    await client.add_participant(target_group, user)
                    wait_time = random.randint(delay_min, delay_max)
                    await update.message.reply_text(
                        f"✅ Added {user.first_name}, waiting {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                except Exception as e:
                    await update.message.reply_text(f"⚠️ Error adding {user.id}: {e}")
                    await asyncio.sleep(5)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    await update.message.reply_text("✅ Process finished or stopped.")

async def stop_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_adding
    is_adding = False
    await update.message.reply_text("🛑 Member adding stopped manually.")

async def set_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global delay_min, delay_max
    try:
        delay_min = int(context.args[0])
        delay_max = int(context.args[1])
        await update.message.reply_text(f"⏱️ Delay set between {delay_min}s - {delay_max}s.")
    except:
        await update.message.reply_text("⚠️ Usage: /setdelay <min> <max>")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_text = "🟢 Active" if is_adding else "🔴 Idle"
    await update.message.reply_text(
        f"📊 Status: {status_text}\n"
        f"⏱️ Delay: {delay_min}-{delay_max}s\n"
        f"👥 Source: {source_group}\n"
        f"🎯 Target: {target_group}"
    )

async def all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⚙️ Current Config:\n\n"
        f"👥 Source Group: {source_group}\n"
        f"🎯 Target Group: {target_group}\n"
        f"⏱️ Delay: {delay_min}-{delay_max}s\n"
        f"📞 Phone: {PHONE}\n"
        f"Status: {'🟢 Adding' if is_adding else '🔴 Stopped'}"
    )

# === BOT SETUP ===
if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not found in environment.")
        exit(1)

    print("🤖 Starting Telegram Controller Bot...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startadd", start_add))
    app.add_handler(CommandHandler("stopadd", stop_add))
    app.add_handler(CommandHandler("setdelay", set_delay))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("all", all_command))

    app.run_polling()
