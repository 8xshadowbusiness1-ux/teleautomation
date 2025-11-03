import asyncio, json, random, logging, os, time
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import InviteToChannelRequest, GetFullChannelRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("worker")

CONFIG = "bot_config.json"
CACHE = "members_cache.json"

def load_cfg():
    with open(CONFIG) as f: return json.load(f)

async def keep_alive_session(client):
    while True:
        try:
            await client.get_me()
            logger.info("💓 Session heartbeat OK")
        except Exception as e:
            logger.warning(f"⚠️ Heartbeat failed: {e}")
        await asyncio.sleep(300)

async def fetch_members_once(client, src_id):
    """Fetch member list once and cache locally"""
    if os.path.exists(CACHE):
        logger.info("📁 Member cache found — using saved list.")
        return json.load(open(CACHE))
    else:
        logger.info(f"📥 Fetching members from source group {src_id} ...")
        members = []
        try:
            async for user in client.iter_participants(src_id):
                members.append(user.id)
            json.dump(members, open(CACHE, "w"))
            logger.info(f"✅ Cached {len(members)} members locally.")
        except Exception as e:
            logger.error(f"❌ Member fetch error: {e}")
        return members

async def worker():
    cfg = load_cfg()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()

    if not await client.is_user_authorized():
        await client.sign_in(phone=cfg["phone"])

    logger.info("🟢 Worker connected successfully.")
    asyncio.create_task(keep_alive_session(client))

    sources = cfg["source_groups"]
    targets = cfg["target_groups"]

    while True:
        cfg = load_cfg()
        if not cfg.get("is_adding"): break

        dmin, dmax = cfg.get("delay_min", 30), cfg.get("delay_max", 60)
        logger.info(f"⚙️ Delay: {dmin}-{dmax}s")

        for src in sources:
            members = await fetch_members_once(client, src)

            for user_id in members:
                for tgt in targets:
                    try:
                        await client(InviteToChannelRequest(tgt, [user_id]))
                        delay = random.randint(dmin, dmax)
                        logger.info(f"✅ Added {user_id} → {tgt} | Sleep {delay}s")
                        await asyncio.sleep(delay)

                    except errors.FloodWaitError as e:
                        wait = e.seconds + random.randint(30, 120)
                        logger.warning(f"🚫 FloodWait {e.seconds}s → sleeping {wait}s")
                        await asyncio.sleep(wait)
                    except errors.UserAlreadyParticipantError:
                        logger.info(f"ℹ️ {user_id} already in target.")
                    except errors.UserPrivacyRestrictedError:
                        logger.warning(f"⚠️ {user_id} privacy restricted.")
                    except Exception as e:
                        logger.warning(f"⚠️ Add error: {e}")
                        await asyncio.sleep(5)

        await asyncio.sleep(15)

    await client.disconnect()
    logger.info("🛑 Worker stopped cleanly.")

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(worker())
        except Exception as e:
            logger.error(f"💥 Worker crashed: {e}")
            time.sleep(10)
