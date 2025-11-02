#!/usr/bin/env bash
echo "🚀 Starting Telegram Automation System (Controller + Worker)"
set -e

pip install -r requirements.txt
export BOT_TOKEN="${BOT_TOKEN}"
mkdir -p logs

# ensure config.json exists and writable
if [ ! -f config.json ]; then
  echo '{"workers": {}, "managers": {}, "pending_otp": {}, "otp_codes": {}, "otp_status": {}}' > config.json
fi
chmod 666 config.json

# dummy web server for Render
python3 -m http.server ${PORT:-8080} >/dev/null 2>&1 &

# start controller
nohup python3 controller_bot.py > logs/controller_bot.log 2>&1 &

sleep 4

# start worker monitor (dynamic launcher)
nohup python3 worker_launcher.py > logs/worker_launcher.log 2>&1 &

tail -f logs/controller_bot.log logs/worker_launcher.log
