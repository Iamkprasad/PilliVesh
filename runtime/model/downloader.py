"""Safe model downloader for PilliVesh (stdlib only).

Rules:
- Only catalog allow-list ids are accepted. Arbitrary URLs are refused.
- Streams to models/<file>.part, verifies size, then renames atomically.
- Progress is published to results/download_progress.json for the dashboard.
- No shell, no subprocess, single download at a time (thread lock).
"""
import json
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "models"
RESULTS = ROOT / "results"
PROGRESS_FILE = RESULTS / "download_progress.json"

CHUNK = 65536
_lock = threading.Lock()
_active = {"model_id": None}


def _progress():
    try:
        if PROGRESS_FILE.exists():
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"status": "idle"}


def _write_progress(data):
    data["updated"] = datetime.now(timezone.utc).isoformat()
    RESULTS.mkdir(exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def status():
    """Current download state for the API: idle/downloading/complete/error."""
    with _lock:
        active = _active["model_id"]
    state = _progress()
    state["active"] = active
    return state


def installed():
    """Actually installed model files (.gguf only; placeholders excluded)."""
    found = []
    try:
        if MODELS_DIR.exists():
            for p in sorted(MODELS_DIR.iterdir()):
                if p.is_file() and p.suffix.lower() == ".gguf":
                    try:
                        size = p.stat().st_size
                    except Exception:
                        size = None
                    found.append({"name": p.name, "size_bytes": size})
    except Exception:
        pass
    return found


def _stream(url, dest, model_id, size_mb):
    req = urllib.request.Request(url, headers={"User-Agent": "PilliVesh/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        total = resp.length or (size_mb * 1024 * 1024 if size_mb else 0)
        done = 0
        start = time.time()
        with dest.open("wb") as f:
            while True:
                chunk = resp.read(CHUNK)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if done % (CHUNK * 16) == 0:
                    _write_progress({
                        "status": "downloading",
                        "model_id": model_id,
                        "bytes_done": done,
                        "bytes_total": total or None,
                        "elapsed_seconds": round(time.time() - start, 1),
                    })
    return done


def download(model_id, dest_dir=None):
    """Download a catalog model. Raises ValueError on any problem."""
    from runtime.model.catalog import get_model

    entry = get_model(model_id)  # allow-list gate; raises for unknown ids
    target_dir = Path(dest_dir) if dest_dir else MODELS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    final = target_dir / entry["filename"]
    part = target_dir / (entry["filename"] + ".part")

    if final.exists():
        _write_progress({"status": "complete", "model_id": model_id,
                         "path": str(final)})
        try:
            from runtime.model.runtime_config import save_profile
            save_profile()
        except Exception:
            pass
        return {"status": "already_installed", "path": str(final)}

    with _lock:
        if _active["model_id"] is not None:
            raise ValueError("Another download is already running")
        _active["model_id"] = model_id
    try:
        _write_progress({"status": "downloading", "model_id": model_id,
                         "bytes_done": 0,
                         "bytes_total": entry["size_mb"] * 1024 * 1024})
        done = _stream(entry["url"], part, model_id, entry["size_mb"])
        minimum = int(entry["size_mb"] * 1024 * 1024 * 0.95)
        if done < minimum:
            part.unlink(missing_ok=True)
            raise ValueError(
                f"Download incomplete: got {done} bytes, "
                f"expected ~{minimum}+ bytes"
            )
        part.rename(final)
        _write_progress({"status": "complete", "model_id": model_id,
                         "bytes_done": done, "path": str(final)})
        try:
            from runtime.model.runtime_config import save_profile
            save_profile()
            from runtime.monitor.monitor import log_event
            log_event("model_download", {"model": entry["filename"],
                                         "bytes": done})
        except Exception:
            pass
        return {"status": "complete", "path": str(final)}
    except Exception as e:
        if not isinstance(e, ValueError) or "incomplete" not in str(e):
            try:
                part.unlink(missing_ok=True)
            except Exception:
                pass
        _write_progress({"status": "error", "model_id": model_id,
                         "error": str(e)[:500]})
        raise
    finally:
        with _lock:
            _active["model_id"] = None


def download_async(model_id):
    """Start a background download thread. Raises if busy/unknown."""
    from runtime.model.catalog import get_model
    get_model(model_id)  # validate early so API can return 400 fast
    with _lock:
        if _active["model_id"] is not None:
            raise ValueError("Another download is already running")
    thread = threading.Thread(target=_background, args=(model_id,),
                              daemon=True)
    thread.start()
    return {"started": True, "model_id": model_id}


def _background(model_id):
    try:
        download(model_id)
    except Exception:
        pass  # error already recorded in progress file


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: python3 -m runtime.model.downloader <model-id>")
        print("       python3 -m runtime.model.downloader --status")
        sys.exit(1)
    if sys.argv[1] == "--status":
        print(json.dumps(status(), indent=2))
    else:
        print(json.dumps(download(sys.argv[1]), indent=2))
