#!/usr/bin/env python3
import asyncio, json, random, logging, os
from telethon import TelegramClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("worker_add")

CONFIG_FILE = "bot_config.json"

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

async def add_loop():
    cfg = load_config()
    if not cfg["is_adding"]:
        logger.warning("🔴 is_adding = False → exiting worker.")
        return

    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()

    if not await client.is_user_authorized():
        logger.error("❌ Worker not logged in! Use /login in main bot.")
        return

    logger.info("🟢 Worker started...")
    try:
        while load_config()["is_adding"]:
            d = random.randint(cfg["delay_min"], cfg["delay_max"])
            logger.info(f"⏳ Waiting {d}s before next add...")
            await asyncio.sleep(d)
            # Placeholder: simulate add logic
            logger.info("👥 Simulated add operation done.")
    except Exception as e:
        logger.error(f"❌ Worker crashed: {e}")
    finally:
        await client.disconnect()
        logger.info("🔴 Worker stopped gracefully.")

if __name__ == "__main__":
    asyncio.run(add_loop())
