import json, os, time, subprocess
from pathlib import Path

CONFIG_PATH = Path("config.json")
running = {}

print("👷 Worker launcher started... monitoring config.json for new workers")

while True:
    try:
        if CONFIG_PATH.exists():
            cfg = json.loads(CONFIG_PATH.read_text())
            workers = cfg.get("workers", {})
            for name, data in workers.items():
                if name not in running:
                    print(f"▶️ Detected new worker '{name}', launching...")
                    running[name] = subprocess.Popen(["python3", "worker_adder.py", name])
        time.sleep(5)
    except Exception as e:
        print(f"[launcher] Error: {e}")
        time.sleep(5)
