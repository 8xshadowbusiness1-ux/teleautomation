#!/usr/bin/env bash
echo "🚀 Starting Telegram Automation System on Render (All-in-One Mode)..."
set -e

# Install all dependencies
pip install -r requirements.txt

# Export bot token from Render env var
export BOT_TOKEN="${BOT_TOKEN}"

# Create logs folder if not exists
mkdir -p logs

# ✅ Start a dummy web server (so Render detects open port)
python3 -m http.server ${PORT:-8080} >/dev/null 2>&1 &

# ✅ Start the controller bot in background
echo "▶️ Starting Controller Bot..."
nohup python3 controller_bot.py > logs/controller_bot.log 2>&1 &

# Wait for few seconds so bot initializes
sleep 5

# ✅ Start Worker 1
echo "▶️ Starting Worker 1..."
nohup python3 worker_adder.py worker1 > logs/worker1.log 2>&1 &

# (Optional) Start Worker 2 also if configured
# echo "▶️ Starting Worker 2..."
# nohup python3 worker_adder.py worker2 > logs/worker2.log 2>&1 &

echo "✅ All services started. Logs available inside /logs folder."
tail -f logs/controller_bot.log
