import asyncio, json, random, logging, time, os
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.types import PeerChannel

CONFIG_FILE = "bot_config.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("worker")

def load_config():
    """Load config safely from file"""
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Config load error: {e}")
        return {}

async def keep_alive_session(client):
    """Heartbeat to keep session alive"""
    while True:
        try:
            await client.get_me()
            logger.info("💓 Session heartbeat sent.")
        except Exception as e:
            logger.warning(f"⚠️ Heartbeat failed: {e}")
        await asyncio.sleep(300)

async def safe_get_entity(client, group_id):
    """Fetch channel entity safely with retry"""
    try:
        return await client.get_entity(PeerChannel(int(group_id)))
    except Exception:
        try:
            await client.get_dialogs()
            await asyncio.sleep(2)
            return await client.get_entity(PeerChannel(int(group_id)))
        except Exception as e:
            logger.warning(f"❌ Entity fetch error ({group_id}): {e}")
            return None

async def worker():
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()

    if not await client.is_user_authorized():
        try:
            await client.sign_in(phone=cfg["phone"])
        except Exception as e:
            logger.error(f"❌ Login repair failed: {e}")
            return

    logger.info("🟢 Worker connected successfully.")
    asyncio.create_task(keep_alive_session(client))

    while True:
        cfg = load_config()  # 🔁 Live reload each loop
        if not cfg.get("is_adding", False):
            logger.info("🔴 Stop flag detected. Worker halting.")
            break

        sources = cfg.get("source_groups", [])
        targets = cfg.get("target_groups", [])
        dmin = int(cfg.get("delay_min", 15))
        dmax = int(cfg.get("delay_max", 30))

        logger.info(f"⚙️ Current delay range: {dmin}-{dmax}s | Sources: {len(sources)} | Targets: {len(targets)}")

        for src in sources:
            source = await safe_get_entity(client, src)
            if not source:
                continue

            try:
                participants = await client.get_participants(source)
            except Exception as e:
                logger.warning(f"⚠️ Participant fetch failed ({src}): {e}")
                continue

            for user in participants:
                for tgt in targets:
                    try:
                        target = await safe_get_entity(client, tgt)
                        if not target:
                            continue

                        await client(InviteToChannelRequest(target, [user]))
                        delay = random.randint(dmin, dmax)
                        logger.info(f"✅ Added {user.id} → {tgt} | Wait {delay}s")
                        await asyncio.sleep(delay)

                    except errors.FloodWaitError as e:
                        logger.warning(f"🚫 Flood wait {e.seconds}s – pausing.")
                        await asyncio.sleep(e.seconds + 10)
                    except errors.UserPrivacyRestrictedError:
                        logger.warning(f"⚠️ Skipped {user.id}: privacy restricted.")
                        await asyncio.sleep(3)
                    except errors.UserAlreadyParticipantError:
                        logger.info(f"ℹ️ {user.id} already in group.")
                        await asyncio.sleep(2)
                    except Exception as e:
                        logger.warning(f"⚠️ Add error: {e}")
                        await asyncio.sleep(2)

        await asyncio.sleep(10)

    await client.disconnect()
    logger.info("🛑 Worker stopped cleanly.")

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(worker())
        except Exception as e:
            logger.error(f"💥 Worker crashed: {e}")
            time.sleep(10)
