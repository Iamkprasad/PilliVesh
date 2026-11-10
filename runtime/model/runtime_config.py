import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)


def command(cmd):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        # llama-cli writes version/device info to stderr on
        # some builds (plus ggml_vulkan warnings), so combine
        # both streams for reliable detection.
        combined = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        return combined
    except Exception as e:
        return f"ERROR: {e}"


def parse_llama_version(text):
    if not text or text.startswith("ERROR:"):
        return ""
    m = re.search(r"version:\s*([0-9][\w\.\-+~]*)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Fallback: first plausible version-like token.
    m = re.search(r"\b(\d+\.\d+\.\d+)\b", text)
    return m.group(1) if m else ""


def available_ram_mb():
    try:
        output = command(["free", "-m"])
        for line in output.splitlines():
            if line.startswith("Mem:"):
                fields = line.split()
                # Use available (field 6) if present, else free
                if len(fields) > 6:
                    return int(fields[6])
                if len(fields) > 3:
                    return int(fields[3])
    except Exception:
        pass
    return None


def _cpu_clusters():
    try:
        cpu_root = Path("/sys/devices/system/cpu")
        freqs = []
        for cpu_dir in sorted(cpu_root.glob("cpu[0-9]*")):
            freq_file = cpu_dir / "cpufreq" / "cpuinfo_max_freq"
            if freq_file.exists():
                try:
                    freqs.append(int(freq_file.read_text().strip()))
                except Exception:
                    pass
        if not freqs:
            return None
        clusters = {}
        for f in freqs:
            clusters[f] = clusters.get(f, 0) + 1
        big_freq = max(clusters.keys())
        return {"big_cores": clusters[big_freq], "total": len(freqs),
                "clusters_khz": clusters}
    except Exception:
        return None


def detect():
    devices = command(["llama-cli", "--list-devices"])
    version_raw = command(["llama-cli", "--version"])
    version = parse_llama_version(version_raw)

    ram = available_ram_mb()
    cpu = os.cpu_count()
    clusters = _cpu_clusters()

    vulkan = "Vulkan0:" in devices
    gpu = "Adreno (TM) 650" if "Adreno (TM) 650" in devices else None

    # Real model check: any .gguf under models/ means downloaded.
    models_dir = ROOT / "models"
    model_downloaded = False
    try:
        if models_dir.exists():
            model_downloaded = any(models_dir.glob("*.gguf"))
    except Exception:
        model_downloaded = False

    res = {
        "cpu_cores": cpu,
        "ram_available_mb": ram,
        "llama_version": version,
        "llama_version_raw": version_raw[:2000],
        "vulkan_available": vulkan,
        "gpu": gpu,
        "backend": "vulkan" if vulkan else "cpu",
        "candidate_context_sizes": [2048, 4096],
        "gpu_layer_strategy": "auto",
        "model_downloaded": model_downloaded,
    }
    if clusters:
        res["cpu_clusters"] = clusters
    return res


def save_profile():
    profile = detect()

    path = RESULTS / "runtime_profile.json"

    path.write_text(
        json.dumps(profile, indent=2),
        encoding="utf-8",
    )

    return profile, path


if __name__ == "__main__":
    profile, path = save_profile()

    print("=== LOCAL AI RUNTIME PROFILE ===")
    print(json.dumps(profile, indent=2))
    print()
    print(f"Saved: {path}")
