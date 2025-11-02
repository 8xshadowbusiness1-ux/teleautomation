#!/usr/bin/env python3
import asyncio, json, random, logging, os
from telethon import TelegramClient, errors
from telethon.tl import functions

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("worker_add")

CONFIG_FILE = "bot_config.json"

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


async def add_loop():
    cfg = load_config()
    if not cfg.get("is_adding"):
        logger.warning("🔴 is_adding = False → exiting worker.")
        return

    session_path = f"{cfg['session_name']}.session"
    client = TelegramClient(session_path, cfg["api_id"], cfg["api_hash"])

    for i in range(3):
        try:
            await client.connect()
            break
        except Exception as e:
            logger.warning(f"⚠️ Retry {i+1}/3 connect failed: {e}")
            await asyncio.sleep(3)
    else:
        logger.error("❌ Could not connect after 3 retries.")
        return

    if not await client.is_user_authorized():
        logger.error("❌ Worker not logged in! Use /login + /otp again.")
        return

    await client.start()
    logger.info("🟢 Worker fully logged in and active!")

    try:
        while load_config().get("is_adding"):
            cfg = load_config()
            sources = cfg.get("source_groups", [])
            targets = cfg.get("target_groups", [])

            if not sources or not targets:
                logger.warning("⚠️ No source/target groups set.")
                await asyncio.sleep(10)
                continue

            for src in sources:
                try:
                    src_entity = await client.get_entity(int(src))
                    participants = await client.get_participants(src_entity)
                except Exception as e:
                    logger.error(f"⚠️ Failed to fetch source {src}: {e}")
                    continue

                for user in participants:
                    for tgt in targets:
                        try:
                            # ✅ Handle both @username or ID
                            if str(tgt).startswith("-100"):
                                entity = await client.get_entity(int(tgt))
                            else:
                                entity = await client.get_entity(tgt)

                            await client(functions.channels.InviteToChannelRequest(
                                channel=entity,
                                users=[user.id]
                            ))
                            logger.info(f"✅ Added {user.first_name} to {tgt}")
                        except errors.UserPrivacyRestrictedError:
                            logger.warning(f"🚫 Privacy restricted: {user.first_name}")
                        except errors.FloodWaitError as e:
                            logger.warning(f"⏳ Flood wait {e.seconds}s")
                            await asyncio.sleep(e.seconds + 5)
                        except errors.UserAlreadyParticipantError:
                            logger.info(f"⚠️ Already in target: {user.first_name}")
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to add {user.id}: {e}")

                        delay = random.randint(cfg["delay_min"], cfg["delay_max"])
                        logger.info(f"⏳ Waiting {delay}s before next add...")
                        await asyncio.sleep(delay)

            logger.info("♻️ Loop complete, checking again...")

    except Exception as e:
        logger.error(f"❌ Worker crashed: {e}")
    finally:
        await client.disconnect()
        logger.info("🔴 Worker stopped gracefully.")


if __name__ == "__main__":
    asyncio.run(add_loop())
