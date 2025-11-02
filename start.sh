#!/usr/bin/env bash
echo "🚀 Starting Telegram Controller Bot on Render (Web Service mode)..."
set -e

# Install dependencies
pip install -r requirements.txt

# Export bot token (Render env var)
export BOT_TOKEN="${BOT_TOKEN}"

# Create logs folder
mkdir -p logs

# Start a dummy web server to keep Render happy (port listener)
echo "▶️ Starting dummy web listener for Render health checks..."
python3 -m http.server 8080 >/dev/null 2>&1 &

# Wait a bit then start Telegram bot
sleep 2
echo "▶️ Starting Telegram bot..."
python3 controller_bot.py >> logs/controller_bot.log 2>&1
