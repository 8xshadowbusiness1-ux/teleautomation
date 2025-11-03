#!/usr/bin/env bash
set -e
echo "🚀 Starting Telegram Automation (Controller + Worker Ready)"

# install deps
pip install -r requirements.txt

# ensure logs folder
mkdir -p logs

# ensure config exists (if not, create with safe defaults)
if [ ! -f bot_config.json ]; then
  cat > bot_config.json <<'JSON'
{
  "session_name": "worker_main",
  "api_id": 1234567,
  "api_hash": "your_api_hash_here",
  "phone": "+91xxxxxxxxxx",
  "is_adding": false,
  "logged_in": false,
  "source_groups": ["-1002647054427"],
  "target_groups": ["-1001823169797"],
  "delay_min": 60,
  "delay_max": 120,
  "cache_ttl_seconds": 3600,
  "PING_URL": "https://teleautomation-by9o.onrender.com"
}
JSON
fi

# small webserver (some platforms require a listening process)
PORT="${PORT:-10000}"
python3 -m http.server "${PORT}" >/dev/null 2>&1 &

# export BOT_TOKEN is expected to be set in environment by Render/host
if [ -z "${BOT_TOKEN}" ]; then
  echo "⚠️ BOT_TOKEN not set. Controller will not start properly."
fi

# launch controller
nohup python3 controller_bot.py > logs/controller.log 2>&1 &

# small sleep before starting worker so OTP/session steps aren't racing
sleep 2

# launch worker (it will check logged_in flag and exit if not logged in)
nohup python3 worker_add.py > logs/worker.log 2>&1 &

# tail logs (optional) - comment out if you don't want blocking tail
sleep 2
tail -n +1 -f logs/controller.log logs/worker.log
