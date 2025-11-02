#!/usr/bin/env bash
echo "🚀 Starting Telegram Automation System (Controller + Worker)"
set -e

pip install -r requirements.txt
export BOT_TOKEN="${BOT_TOKEN}"
mkdir -p logs

# dummy web listener (Render needs open port)
python3 -m http.server ${PORT:-8080} >/dev/null 2>&1 &

# controller bot
echo "▶️ Controller starting..."
nohup python3 controller_bot.py > logs/controller_bot.log 2>&1 &

sleep 5

# worker (example: new)
echo "▶️ Worker 'new' starting..."
python3 worker_adder.py new > logs/worker_new.log 2>&1 || true

# tail both logs so you can see worker output
tail -f logs/controller_bot.log logs/worker_new.log
