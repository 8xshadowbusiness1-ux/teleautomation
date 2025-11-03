#!/usr/bin/env bash
echo "🚀 Starting Telegram Automation (Controller + Worker Ready)"
set -e

pip install --no-cache-dir -r requirements.txt
export PORT=${PORT:-10000}

# Dummy webserver to keep Render alive
python3 -m http.server $PORT >/dev/null 2>&1 &

echo "🌐 Webserver running on port $PORT"
python3 controller_bot.py
