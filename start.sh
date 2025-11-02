#!/usr/bin/env bash
echo "🚀 Starting Telegram Automation System (Controller + Worker)..."
set -e

pip install -r requirements.txt
export BOT_TOKEN="${BOT_TOKEN}"
mkdir -p logs

# Dummy web listener for Render
python3 -m http.server ${PORT:-8080} >/dev/null 2>&1 &

# Start controller bot in background
echo "▶️ Starting Controller Bot..."
nohup python3 controller_bot.py > logs/controller_bot.log 2>&1 &

# Wait few seconds
sleep 5

# Start your worker(s)
echo "▶️ Starting Worker 1..."
nohup python3 worker_adder.py worker1 > logs/worker1.log 2>&1 &

# (optional) start more workers
# echo "▶️ Starting Worker 2..."
# nohup python3 worker_adder.py worker2 > logs/worker2.log 2>&1 &

echo "✅ All services started. Check logs folder for output."
tail -f logs/controller_bot.log
