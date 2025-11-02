
# worker_adder.py
import asyncio, json, random, os, sys, time
from pathlib import Path
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import InviteToChannelRequest
# --- ensure config file exists ---
CONFIG_PATH = Path("config.json")

# Auto-create config file if missing (so worker never crashes)
if not CONFIG_PATH.exists():
    CONFIG_PATH.write_text(json.dumps({
        "workers": {},
        "managers": {},
        "pending_otp": {},
        "otp_codes": {},
        "otp_status": {}
    }, indent=2))

CONFIG_PATH = Path("config.json")

def load_cfg():
    return json.loads(CONFIG_PATH.read_text())

def save_cfg(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

async def safe_invite(client, target_entity, user):
    try:
        await client(InviteToChannelRequest(target_entity, [user]))
        return True, None
    except errors.UserPrivacyRestrictedError:
        # Privacy: do NOT share user's link/username with manager
        return False, "privacy_restricted"
    except errors.UserAlreadyParticipantError:
        return False, "already"
    except Exception as e:
        return False, str(e)

async def perform_otp_flow(client, worker_name, phone):
    """
    Called when config signals pending_otp for this worker.
    Sends code request and waits for otp_codes entry in config to sign in.
    """
    cfg = load_cfg()
    try:
        print(f"[{worker_name}] Sending code request to {phone} ...")
        await client.send_code_request(phone)
        cfg = load_cfg()
        cfg.setdefault("otp_status", {})[worker_name] = "waiting_for_code"
        save_cfg(cfg)
    except Exception as e:
        print(f"[{worker_name}] Error sending code request: {e}")
        cfg = load_cfg()
        cfg.setdefault("otp_status", {})[worker_name] = f"error:{e}"
        save_cfg(cfg)
        return

async def worker_loop(worker_name):
    cfg = load_cfg()
    if worker_name not in cfg.get("workers", {}):
        print("Worker not configured in config.json")
        return

    worker_cfg = cfg["workers"][worker_name]
    session_name = worker_cfg.get("session_name")
    # credential fallback: config -> env
    api_id = int(worker_cfg.get("api_id") or os.environ.get("API_ID") or 0)
    api_hash = worker_cfg.get("api_hash") or os.environ.get("API_HASH") or ""
    phone_from_cfg = worker_cfg.get("phone")

    if not api_id or not api_hash:
        print(f"[{worker_name}] Missing API credentials. Set via /setworkercred or env.")
        return

    client = TelegramClient(session_name, api_id, api_hash)
    await client.connect()
    print(f"[{worker_name}] Telethon client connected. Authorized? {client.is_user_authorized()}")

    # If session not authorized, we may still accept pending_otp to sign_in
    try:
        while True:
            cfg = load_cfg()
            # --- OTP handling ---
            pending = cfg.get("pending_otp", {})
            if worker_name in pending:
                phone = pending[worker_name]
                # trigger send_code_request
                await perform_otp_flow(client, worker_name, phone)
                # sleep short and continue to let manager submit OTP via bot
                await asyncio.sleep(5)

            # If OTP code submitted, attempt sign in
            otp_codes = cfg.get("otp_codes", {})
            if worker_name in otp_codes:
                code = otp_codes[worker_name]
                phone = cfg.get("pending_otp", {}).get(worker_name) or phone_from_cfg
                if not phone:
                    print(f"[{worker_name}] No phone known for OTP sign-in.")
                else:
                    try:
                        print(f"[{worker_name}] Trying sign_in with code (will not store code).")
                        await client.sign_in(phone, code)
                        print(f"[{worker_name}] Sign-in successful. Session saved: {session_name}.session")
                        # cleanup
                        cfg = load_cfg()
                        cfg.get("otp_codes", {}).pop(worker_name, None)
                        cfg.get("pending_otp", {}).pop(worker_name, None)
                        cfg.setdefault("otp_status", {})[worker_name] = "verified"
                        save_cfg(cfg)
                    except Exception as e:
                        print(f"[{worker_name}] sign_in error: {e}")
                        cfg = load_cfg()
                        cfg.setdefault("otp_status", {})[worker_name] = f"sign_in_error:{e}"
                        save_cfg(cfg)
                        # remove code to avoid endless loop; manager can submit again
                        cfg.get("otp_codes", {}).pop(worker_name, None)
                        save_cfg(cfg)

            # --- main adding logic ---
            # iterate managers and check assigned workers + active flag
            for manager_id, mdata in cfg.get("managers", {}).items():
                assigned = mdata.get("workers") or mdata.get("worker") or []
                if isinstance(assigned, str):
                    assigned = [assigned]
                if worker_name not in assigned:
                    continue
                if not mdata.get("active"):
                    continue

                src = mdata.get("source")
                tgt = mdata.get("target")
                if not src or not tgt:
                    print(f"[{worker_name}] Manager {manager_id} missing source/target.")
                    continue

                # resolve entities
                try:
                    print(f"[{worker_name}] Resolving source {src} and target {tgt} ...")
                    source_entity = await client.get_entity(src)
                    target_entity = await client.get_entity(tgt)
                except Exception as e:
                    print(f"[{worker_name}] Error resolving groups: {e}")
                    continue

                try:
                    all_participants = await client.get_participants(source_entity)
                    target_participants = await client.get_participants(target_entity)
                except Exception as e:
                    print(f"[{worker_name}] Error fetching participants: {e}")
                    await asyncio.sleep(10)
                    continue

                target_ids = {u.id for u in target_participants}
                print(f"[{worker_name}] Source members: {len(all_participants)}, Target members: {len(target_ids)}")

                # iterate and add missing
                for user in all_participants:
                    if user.id in target_ids:
                        continue
                    # Attempt invite
                    ok, reason = await safe_invite(client, target_entity, user)
                    if ok:
                        print(f"[{worker_name}] Invited user id {user.id} (no link disclosed).")
                    else:
                        # Privacy: never send username/link to manager. Only send safe summary statuses.
                        if reason == "privacy_restricted":
                            print(f"[{worker_name}] Skipped user id {user.id} due to privacy restrictions. (no link shared)")
                        elif reason == "already":
                            print(f"[{worker_name}] User id {user.id} already participant.")
                        else:
                            print(f"[{worker_name}] Failed to invite user id {user.id} => {reason}")

                    # Sleep random between manager delay window
                    mn = int(mdata.get("delay_min_minutes", 10))
                    mx = int(mdata.get("delay_max_minutes", 15))
                    sleep_seconds = random.randint(mn*60, mx*60)
                    print(f"[{worker_name}] Sleeping {sleep_seconds} seconds before next invite.")
                    await asyncio.sleep(sleep_seconds)

                    # re-load cfg and break if manager turned off
                    cfg = load_cfg()
                    if not cfg["managers"].get(manager_id, {}).get("active"):
                        print(f"[{worker_name}] Manager {manager_id} set active=false. Breaking out for this manager.")
                        break

            # small loop pause
            await asyncio.sleep(5)
    finally:
        await client.disconnect()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python worker_adder.py <worker_name>")
        exit(1)
    worker_name = sys.argv[1]
    try:
        asyncio.run(worker_loop(worker_name))
    except KeyboardInterrupt:
        print("Worker stopped by user.")
