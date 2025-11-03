import asyncio, json, random, logging
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import InviteToChannelRequest, GetFullChannelRequest
from telethon.tl.types import PeerChannel

CONFIG_FILE = "bot_config.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("worker")

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

async def keep_alive_session(client):
    while True:
        try:
            await client.get_me()
            logger.info("💓 Session heartbeat sent.")
        except Exception as e:
            logger.warning(f"⚠️ Heartbeat failed: {e}")
        await asyncio.sleep(300)

async def safe_get_entity(client, group_id):
    """Retry-safe entity fetch"""
    try:
        return await client.get_entity(PeerChannel(int(group_id)))
    except Exception:
        try:
            # Force refresh dialogs if not found
            await client.get_dialogs()
            await asyncio.sleep(2)
            return await client.get_entity(PeerChannel(int(group_id)))
        except Exception as e:
            logger.warning(f"❌ Source fetch error: {e}")
            return None

async def worker():
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()

    # DC Auto-heal (handle migration)
    if not await client.is_user_authorized():
        try:
            await client.sign_in(phone=cfg["phone"])
        except Exception as e:
            logger.error(f"❌ Login repair failed: {e}")
            return

    logger.info("🟢 Worker connected successfully.")
    asyncio.create_task(keep_alive_session(client))

    sources = cfg.get("source_groups", [])
    targets = cfg.get("target_groups", [])
    dmin = cfg.get("delay_min", 15)
    dmax = cfg.get("delay_max", 30)

    while True:
        cfg = load_config()
        if not cfg.get("is_adding", False):
            logger.info("🔴 Stopping worker (flag off).")
            break

        for src in sources:
            source = await safe_get_entity(client, src)
            if not source:
                continue

            try:
                participants = await client.get_participants(source)
            except Exception as e:
                logger.warning(f"⚠️ Could not fetch participants: {e}")
                continue

            for user in participants:
                for tgt in targets:
                    try:
                        target = await safe_get_entity(client, tgt)
                        if not target:
                            continue

                        await client(InviteToChannelRequest(target, [user]))
                        delay = random.randint(dmin, dmax)
                        logger.info(f"✅ Added {user.id} to {tgt} | Wait {delay}s")
                        await asyncio.sleep(delay)

                    except errors.FloodWaitError as e:
                        logger.warning(f"🚫 Flood wait {e.seconds}s")
                        await asyncio.sleep(e.seconds)
                    except errors.UserPrivacyRestrictedError:
                        logger.warning(f"⚠️ User {user.id} privacy restricted.")
                        continue
                    except Exception as e:
                        logger.warning(f"⚠️ Add error: {e}")
                        continue

        await asyncio.sleep(10)

    await client.disconnect()
    logger.info("🛑 Worker stopped cleanly.")

if __name__ == "__main__":
    asyncio.run(worker())
