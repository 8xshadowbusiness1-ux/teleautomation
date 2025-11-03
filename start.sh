#!/usr/bin/env bash
echo "🚀 Starting Telegram Automation (Controller + Worker Ready)"
set -e

# Install dependencies (safe repeat)
pip install --upgrade pip
pip install -r requirements.txt

# Ensure logs folder
mkdir -p logs

# Ensure bot_config.json exists
if [ ! -f bot_config.json ]; then
  echo "⚠️ bot_config.json not found, creating default..."
  echo '{
    "session_name": "worker_main",
    "api_id": 0,
    "api_hash": "",
    "phone": "",
    "logged_in": false,
    "is_adding": false,
    "source_groups": [],
    "target_groups": [],
    "delay_min": 15,
    "delay_max": 30,
    "PING_URL": ""
  }' > bot_config.json
fi

# Start dummy webserver (Render requirement)
python3 -m http.server ${PORT:-8080} >/dev/null 2>&1 &

# Start controller bot (auto restart if crash)
while true; do
  echo "🟢 Launching controller_bot.py at $(date)"
  python3 controller_bot.py > logs/controller.log 2>&1 || true
  echo "⚠️ Controller crashed — restarting in 10 seconds..."
  sleep 10
done
