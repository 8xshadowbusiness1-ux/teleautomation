import asyncio, json
from telethon import TelegramClient
from pathlib import Path

CONFIG_PATH = Path("config.json")

def load_cfg():
    return json.loads(CONFIG_PATH.read_text())

async def login_worker(name):
    print(f"[{name}] 🟢 Worker started...")
    while True:
        cfg = load_cfg()
        worker = cfg["workers"].get(name)
        if not worker:
            print(f"[{name}] ❌ Worker not found, waiting...")
            await asyncio.sleep(5)
            continue

        api_id = worker.get("api_id")
        api_hash = worker.get("api_hash")
        phone = worker.get("phone")

        if not api_id or not api_hash or not phone:
            print(f"[{name}] ⚠️ Missing credentials! api_id/api_hash/phone required.")
            await asyncio.sleep(5)
            continue

        client = TelegramClient(worker["session_name"], int(api_id), api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            print(f"[{name}] 📩 Sending OTP request to {phone}...")
            try:
                await client.send_code_request(phone)
                print(f"[{name}] ✅ OTP sent successfully! Submit via /submitotp {name} <code>")
            except Exception as e:
                print(f"[{name}] ⚠️ Error sending OTP: {e}")

        # OTP already submitted?
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
