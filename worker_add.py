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
    if not cfg["is_adding"]:
        logger.warning("🔴 is_adding = False → exiting worker.")
        return

    # ✅ Ensure .session file path stays persistent even after restart
    session_name = cfg.get("session_name", "worker_main")
    session_path = os.path.join("/tmp", f"{session_name}.session")

    client = TelegramClient(session_path, cfg["api_id"], cfg["api_hash"])

    # Try to connect safely
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

    # ✅ Auto login check
    if not await client.is_user_authorized():
        phone = cfg.get("phone")
        if not phone:
            logger.error("📵 No phone number in config.json")
            return

        logger.info("📲 Sending login code...")
        try:
            await client.send_code_request(phone)
            logger.warning("⚠️ Please enter OTP in Telegram bot using /otp <code>")
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"❌ OTP send failed: {e}")
            return

    # Check again after OTP step
    if not await client.is_user_authorized():
        logger.error("❌ Worker still not logged in! Run /login + /otp again.")
        return

    logger.info("🟢 Worker logged in and ready.")
    try:
        while load_config()["is_adding"]:
            cfg = load_config()
            sources = cfg.get("source_groups", [])
            targets = cfg.get("target_groups", [])

            if not sources or not targets:
                logger.warning("⚠️ No source/target groups set.")
                await asyncio.sleep(10)
                continue

            for src in sources:
                async for user in client.get_participants(src, aggressive=True):
                    for tgt in targets:
                        try:
                            await client(functions.channels.InviteToChannelRequest(
                                channel=tgt,
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

            logger.info("♻️ Loop completed, checking again...")

    except Exception as e:
        logger.error(f"❌ Worker crashed: {e}")
    finally:
        await client.disconnect()
        logger.info("🔴 Worker stopped gracefully.")

if __name__ == "__main__":
    asyncio.run(add_loop())
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
    if not cfg["is_adding"]:
        logger.warning("🔴 is_adding = False → exiting worker.")
        return

    # ✅ Ensure .session file path stays persistent even after restart
    session_name = cfg.get("session_name", "worker_main")
    session_path = os.path.join("/tmp", f"{session_name}.session")

    client = TelegramClient(session_path, cfg["api_id"], cfg["api_hash"])

    # Try to connect safely
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

    # ✅ Auto login check
    if not await client.is_user_authorized():
        phone = cfg.get("phone")
        if not phone:
            logger.error("📵 No phone number in config.json")
            return

        logger.info("📲 Sending login code...")
        try:
            await client.send_code_request(phone)
            logger.warning("⚠️ Please enter OTP in Telegram bot using /otp <code>")
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"❌ OTP send failed: {e}")
            return

    # Check again after OTP step
    if not await client.is_user_authorized():
        logger.error("❌ Worker still not logged in! Run /login + /otp again.")
        return

    logger.info("🟢 Worker logged in and ready.")
    try:
        while load_config()["is_adding"]:
            cfg = load_config()
            sources = cfg.get("source_groups", [])
            targets = cfg.get("target_groups", [])

            if not sources or not targets:
                logger.warning("⚠️ No source/target groups set.")
                await asyncio.sleep(10)
                continue

            for src in sources:
                async for user in client.get_participants(src, aggressive=True):
                    for tgt in targets:
                        try:
                            await client(functions.channels.InviteToChannelRequest(
                                channel=tgt,
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

            logger.info("♻️ Loop completed, checking again...")

    except Exception as e:
        logger.error(f"❌ Worker crashed: {e}")
    finally:
        await client.disconnect()
        logger.info("🔴 Worker stopped gracefully.")

if __name__ == "__main__":
    asyncio.run(add_loop())
