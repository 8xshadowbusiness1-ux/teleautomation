#!/usr/bin/env bash
echo "🚀 Starting Telegram Automation (Controller + Worker Ready)"
set -e

pip install -r requirements.txt

export BOT_TOKEN="${BOT_TOKEN}"
mkdir -p logs

# Ensure config exists
if [ ! -f bot_config.json ]; then
  echo '{"is_adding": false, "logged_in": false, "source_groups": [], "target_groups": [], "delay_min": 10, "delay_max": 20, "session_name": "worker_main"}' > bot_config.json
fi

# Dummy webserver (Render requirement)
python3 -m http.server ${PORT:-8080} >/dev/null 2>&1 &

# Launch main controller
nohup python3 controller_bot.py > logs/controller.log 2>&1 &

sleep 4
tail -f logs/controller.log
