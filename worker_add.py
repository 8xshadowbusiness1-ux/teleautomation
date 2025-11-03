import asyncio, json, random, logging
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import InviteToChannelRequest

CONFIG_FILE = "bot_config.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("worker")

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

async def keep_alive_session(client):
    """Keeps Telegram session alive forever"""
    while True:
        try:
            await client.get_me()
            logger.info("💓 Session heartbeat sent.")
        except Exception as e:
            logger.warning(f"Heartbeat failed: {e}")
        await asyncio.sleep(300)  # 5 min

async def worker():
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()

    if not await client.is_user_authorized():
        logger.error("❌ Worker not logged in.")
        return

    logger.info("🟢 Worker connected successfully.")
    asyncio.create_task(keep_alive_session(client))

    sources = cfg.get("source_groups", [])
    targets = cfg.get("target_groups", [])
    dmin = cfg.get("delay_min", 15)
    dmax = cfg.get("delay_max", 30)

    while cfg.get("is_adding", True):
        for src in sources:
            try:
                await client.get_dialogs()
                source = await client.get_entity(src)
                async for user in client.iter_participants(source):
                    for tgt in targets:
                        try:
                            target = await client.get_entity(tgt)
                            await client(InviteToChannelRequest(target, [user]))
                            delay = random.randint(dmin, dmax)
                            logger.info(f"✅ Added {user.id} → {tgt}, waiting {delay}s")
                            await asyncio.sleep(delay)
                        except errors.FloodWaitError as e:
                            logger.warning(f"Flood wait {e.seconds}s")
                            await asyncio.sleep(e.seconds)
                        except Exception as e:
                            logger.warning(f"⚠️ Add error: {e}")
            except Exception as e:
                logger.warning(f"❌ Source fetch error: {e}")
        cfg = load_config()
    await client.disconnect()
    logger.info("🔴 Worker stopped gracefully.")

if __name__ == "__main__":
    asyncio.run(worker())
