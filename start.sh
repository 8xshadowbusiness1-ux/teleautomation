#!/usr/bin/env bash
echo "🚀 Starting Telegram Automation (Controller + Worker Ready)"
set -e  # Stop script if any command fails

# ========== 1️⃣ INSTALL DEPENDENCIES ==========
pip install --no-cache-dir -r requirements.txt

# ========== 2️⃣ VERIFY ENVIRONMENT VARIABLES ==========
if [ -z "$BOT_TOKEN" ]; then
  echo "❌ BOT_TOKEN not set! Please add it in Render → Environment → Environment Variables."
  exit 1
fi

# ========== 3️⃣ CONFIG FILE SETUP ==========
if [ ! -f bot_config.json ]; then
  echo "🛠️ Creating default bot_config.json..."
  cat <<EOF > bot_config.json
{
  "session_name": "worker_main",
  "api_id": 123456,
  "api_hash": "your_api_hash_here",
  "phone": "+910000000000",
  "is_adding": false,
  "logged_in": false,
  "source_groups": [],
  "target_groups": [],
  "delay_min": 60,
  "delay_max": 120
}
EOF
fi

# ========== 4️⃣ CREATE LOG DIRECTORY ==========
mkdir -p logs

# ========== 5️⃣ START DUMMY WEB SERVER ==========
# Render requires a service to bind to $PORT, so we keep this alive silently.
PORT=${PORT:-10000}
python3 -m http.server $PORT >/dev/null 2>&1 &

echo "🌐 Web server running on port $PORT (Render requirement OK)"

# ========== 6️⃣ START CONTROLLER BOT ==========
echo "⚙️ Launching controller bot..."
python3 controller_bot.py

# NOTE:
# Do NOT use nohup or & here — Render requires the main process to stay in foreground.
# If you background it, Render will kill the service thinking it's idle.
