#!/usr/bin/env python3
import os, json, asyncio, random, logging
from telethon import TelegramClient, errors
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("worker")

CONFIG_FILE = "bot_config.json"

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

async def keep_session_alive(client):
    """Keeps session active to prevent auto logout"""
    while True:
        try:
            await client.get_me()
            logger.info("💓 Session heartbeat sent.")
        except Exception as e:
            logger.warning(f"⚠️ Heartbeat failed: {e}")
        await asyncio.sleep(600)  # every 10 min

async def start_worker():
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])

    # 🔁 Auto reconnect logic
    for i in range(5):
        try:
            await client.connect()
            if not await client.is_user_authorized():
                logger.warning("⚠️ Session not authorized — trying to resume login")
                await client.start(phone=cfg["phone"])
            logger.info("🟢 Worker connected successfully.")
            break
        except Exception as e:
            logger.warning(f"⚠️ Retry {i+1}/5 connect failed: {e}")
            await asyncio.sleep(5)
    else:
        logger.error("❌ Could not connect after 5 retries.")
        return

    asyncio.create_task(keep_session_alive(client))
    logger.info("🚀 Worker started and session keep-alive active.")

    try:
        while cfg.get("is_adding"):
            cfg = load_config()
            delay_min = cfg.get("delay_min", 15)
            delay_max = cfg.get("delay_max", 30)
            delay = random.randint(delay_min, delay_max)

            if not cfg["source_groups"] or not cfg["target_groups"]:
                logger.warning("⚠️ Source or target list empty. Waiting...")
                await asyncio.sleep(30)
                continue

            src = random.choice(cfg["source_groups"])
            tgt = random.choice(cfg["target_groups"])

            try:
                members = await client.get_participants(src, limit=5)
                for user in members:
                    if not cfg.get("is_adding"):
                        break

                    try:
                        await client.add_participant(tgt, user)
                        logger.info(f"✅ Added {user.id} → {tgt}")
                        await asyncio.sleep(delay)
                    except errors.FloodWaitError as e:
                        logger.warning(f"🚫 Floodwait: sleeping {e.seconds}s")
                        await asyncio.sleep(e.seconds + 5)
                    except Exception as e:
                        logger.warning(f"⚠️ Add error: {e}")

            except Exception as e:
                logger.error(f"❌ Source fetch error: {e}")
                await asyncio.sleep(30)

        logger.info("🛑 Adding stopped manually.")
    finally:
        await client.disconnect()
        logger.info("🔴 Worker stopped gracefully.")

if __name__ == "__main__":
    asyncio.run(start_worker())
