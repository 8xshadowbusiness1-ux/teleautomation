#!/usr/bin/env python3
import asyncio, json, random, logging, time, os
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.types import PeerChannel
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("worker")

CONFIG_FILE = "bot_config.json"
PROGRESS_FILE = "progress.json"

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Config load error: {e}")
        return {}

def save_progress(p):
    try:
        with open(PROGRESS_FILE, "w") as f:
            json.dump(p, f, indent=2)
    except:
        logger.exception("Cannot save progress")

async def keep_alive_session(client):
    while True:
        try:
            await client.get_me()
            logger.info("💓 Session heartbeat sent.")
        except Exception as e:
            logger.warning(f"Heartbeat failed: {e}")
        await asyncio.sleep(300)  # 5 minutes keep session alive

async def safe_get_entity(client, group_id):
    try:
        return await client.get_entity(PeerChannel(int(group_id)))
    except Exception:
        try:
            await client.get_dialogs()
            await asyncio.sleep(1)
            return await client.get_entity(PeerChannel(int(group_id)))
        except Exception as e:
            logger.warning(f"Entity fetch error ({group_id}): {e}")
            return None

def cache_filename(group_id):
    return f"members_cache_{str(group_id).lstrip('-').replace(' ', '')}.json"

def load_cache(group_id):
    fn = cache_filename(group_id)
    if not os.path.exists(fn):
        return {"ts": 0, "members": []}
    try:
        data = json.load(open(fn))
        return data
    except:
        return {"ts": 0, "members": []}

def save_cache(group_id, members):
    fn = cache_filename(group_id)
    try:
        json.dump({"ts": int(time.time()), "members": members}, open(fn, "w"), indent=2)
    except:
        logger.exception("Saving cache failed")

async def fetch_members_with_cache(client, group_id, ttl):
    cache = load_cache(group_id)
    age = int(time.time()) - int(cache.get("ts", 0))
    if cache.get("members") and age < ttl:
        logger.info(f"Using cached members for {group_id} (age {age}s)")
        return cache["members"], age
    # fetch fresh
    try:
        ent = await safe_get_entity(client, group_id)
        if not ent:
            return [], age
        members = await client.get_participants(ent)
        # simplify to list of dicts with id and access hash etc if needed
        members_serial = []
        for m in members:
            members_serial.append({"id": m.id, "access_hash": getattr(m, "access_hash", None)})
        save_cache(group_id, members_serial)
        return members_serial, 0
    except Exception as e:
        logger.warning(f"Fetch participants failed ({group_id}): {e}")
        return cache.get("members", []), age

async def worker_loop():
    cfg = load_config()
    client = TelegramClient(cfg["session_name"], cfg["api_id"], cfg["api_hash"])
    await client.connect()
    try:
        if not await client.is_user_authorized():
            logger.warning("⚠️ Not logged in. Login via controller first.")
            await client.disconnect()
            return

        logger.info("🟢 Worker connected successfully.")
        asyncio.create_task(keep_alive_session(client))

        # live config reload
        while True:
            cfg = load_config()
            if not cfg.get("is_adding", False):
                logger.info("🔴 is_adding flag false — worker halting.")
                break

            sources = cfg.get("source_groups", [])
            targets = cfg.get("target_groups", [])
            dmin = int(cfg.get("delay_min", 15))
            dmax = int(cfg.get("delay_max", 30))
            ttl = int(cfg.get("cache_ttl_seconds", 3600))
            progress = {"source": None, "target": None, "added": 0,
                        "delay_min": dmin, "delay_max": dmax, "uptime": "0m", "cache_age_seconds": None}
            save_progress(progress)

            logger.info(f"⚙️ Current delay range: {dmin}-{dmax}s | Sources: {len(sources)} | Targets: {len(targets)}")

            for src in sources:
                # fetch members (cached)
                members, cache_age = await fetch_members_with_cache(client, src, ttl)
                progress["cache_age_seconds"] = cache_age
                progress["source"] = src
                save_progress(progress)
                if not members:
                    logger.info(f"No members found for source {src}")
                    continue

                # iterate over members
                for m in members:
                    # each loop re-load cfg so live changes considered
                    cfg = load_config()
                    if not cfg.get("is_adding"):
                        logger.info("Stop signal received during loop.")
                        break
                    targets = cfg.get("target_groups", [])
                    dmin = int(cfg.get("delay_min", dmin))
                    dmax = int(cfg.get("delay_max", dmax))

                    for tgt in targets:
                        progress["target"] = tgt
                        save_progress(progress)
                        try:
                            target_ent = await safe_get_entity(client, tgt)
                            if not target_ent:
                                continue

                            # build user entity from id (Telethon will resolve)
                            # InviteToChannelRequest expects list of users (User or InputUser)
                            await client(InviteToChannelRequest(target_ent, [m["id"]]))
                            progress["added"] += 1
                            save_progress(progress)
                            delay = random.randint(dmin, dmax)
                            logger.info(f"✅ Added {m['id']} → {tgt} | wait {delay}s")
                            await asyncio.sleep(delay)

                        except errors.FloodWaitError as e:
                            # main flood control: wait and backoff
                            wait = int(e.seconds) + 10
                            logger.warning(f"🚫 FloodWaitError: waiting {wait}s")
                            # increase delay window a bit to be cautious
                            dmin = max(dmin, dmin + 5)
                            dmax = max(dmax, dmax + 10)
                            cfg["delay_min"] = dmin
                            cfg["delay_max"] = dmax
                            save_config(cfg)
                            await asyncio.sleep(wait)
                        except errors.UserPrivacyRestrictedError:
                            logger.warning(f"⚠️ User {m['id']} privacy restricted — skipped.")
                            await asyncio.sleep(2)
                        except errors.UserAlreadyParticipantError:
                            logger.info(f"ℹ️ {m['id']} already participant in {tgt}.")
                            await asyncio.sleep(1)
                        except Exception as e:
                            logger.warning(f"Add error: {e}")
                            await asyncio.sleep(2)

                    # small sleep between users to avoid burst
                    await asyncio.sleep(random.uniform(0.5, 1.5))

                # after finishing source, small delay
                await asyncio.sleep(5)

            # update uptime
            progress["uptime"] = f"{int(time.time()/60)}m"
            save_progress(progress)

            # short sleep before next full pass
            await asyncio.sleep(10)

    finally:
        try:
            await client.disconnect()
        except:
            pass
        logger.info("🛑 Worker stopped cleanly.")

if __name__ == "__main__":
    # run forever with crash-restart inside script
    while True:
        try:
            asyncio.run(worker_loop())
        except Exception as e:
            logger.exception(f"Worker crashed: {e}")
            time.sleep(8)
