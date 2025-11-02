import asyncio, json, os
from telethon import TelegramClient
from pathlib import Path

CONFIG_PATH = Path("config.json")

def load_cfg():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps({"workers": {}, "otp_codes": {}, "otp_passwords": {}}, indent=2))
    return json.loads(CONFIG_PATH.read_text())

async def login_worker(name):
    print(f"[{name}] 🟢 Worker started, waiting for OTP or password...")
    while True:
        cfg = load_cfg()
        worker = cfg["workers"].get(name)
        if not worker:
            print(f"[{name}] ⚠️ Worker '{name}' not found in config.json")
            await asyncio.sleep(5)
            continue

        api_id = worker.get("api_id")
        api_hash = worker.get("api_hash")
        phone = worker.get("phone")

        if not api_id or not api_hash or not phone:
            print(f"[{name}] ⚠️ Missing credentials (api_id/api_hash/phone)")
            await asyncio.sleep(5)
            continue

        api_id = int(api_id)
        session_name = worker.get("session_name", f"{name}_session")
        client = TelegramClient(session_name, api_id, api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            try:
                print(f"[{name}] 📩 Sending OTP request to {phone} ...")
                await client.send_code_request(phone)
                print(f"[{name}] ✅ OTP sent successfully! Enter it using /submitotp {name} <otp>")
            except Exception as e:
                print(f"[{name}] ❌ Failed to send OTP: {e}")

        # check if OTP entered
        otp_code = cfg.get("otp_codes", {}).get(name)
        if otp_code:
            try:
                print(f"[{name}] Trying OTP {otp_code}...")
                await client.sign_in(phone=phone, code=otp_code)
                print(f"[{name}] ✅ Logged in successfully!")
                break
            except Exception as e:
                if "SESSION_PASSWORD_NEEDED" in str(e):
                    print(f"[{name}] 🔐 2FA password needed!")
                else:
                    print(f"[{name}] ⚠️ OTP login failed: {e}")

        otp_pass = cfg.get("otp_passwords", {}).get(name)
        if otp_pass:
            try:
                await client.sign_in(password=otp_pass)
                print(f"[{name}] ✅ 2FA login successful!")
                break
            except Exception as e:
                print(f"[{name}] ❌ Wrong password: {e}")

        await asyncio.sleep(5)

asyncio.run(login_worker("worker1"))
