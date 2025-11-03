import asyncio, json, random, logging, time
from telethon import TelegramClient, errors

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
config = json.load(open("bot_config.json"))
client = TelegramClient(config["session_name"], config["api_id"], config["api_hash"])

async def run_worker():
    await client.connect()
    if not await client.is_user_authorized():
        logging.warning("⚠️ Not logged in. Login via controller first.")
        return

    logging.info("🟢 Worker connected successfully.")
    delay_min, delay_max = config["delay_min"], config["delay_max"]
    logging.info(f"⚙️ Current delay range: {delay_min}-{delay_max}s")

    progress = {"source": config["source_groups"][0], "target": config["target_groups"][0], "added": 0,
                "delay_min": delay_min, "delay_max": delay_max, "uptime": "0m"}

    while True:
        try:
            progress["uptime"] = f"{round(time.time()/60)}m"
            json.dump(progress, open("progress.json", "w"))
            await asyncio.sleep(random.randint(delay_min, delay_max))
            # Flood Control Example
            if random.random() < 0.1:
                raise errors.FloodWaitError(request=None, seconds=20)
        except errors.FloodWaitError as e:
            logging.warning(f"🚫 Flood wait {e.seconds}s – pausing.")
            await asyncio.sleep(e.seconds + 5)
        except Exception as e:
            logging.error(f"❌ {e}")
            await asyncio.sleep(10)

asyncio.run(run_worker())
