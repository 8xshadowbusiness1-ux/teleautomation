#!/usr/bin/env python3
import asyncio, json, random, logging, time, os
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.types import PeerChannel

CONFIG_FILE = "bot_config.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("worker")

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Config load error: {e}")
        return {}

async def keep_alive_session(client):
    while True:
        try:
            await client.get_me()
            logger.info("💓 Session heartbeat sent.")
        except Exception as e:
            logger.warning(f"⚠️ Heartbeat failed: {e}")
        await asyncio.sleep(300)

async def safe_get_entity(client, group_id):
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
    client = TelegramClient(cfg["session_name"] + "_worker", cfg["api_id"], cfg["api_hash"])
    await client.connect()

    if not await client.is_user_authorized():
        logger.error("⚠️ Not logged in. Login via controller first.")
        await client.disconnect()
        return

    logger.info("🟢 Worker connected successfully.")
    asyncio.create_task(keep_alive_session(client))

    adaptive_multiplier = 1.0
    last_flood = 0

    while True:
        cfg = load_config()
        if not cfg.get("is_adding", False):
            logger.info("🔴 Stop flag detected. Worker halting.")
            break

        sources = cfg.get("source_groups", [])
        targets = cfg.get("target_groups", [])
        dmin = int(cfg.get("delay_min", 30) * adaptive_multiplier)
        dmax = int(cfg.get("delay_max", 60) * adaptive_multiplier)
        logger.info(f"⚙️ Delay range: {dmin}-{dmax}s | Adaptive: x{adaptive_multiplier:.2f}")

        for src in sources:
            source = await safe_get_entity(client, src)
            if not source:
                continue

            try:
                participants = await client.get_participants(source)
            except errors.FloodWaitError as e:
                logger.warning(f"🚫 Flood wait {e.seconds}s on get_participants")
                adaptive_multiplier = min(adaptive_multiplier * 1.5, 6.0)
                await asyncio.sleep(e.seconds)
                continue

            for user in participants:
                for tgt in targets:
                    try:
                        target = await safe_get_entity(client, tgt)
                        if not target: continue

                        await client(InviteToChannelRequest(target, [user]))
                        delay = random.randint(dmin, dmax)
                        logger.info(f"✅ Added {user.id} → {tgt} | Wait {delay}s")
                        await asyncio.sleep(delay)

                    except errors.FloodWaitError as e:
                        logger.warning(f"🚫 Flood wait {e.seconds}s — pausing & adapting")
                        adaptive_multiplier = min(adaptive_multiplier * 1.5, 5.0)
                        last_flood = time.time()
                        await asyncio.sleep(e.seconds)
                    except errors.UserPrivacyRestrictedError:
                        logger.warning(f"⚠️ Skipped {user.id} (privacy)")
                        await asyncio.sleep(3)
                    except errors.UserAlreadyParticipantError:
                        await asyncio.sleep(2)
                    except Exception as e:
                        logger.warning(f"⚠️ Add error: {e}")
                        await asyncio.sleep(3)

        # Recovery: if no flood for 10 min, slowly decrease adaptive multiplier
        if time.time() - last_flood > 600 and adaptive_multiplier > 1.0:
            adaptive_multiplier = max(1.0, adaptive_multiplier * 0.9)
        await asyncio.sleep(5)

    await client.disconnect()
    logger.info("🛑 Worker stopped cleanly.")

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(worker())
        except Exception as e:
            logger.error(f"💥 Worker crashed: {e}")
            time.sleep(10)
