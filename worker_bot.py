import asyncio, json, random, logging, time, os
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.types import PeerChannel

CONFIG_FILE = "bot_config.json"
CACHE_FILE = "member_cache.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("worker")


def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


async def keep_alive_session(client):
    while True:
        try:
            await client.get_me()
            logger.info("💓 Worker heartbeat sent.")
        except Exception as e:
            logger.warning(f"⚠️ Heartbeat failed: {e}")
        await asyncio.sleep(600)


async def get_cached_members(group_id):
    if not os.path.exists(CACHE_FILE):
        return []
    with open(CACHE_FILE, "r") as f:
        cache = json.load(f)
    return cache.get(str(group_id), [])


async def save_cached_members(group_id, members):
    cache = {}
    if os.path.exists(CACHE_FILE):
        cache = json.load(open(CACHE_FILE))
    cache[str(group_id)] = [m.id for m in members]
    json.dump(cache, open(CACHE_FILE, "w"), indent=2)


async def worker():
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()

    if not await client.is_user_authorized():
        logger.error("⚠️ Not logged in. Login via controller first.")
        return

    logger.info("🟢 Worker connected successfully.")
    asyncio.create_task(keep_alive_session(client))

    added_count = 0
    start_time = time.time()

    while cfg.get("is_adding", False):
        cfg = load_config()
        sources = cfg.get("source_groups", [])
        targets = cfg.get("target_groups", [])
        dmin, dmax = int(cfg["delay_min"]), int(cfg["delay_max"])

        for src in sources:
            try:
                members = await get_cached_members(src)
                if not members:
                    logger.info(f"📥 Fetching members for {src}")
                    participants = await client.get_participants(PeerChannel(int(src)))
                    await save_cached_members(src, participants)
                    members = [p.id for p in participants]
                    logger.info(f"💾 Cached {len(members)} members.")
                else:
                    logger.info(f"⚡ Loaded {len(members)} members from cache.")

                for user_id in members:
                    for tgt in targets:
                        try:
                            await client(InviteToChannelRequest(int(tgt), [user_id]))
                            added_count += 1
                            delay = random.randint(dmin, dmax)
                            logger.info(f"✅ Added {user_id} → {tgt} | Wait {delay}s")
                            progress = {
                                "source": src,
                                "target": tgt,
                                "added": added_count,
                                "delay_min": dmin,
                                "delay_max": dmax,
                                "uptime": f"{round((time.time() - start_time)/60)}m"
                            }
                            json.dump(progress, open("progress.json", "w"), indent=2)
                            await asyncio.sleep(delay)

                        except errors.FloodWaitError as e:
                            logger.warning(f"🚫 Flood wait {e.seconds}s – pausing.")
                            await asyncio.sleep(e.seconds + 10)
                        except errors.UserPrivacyRestrictedError:
                            logger.warning(f"⚠️ Skipped: privacy restricted.")
                            await asyncio.sleep(2)
                        except errors.UserAlreadyParticipantError:
                            logger.info(f"ℹ️ Already in target.")
                            await asyncio.sleep(2)
                        except Exception as e:
                            logger.warning(f"⚠️ Add error: {e}")
                            await asyncio.sleep(3)

            except Exception as e:
                logger.error(f"❌ Source error: {e}")
                await asyncio.sleep(10)

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
