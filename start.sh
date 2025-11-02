#!/usr/bin/env bash
echo "🚀 Starting Telegram Automation System (Controller Bot)"
set -e  # stop on error

# Install dependencies
echo "📦 Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

# Create log folder
mkdir -p logs

# Ensure config file exists
if [ ! -f bot_config.json ]; then
  echo "🧩 Creating default config file..."
  echo '{"api_id":22676464,"api_hash":"b52406ee2c61546d8b560e2d009052d3","phone":"+917671914528","session_name":"worker_main","source_groups":[],"target_groups":[],"delay_min":10,"delay_max":15,"is_adding":false,"logged_in":false}' > bot_config.json
fi

# Make config file writable
chmod 666 bot_config.json

# Export Bot Token
if [ -z "$BOT_TOKEN" ]; then
  echo "❌ BOT_TOKEN missing! Set it in Render Environment Variables."
  exit 1
fi
export BOT_TOKEN="${BOT_TOKEN}"

# Dummy HTTP server to keep Render service alive
echo "🌐 Starting dummy web server for Render port binding..."
python3 -m http.server ${PORT:-8080} >/dev/null 2>&1 &

# Small sleep to let server bind before bot start
sleep 3

# Start Controller Bot
echo "🤖 Starting Controller Bot..."
nohup python3 controller_bot.py > logs/controller.log 2>&1 &

# Display logs continuously
echo "📜 Following logs (Ctrl+C to stop view)"
tail -f logs/controller.log
