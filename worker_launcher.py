import asyncio, json
from telethon import TelegramClient
from pathlib import Path

CONFIG_PATH = Path("config.json")

def load_cfg():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps({"workers": {}}, indent=2))
    return json.loads(CONFIG_PATH.read_text())

async def login_worker(name):
    print(f"\n[{name}] 🟢 Worker started... checking config.json\n")

    cfg = load_cfg()
    print("📄 DEBUG | Loaded config.json data:\n", json.dumps(cfg, indent=2))

    worker = cfg["workers"].get(name)
    if not worker:
        print(f"[{name}] ❌ Worker not found in config.json")
        return

    api_id = worker.get("api_id")
    api_hash = worker.get("api_hash")
    phone = worker.get("phone")

    if not api_id or not api_hash or not phone:
        print(f"[{name}] ⚠️ Missing credentials (api_id/api_hash/phone)")
        return

    client = TelegramClient(worker["session_name"], int(api_id), api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print(f"[{name}] 📩 Sending OTP request to {phone} ...")
        try:
            await client.send_code_request(phone)
            print(f"[{name}] ✅ OTP sent! Use /submitotp {name} <code>")
        except Exception as e:
            print(f"[{name}] ❌ Failed to send OTP: {e}")
    else:
        print(f"[{name}] ✅ Already authorized.")

asyncio.run(login_worker("worker1"))
