#!/usr/bin/env bash
echo "🚀 Starting Telegram Automation System on Render..."
set -e

# Install dependencies
pip install -r requirements.txt

# Export bot token from Render environment variable
export BOT_TOKEN="${BOT_TOKEN}"

# Create logs folder
mkdir -p logs

# Start dummy web server for Render (keeps port open)
python3 -m http.server ${PORT:-8080} >/dev/null 2>&1 &

# Start controller bot
echo "▶️ Starting Controller Bot..."
nohup python3 controller_bot.py > logs/controller_bot.log 2>&1 &

# Wait few seconds to make sure bot starts
sleep 5

# ✅ Start Worker 1 (your “new” worker)
echo "▶️ Starting Worker: new"
nohup python3 worker_adder.py new > logs/worker_new.log 2>&1 &

# Tail controller bot logs for Render
echo "✅ All systems started. Watching logs..."
tail -f logs/controller_bot.log
