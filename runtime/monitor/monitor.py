import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

EVENT_LOG = LOG_DIR / "runtime.jsonl"


def command(cmd):
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"


def snapshot():
    memory = command(["free", "-h"])
    gpu = command(["llama-cli", "--list-devices"])

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cpu_cores": os.cpu_count(),
        "memory": memory,
        "gpu": gpu,
    }


def log_event(event, data=None):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "data": data or {},
    }

    with EVENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def health_check():
    data = snapshot()

    log_event("health_check", {
        "cpu_cores": data["cpu_cores"],
        "gpu_available": "Vulkan0:" in data["gpu"],
    })

    return data


if __name__ == "__main__":
    result = health_check()

    print("=== RUNTIME HEALTH ===")
    print(json.dumps(result, indent=2))

    print("\n=== LOG ===")
    print(EVENT_LOG)
