import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

RESULTS = ROOT / "results"
LOGS = ROOT / "logs"

RESULTS.mkdir(exist_ok=True)
LOGS.mkdir(exist_ok=True)

TELEMETRY_FILE = RESULTS / "telemetry_latest.json"


def command(cmd):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        # Combine stdout+stderr: llama-cli emits version and
        # vulkan warnings on stderr on Android builds.
        combined = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        return combined
    except Exception as e:
        return f"ERROR: {e}"


def memory_info():
    output = command(["free", "-m"])

    data = {}

    for line in output.splitlines():
        if line.startswith("Mem:"):
            fields = line.split()

            if len(fields) >= 7:
                data = {
                    "total_mb": int(fields[1]),
                    "used_mb": int(fields[2]),
                    "free_mb": int(fields[3]),
                    "available_mb": int(fields[6]),
                }

        elif line.startswith("Swap:"):
            fields = line.split()

            if len(fields) >= 4:
                data["swap_total_mb"] = int(fields[1])
                data["swap_used_mb"] = int(fields[2])
                data["swap_free_mb"] = int(fields[3])

    return data


def temperatures():
    result = {}

    thermal_path = Path("/sys/class/thermal")

    if not thermal_path.exists():
        return result

    for zone in thermal_path.glob("thermal_zone*"):
        try:
            name = (zone / "type").read_text().strip()
            raw = (zone / "temp").read_text().strip()

            if raw.isdigit():
                value = int(raw)

                # Most Android thermal zones expose millidegrees C.
                if 1000 <= value <= 150000:
                    result[name] = round(value / 1000, 1)

        except Exception:
            continue

    return result


def gpu_info():
    output = command(["llama-cli", "--list-devices"])

    return {
        "vulkan_available": "Vulkan0:" in output,
        "device": (
            "Adreno (TM) 650"
            if "Adreno (TM) 650" in output
            else None
        ),
        "raw": output,
    }


def load_json(path):
    if not path.exists():
        return {}

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return {}


def collect():
    profile = load_json(
        RESULTS / "runtime_profile.json"
    )

    benchmark = load_json(
        RESULTS / "benchmark_latest.json"
    )

    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),

        "system": {
            "cpu_cores": os.cpu_count(),
            "memory": memory_info(),
            "temperatures_c": temperatures(),
        },

        "gpu": gpu_info(),

        "runtime": {
            "backend": profile.get("backend"),
            "llama_version": profile.get("llama_version"),
            "model_downloaded": profile.get(
                "model_downloaded",
                False,
            ),
        },

        "benchmark": {
            "status": benchmark.get("status"),
            "model": benchmark.get("model"),
            "metrics": benchmark.get("metrics", {}),
        },
    }

    return data


def save():
    data = collect()

    TELEMETRY_FILE.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )

    return data


if __name__ == "__main__":
    data = save()

    print("=== LOCAL AI TELEMETRY ===")
    print(json.dumps(data, indent=2))
    print()
    print(f"Saved: {TELEMETRY_FILE}")
