import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)


def run_command(command):
    start = time.perf_counter()

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    elapsed = time.perf_counter() - start

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "elapsed_seconds": round(elapsed, 3),
    }


def parse_metrics(text):
    metrics = {}

    patterns = {
        "prompt_tokens_per_second": r"prompt.*?(\d+(?:\.\d+)?)\s*t/s",
        "generation_tokens_per_second": r"eval.*?(\d+(?:\.\d+)?)\s*t/s",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            metrics[key] = float(match.group(1))

    return metrics


def benchmark(model_path=None):
    profile_path = RESULTS / "runtime_profile.json"

    profile = {}
    if profile_path.exists():
        profile = json.loads(
            profile_path.read_text(encoding="utf-8")
        )

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model_path,
        "runtime": profile,
        "status": "not_run",
        "metrics": {},
        "message": "",
    }

    if not model_path:
        result["message"] = (
            "Benchmark prepared but not executed. "
            "No model has been downloaded yet."
        )

        output = RESULTS / "benchmark_latest.json"
        output.write_text(
            json.dumps(result, indent=2),
            encoding="utf-8",
        )

        return result

    command = [
        "llama-cli",
        "-m",
        model_path,
        "-p",
        "Hello. Respond with one short sentence.",
        "-n",
        "32",
    ]

    if profile.get("vulkan_available"):
        command += [
            "-ngl",
            "auto",
        ]

    execution = run_command(command)

    combined = execution["stdout"] + "\n" + execution["stderr"]

    result["status"] = (
        "success"
        if execution["returncode"] == 0
        else "failed"
    )

    result["elapsed_seconds"] = execution["elapsed_seconds"]
    result["metrics"] = parse_metrics(combined)

    if execution["returncode"] != 0:
        result["error"] = execution["stderr"][-2000:]

    output = RESULTS / "benchmark_latest.json"
    output.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )

    # Append a compact record for historical charting (best-effort).
    try:
        hist = RESULTS / "benchmark_history.jsonl"
        record = {
            "timestamp": result.get("timestamp"),
            "status": result.get("status"),
            "model": result.get("model"),
            "metrics": result.get("metrics", {}),
            "elapsed_seconds": result.get("elapsed_seconds"),
        }
        with hist.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass

    return result


if __name__ == "__main__":
    result = benchmark()

    print("=== LLM BENCHMARK ===")
    print(f"Status: {result['status']}")
    print(f"Model: {result['model']}")
    print(result["message"])

    if result["metrics"]:
        print("Metrics:")
        for key, value in result["metrics"].items():
            print(f"  {key}: {value}")
