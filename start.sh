#!/usr/bin/env bash
echo "🚀 Launching Telegram Controller Bot on Render..."
set -e

# install all dependencies
pip install -r requirements.txt

# export your bot token (set your token in Render environment variables for safety)
export BOT_TOKEN="${BOT_TOKEN}"

# (optional) create logs folder
mkdir -p logs

# run the bot with restart loop
while true; do
  echo "▶️ Starting Controller Bot at $(date)"
  python3 controller_bot.py >> logs/controller_bot.log 2>&1
  echo "⚠️ Bot crashed or stopped — restarting in 5 seconds..."
  sleep 5
done
