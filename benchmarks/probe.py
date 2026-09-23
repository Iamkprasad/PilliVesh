"""Light benchmark probe against the resident llama-server (port 8081).

Avoids spawning a second llama-cli process (full llm_benchmark.py path).
Each successful probe is recorded:
  - results/benchmark_latest.json      (global Home panel)
  - results/benchmark_history.jsonl    (global chart, last 50)
  - results/model_stats/<model_id>.jsonl (per-model samples, last 200)

Summaries are computed on read (handlers.get_models / get_model_stats).
"""
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
MODEL_STATS_DIR = RESULTS / "model_stats"
BENCH_LATEST = RESULTS / "benchmark_latest.json"
BENCH_HISTORY = RESULTS / "benchmark_history.jsonl"
HISTORY_KEEP = 50
STATS_KEEP = 200

PROMPT = (
    "Write exactly three short sentences about local AI running on a phone. "
    "Do not stop early."
)
MAX_TOKENS = 48
HTTP_TIMEOUT = 60.0


def _now():
    return datetime.now(timezone.utc).isoformat()


def _model_reachable():
    try:
        from runtime.model import router as router_mod
        if router_mod.router_running():
            return True
        return bool(router_mod._http_health())
    except Exception:
        return False


def _resident_model_id():
    try:
        from runtime.model import router as router_mod
        return router_mod.current_model_id() or "unknown"
    except Exception:
        return "unknown"


def _profile():
    try:
        p = RESULTS / "runtime_profile.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _metrics_from_response(payload, elapsed):
    """Prefer llama-server timings; fall back to wall-clock estimate."""
    metrics = {}
    timings = payload.get("timings") or {}
    if not isinstance(timings, dict):
        timings = {}

    def _f(val):
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    pps = _f(timings.get("prompt_per_second"))
    gps = _f(timings.get("predicted_per_second"))
    # Treat 0 / negative as missing (happens when n_predict is tiny).
    if pps is not None and pps > 0:
        metrics["prompt_tokens_per_second"] = round(pps, 2)
    if gps is not None and gps > 0:
        metrics["generation_tokens_per_second"] = round(gps, 2)

    usage = payload.get("usage") or {}
    pt = usage.get("prompt_tokens")
    ct = usage.get("completion_tokens")
    try:
        pt = int(pt) if pt is not None else None
    except (TypeError, ValueError):
        pt = None
    try:
        ct = int(ct) if ct is not None else None
    except (TypeError, ValueError):
        ct = None

    # Timing windows (ms) → seconds, for tighter estimates.
    # Guard against llama-server's degenerate 0.001ms predicted_ms on 1-token EOS.
    prompt_ms = _f(timings.get("prompt_ms"))
    pred_ms = _f(timings.get("predicted_ms"))
    prompt_s = (prompt_ms / 1000.0) if prompt_ms and prompt_ms >= 1.0 else None
    pred_s = (pred_ms / 1000.0) if pred_ms and pred_ms >= 1.0 else None

    if "prompt_tokens_per_second" not in metrics and pt:
        denom = prompt_s if prompt_s else max((elapsed or 1.0) * 0.3, 0.001)
        metrics["prompt_tokens_per_second"] = round(pt / denom, 2)
    if "generation_tokens_per_second" not in metrics and ct:
        denom = pred_s if pred_s else max((elapsed or 1.0) * 0.7, 0.001)
        # Clamp absurd values from bad timing windows.
        est = ct / denom
        if est > 0 and est < 10000:
            metrics["generation_tokens_per_second"] = round(est, 2)
    return metrics, pt, ct


def _append_jsonl(path, record, keep):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > keep:
            path.write_text(
                "\n".join(lines[-keep:]) + "\n", encoding="utf-8"
            )
    except Exception:
        pass


def run_probe(force=False):
    """One light completion against the resident server. Returns result dict.

    force: currently unused (reserved); probe always runs when reachable.
    """
    ts = _now()
    model_id = _resident_model_id()

    if not _model_reachable():
        result = {
            "timestamp": ts,
            "model": model_id,
            "runtime": _profile(),
            "status": "waiting",
            "metrics": {},
            "elapsed_seconds": None,
            "message": "No model loaded. Load a model to run the probe.",
        }
        # Do not clobber a prior success with waiting state for the chart.
        try:
            if BENCH_LATEST.exists():
                prior = json.loads(BENCH_LATEST.read_text(encoding="utf-8"))
                if prior.get("status") == "success":
                    result["message"] = (
                        "No model loaded (showing last successful run)."
                    )
                    result["metrics"] = prior.get("metrics", {})
                    result["model"] = prior.get("model") or model_id
                    result["elapsed_seconds"] = prior.get("elapsed_seconds")
                    result["status"] = "stale"
        except Exception:
            pass
        return result

    payload = {
        "model": "local",
        "messages": [
            {
                "role": "user",
                "content": (
                    "Write exactly three short sentences about local AI "
                    "running on a phone. Do not stop early."
                ),
            }
        ],
        "max_tokens": MAX_TOKENS,
        "temperature": 0.7,
        "stream": False,
    }
    try:
        from runtime.model import router as router_mod
        url = (
            f"http://{router_mod.ROUTER_HOST}:{router_mod.ROUTER_PORT}"
            f"/v1/chat/completions"
        )
    except Exception:
        url = "http://127.0.0.1:8081/v1/chat/completions"

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "PilliVesh/1.0",
        },
        method="POST",
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        elapsed = round(time.perf_counter() - start, 3)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:400]
        return {
            "timestamp": ts,
            "model": model_id,
            "runtime": _profile(),
            "status": "failed",
            "metrics": {},
            "elapsed_seconds": None,
            "message": f"Probe HTTP {e.code}: {detail}",
        }
    except Exception as e:
        return {
            "timestamp": ts,
            "model": model_id,
            "runtime": _profile(),
            "status": "failed",
            "metrics": {},
            "elapsed_seconds": None,
            "message": f"Probe failed: {e}",
        }

    metrics, pt, ct = _metrics_from_response(body, elapsed)
    # Chat completions report usage on the response.
    if pt is None or ct is None:
        usage = body.get("usage") or {}
        if pt is None:
            pt = usage.get("prompt_tokens")
        if ct is None:
            ct = usage.get("completion_tokens")
    status = "success" if metrics.get("generation_tokens_per_second") else (
        "success" if metrics else "failed"
    )
    result = {
        "timestamp": ts,
        "model": model_id,
        "runtime": _profile(),
        "status": status,
        "metrics": metrics,
        "elapsed_seconds": elapsed,
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "message": (
            "Light probe vs resident llama-server."
            if status == "success"
            else "Probe ran but no tok/s metrics returned."
        ),
    }

    if status != "success":
        return result

    # Persist global latest + history + per-model sample.
    try:
        RESULTS.mkdir(exist_ok=True)
        BENCH_LATEST.write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        hist_rec = {
            "timestamp": result["timestamp"],
            "status": result["status"],
            "model": result["model"],
            "metrics": result["metrics"],
            "elapsed_seconds": result["elapsed_seconds"],
        }
        _append_jsonl(BENCH_HISTORY, hist_rec, HISTORY_KEEP)
        stats_rec = {
            "timestamp": result["timestamp"],
            "model_id": model_id,
            "status": status,
            "prompt_tokens_per_second": metrics.get("prompt_tokens_per_second"),
            "generation_tokens_per_second": metrics.get(
                "generation_tokens_per_second"
            ),
            "elapsed_seconds": elapsed,
            "prompt_tokens": pt,
            "completion_tokens": ct,
        }
        _append_jsonl(
            MODEL_STATS_DIR / f"{model_id}.jsonl", stats_rec, STATS_KEEP
        )
    except Exception:
        pass

    return result


def summarize(model_id, limit=50):
    """Aggregate per-model stats for the Models list / comparison panel."""
    path = MODEL_STATS_DIR / f"{model_id}.jsonl"
    samples = []
    try:
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
            for line in lines[-limit:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    samples.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        samples = []

    gen = [
        s["generation_tokens_per_second"]
        for s in samples
        if s.get("generation_tokens_per_second") is not None
        and s.get("status") == "success"
    ]
    pr = [
        s["prompt_tokens_per_second"]
        for s in samples
        if s.get("prompt_tokens_per_second") is not None
        and s.get("status") == "success"
    ]
    lat = [
        s["elapsed_seconds"]
        for s in samples
        if s.get("elapsed_seconds") is not None
        and s.get("status") == "success"
    ]

    def _avg(xs):
        return round(sum(xs) / len(xs), 2) if xs else None

    spark = gen[-20:]
    return {
        "runs": len(gen),
        "last": samples[-1].get("timestamp") if samples else None,
        "avg_generation_tps": _avg(gen),
        "min_generation_tps": round(min(gen), 2) if gen else None,
        "max_generation_tps": round(max(gen), 2) if gen else None,
        "avg_prompt_tps": _avg(pr),
        "avg_latency_ms": (
            round(sum(lat) / len(lat) * 1000, 0) if lat else None
        ),
        "spark": spark,
        "recent": samples[-10:][::-1],
    }


if __name__ == "__main__":
    print(json.dumps(run_probe(), indent=2))
