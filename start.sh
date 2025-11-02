#!/usr/bin/env bash
echo "🚀 Starting Telegram Automation System (Controller + Worker)"
set -e

# 1️⃣ Install dependencies (only if not cached)
pip install -r requirements.txt

# 2️⃣ Ensure config.json exists and writable
mkdir -p logs
if [ ! -f config.json ]; then
  echo '{"workers": {}, "managers": {}, "pending_otp": {}, "otp_codes": {}, "otp_passwords": {}, "otp_status": {}}' > config.json
fi
chmod 666 config.json

# 3️⃣ Start a dummy web server for Render to detect the service
python3 -m http.server ${PORT:-10000} >/dev/null 2>&1 &

# 4️⃣ Start Controller bot in background
nohup python3 controller_bot.py > logs/controller_bot.log 2>&1 &
echo "🧩 Controller bot launched..."

# 5️⃣ Wait for bot init
sleep 8

# 6️⃣ Start Worker (main process, will print logs to console)
echo "⚙️ Starting worker_launcher..."
python3 worker_launcher.py > logs/worker_launcher.log 2>&1 &

# 7️⃣ Stream both logs live
sleep 2
tail -f logs/controller_bot.log logs/worker_launcher.log
