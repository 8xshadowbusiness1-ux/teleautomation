import asyncio, json, time
from telethon import TelegramClient
from pathlib import Path

CONFIG_PATH = Path("config.json")

def load_cfg():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps({
            "workers": {}, "otp_codes": {}, "otp_passwords": {}
        }, indent=2))
    return json.loads(CONFIG_PATH.read_text())

async def login_worker(name):
    print(f"[{name}] 🟢 Worker started, waiting for OTP or password...")
    while True:
        cfg = load_cfg()
        worker = cfg["workers"].get(name)
        if not worker:
            print(f"[{name}] Not found in config.json, waiting...")
            await asyncio.sleep(5)
            continue

        api_id = int(worker["api_id"])
        api_hash = worker["api_hash"]
        phone = worker["phone"]
        client = TelegramClient(worker["session_name"], api_id, api_hash)
        await client.connect()

        # --- Try OTP login ---
        otp_code = cfg.get("otp_codes", {}).get(name)
        if otp_code:
            try:
                print(f"[{name}] Trying OTP {otp_code}...")
                await client.sign_in(phone=phone, code=otp_code)
                print(f"[{name}] ✅ Logged in successfully!")
                break
            except Exception as e:
                if "SESSION_PASSWORD_NEEDED" in str(e):
                    print(f"[{name}] 🔐 2FA password required...")
                else:
                    print(f"[{name}] ⚠️ OTP login failed: {e}")

        # --- Try 2FA password ---
        otp_pass = cfg.get("otp_passwords", {}).get(name)
        if otp_pass:
            try:
                await client.sign_in(password=otp_pass)
                print(f"[{name}] ✅ 2FA login successful!")
                break
            except Exception as e:
                print(f"[{name}] ❌ Wrong password or error: {e}")

        await asyncio.sleep(5)

asyncio.run(login_worker("worker1"))
