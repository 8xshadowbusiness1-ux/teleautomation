#!/usr/bin/env bash
echo "🚀 Starting Telegram Automation (Controller + Worker Ready)"
set -e

pip install --no-cache-dir -r requirements.txt
mkdir -p logs

if [ ! -f bot_config.json ]; then
  echo '{"api_id":22676464,"api_hash":"b52406ee2c61546d8b560e2d009052d3","phone":"+917671914528","session_name":"worker_main","source_groups":[],"target_groups":[],"delay_min":10,"delay_max":15,"is_adding":false,"logged_in":false}' > bot_config.json
fi

chmod 666 bot_config.json

if [ -z "$BOT_TOKEN" ]; then
  echo "❌ BOT_TOKEN missing!"
  exit 1
fi

python3 -m http.server ${PORT:-8080} >/dev/null 2>&1 &
sleep 3

echo "🤖 Launching controller..."
nohup python3 controller_bot.py > logs/controller.log 2>&1 &

echo "📜 Tail logs:"
tail -f logs/controller.log
