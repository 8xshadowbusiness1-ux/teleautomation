#!/usr/bin/env bash
echo "🚀 Starting Telegram Automation (Controller + Worker Ready)"
set -e

pip install -r requirements.txt

export BOT_TOKEN="${BOT_TOKEN}"
mkdir -p logs

# ✅ Ensure config file exists
if [ ! -f bot_config.json ]; then
  echo '{"is_adding": false, "logged_in": false, "source_groups": [], "target_groups": [], "delay_min": 10, "delay_max": 20, "session_name": "worker_main"}' > bot_config.json
fi

# ✅ Start a dummy webserver to keep Render port open
echo "🌐 Webserver running on port ${PORT:-10000}"
python3 -m http.server ${PORT:-10000} >/dev/null 2>&1 &

# ✅ Start Controller Bot
nohup python3 controller_bot.py > logs/controller.log 2>&1 &

# ✅ Keep logs visible
sleep 4
tail -f logs/controller.log
