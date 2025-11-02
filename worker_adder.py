# worker_adder.py
import asyncio, json, random, os, sys, time
from pathlib import Path
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import InviteToChannelRequest

# --- ensure config file exists ---
CONFIG_PATH = Path("config.json")

if not CONFIG_PATH.exists():
    CONFIG_PATH.write_text(json.dumps({
        "workers": {},
        "managers": {},
        "pending_otp": {},
        "otp_codes": {},
        "otp_passwords": {},
        "otp_status": {}
    }, indent=2))

def load_cfg():
    return json.loads(CONFIG_PATH.read_text())

def save_cfg(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

async def safe_invite(client, target_entity, user):
    try:
        await client(InviteToChannelRequest(target_entity, [user]))
        return True, None
    except errors.UserPrivacyRestrictedError:
        return False, "privacy_restricted"
    except errors.UserAlreadyParticipantError:
        return False, "already"
    except Exception as e:
        return False, str(e)

async def perform_otp_flow(client, worker_name, phone):
    """Request OTP code for a phone number."""
    cfg = load_cfg()
    try:
        print(f"[{worker_name}] Sending code request to {phone} ...")
        await client.send_code_request(phone)
        cfg.setdefault("otp_status", {})[worker_name] = "waiting_for_code"
        save_cfg(cfg)
    except Exception as e:
        print(f"[{worker_name}] Error sending code request: {e}")
        cfg.setdefault("otp_status", {})[worker_name] = f"error:{e}"
        save_cfg(cfg)

async def worker_loop(worker_name):
    cfg = load_cfg()
    if worker_name not in cfg.get("workers", {}):
        print("Worker not configured in config.json")
        return

    worker_cfg = cfg["workers"][worker_name]
    session_name = worker_cfg.get("session_name", worker_name)
    api_id = int(worker_cfg.get("api_id") or os.environ.get("API_ID") or 0)
    api_hash = worker_cfg.get("api_hash") or os.environ.get("API_HASH") or ""
    phone_from_cfg = worker_cfg.get("phone")

    if not api_id or not api_hash:
        print(f"[{worker_name}] Missing API credentials. Set via /setworkercred or env.")
        return

    client = TelegramClient(session_name, api_id, api_hash)
    await client.connect()
    authorized = await client.is_user_authorized()
    print(f"[{worker_name}] Telethon client connected. Authorized? {authorized}")

    try:
        while True:
            cfg = load_cfg()

            # --- OTP Handling ---
            pending = cfg.get("pending_otp", {})
            if worker_name in pending:
                phone = pending[worker_name]
                await perform_otp_flow(client, worker_name, phone)
                await asyncio.sleep(5)

            otp_codes = cfg.get("otp_codes", {})
            if worker_name in otp_codes:
                code = otp_codes[worker_name]
                phone = cfg.get("pending_otp", {}).get(worker_name) or phone_from_cfg
                if phone:
                    try:
                        print(f"[{worker_name}] Trying sign_in with code (will not store code).")
                        await client.sign_in(phone, code)
                        print(f"[{worker_name}] Sign-in successful. Session saved.")
                        cfg.get("otp_codes", {}).pop(worker_name, None)
                        cfg.get("pending_otp", {}).pop(worker_name, None)
                        cfg.setdefault("otp_status", {})[worker_name] = "verified"
                        save_cfg(cfg)
                    except errors.SessionPasswordNeededError:
                        print(f"[{worker_name}] Two-step verification password required.")
                        cfg.setdefault("otp_status", {})[worker_name] = "waiting_for_2fa"
                        save_cfg(cfg)
                    except Exception as e:
                        print(f"[{worker_name}] sign_in error: {e}")
                        cfg.setdefault("otp_status", {})[worker_name] = f"sign_in_error:{e}"
                        save_cfg(cfg)
                        cfg.get("otp_codes", {}).pop(worker_name, None)
                        save_cfg(cfg)

            # --- handle 2FA password ---
            otp_passwords = cfg.get("otp_passwords", {})
            if worker_name in otp_passwords:
                try:
                    password = otp_passwords[worker_name]
                    print(f"[{worker_name}] Attempting 2FA password login...")
                    await client.sign_in(password=password)
                    print(f"[{worker_name}] 2FA login successful!")
                    cfg = load_cfg()
                    cfg.get("otp_passwords", {}).pop(worker_name, None)
                    cfg.setdefault("otp_status", {})[worker_name] = "verified"
                    save_cfg(cfg)
                except Exception as e:
                    print(f"[{worker_name}] 2FA login failed: {e}")
                    cfg = load_cfg()
                    cfg.setdefault("otp_status", {})[worker_name] = f"2fa_error:{e}"
                    save_cfg(cfg)

            # --- Main Adding Logic ---
            for manager_id, mdata in cfg.get("managers", {}).items():
                assigned = mdata.get("workers") or mdata.get("worker") or []
                if isinstance(assigned, str):
                    assigned = [assigned]
                if worker_name not in assigned or not mdata.get("active"):
                    continue

                src = mdata.get("source")
                tgt = mdata.get("target")
                if not src or not tgt:
                    continue

                try:
                    source_entity = await client.get_entity(src)
                    target_entity = await client.get_entity(tgt)
                    all_participants = await client.get_participants(source_entity)
                    target_participants = await client.get_participants(target_entity)
                except Exception as e:
                    print(f"[{worker_name}] Error resolving/fetching groups: {e}")
                    await asyncio.sleep(10)
                    continue

                target_ids = {u.id for u in target_participants}
                print(f"[{worker_name}] Source: {len(all_participants)}, Target: {len(target_ids)}")

                for user in all_participants:
                    if user.id in target_ids:
                        continue

                    ok, reason = await safe_invite(client, target_entity, user)
                    if ok:
                        print(f"[{worker_name}] Invited user id {user.id}.")
                    else:
                        if reason == "privacy_restricted":
                            print(f"[{worker_name}] Skipped due to privacy restrictions.")
                        elif reason == "already":
                            print(f"[{worker_name}] Already participant.")
                        else:
                            print(f"[{worker_name}] Failed: {reason}")

                    mn = int(mdata.get("delay_min_minutes", 10))
                    mx = int(mdata.get("delay_max_minutes", 15))
                    delay = random.randint(mn * 60, mx * 60)
                    print(f"[{worker_name}] Sleeping {delay} seconds.")
                    await asyncio.sleep(delay)

                    cfg = load_cfg()
                    if not cfg["managers"].get(manager_id, {}).get("active"):
                        print(f"[{worker_name}] Manager {manager_id} stopped. Exiting loop.")
                        break

            await asyncio.sleep(5)

    finally:
        await client.disconnect()
        print(f"[{worker_name}] Worker stopped and disconnected.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python worker_adder.py <worker_name>")
        exit(1)
    worker_name = sys.argv[1]
    try:
        asyncio.run(worker_loop(worker_name))
    except KeyboardInterrupt:
        print("Worker stopped by user.")
