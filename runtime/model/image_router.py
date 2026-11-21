"""Lazy single-model sd-server supervisor for PilliVesh's image engine.

Mirrors runtime/model/router.py: fixed loopback port, one resident model, RAM
gate, state in results/, no shell, argv built from catalog paths only.
"""
import json
import os
import shutil
import signal
import subprocess
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
STATE_FILE = RESULTS / "image_router_state.json"
LOG_FILE = RESULTS / "image_router.log"

HOST = "127.0.0.1"
PORT = 8091
BASE = "http://%s:%d" % (HOST, PORT)
START_TIMEOUT = 90.0

_lock = threading.RLock()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _write_state(data):
    data["updated"] = _now()
    RESULTS.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_state():
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"running": False, "pid": None, "port": PORT, "model_id": None,
            "job_id": None}


def _pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def _http_get(path, timeout=2.0):
    req = urllib.request.Request(
        BASE + path, headers={"User-Agent": "PilliVesh/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8", "replace"))


def engine_running():
    st = read_state()
    if not st.get("running") or not _pid_alive(st.get("pid")):
        return False
    try:
        status, _ = _http_get("/sdcpp/v1/capabilities", timeout=1.5)
        return 200 <= status < 300
    except Exception:
        return False


def find_engine():
    """Resolve the native sd-server binary. No downloads here."""
    configured = os.environ.get("AI_LAB_IMAGE_ENGINE")
    if configured:
        return Path(configured)
    candidates = [
        ROOT / "bin" / "sd-server",
        Path.home() / ".local" / "opt" / "pillivesh-image" / "bin" / "sd-server",
    ]
    for path in candidates:
        if path.is_file():
            return path
    found = shutil.which("sd-server")
    return Path(found) if found else None


def current_model_id():
    if not engine_running():
        return None
    return read_state().get("model_id")


def current_job_id():
    return read_state().get("job_id")


def set_job_id(job_id):
    st = read_state()
    st["job_id"] = job_id
    _write_state(st)


def status_summary():
    st = read_state()
    running = engine_running()
    return {
        "engine_running": running,
        "port": PORT if running else None,
        "pid": st.get("pid") if running else None,
        "loaded_id": st.get("model_id") if running else None,
        "job_id": st.get("job_id") if running else None,
        "state": st,
    }


def list_models():
    from runtime.model.image_catalog import list_models as catalog_list
    running = engine_running()
    resident = read_state().get("model_id") if running else None
    models = []
    for entry in catalog_list():
        loaded = bool(running and resident == entry["id"])
        models.append({
            "id": entry["id"],
            "name": entry["name"],
            "installed": entry["installed"],
            "size_mb": entry["size_mb"],
            "license": entry["license"],
            "notes": entry["notes"],
            "source_url": entry["source_url"],
            "width": entry["width"],
            "height": entry["height"],
            "steps": entry["steps"],
            "status": "loaded" if loaded else (
                "installed" if entry["installed"] else "not_installed"),
        })
    return {"engine_running": running, "port": PORT if running else None,
            "models": models}


def _kill_pid(pid, timeout=5):
    try:
        os.kill(int(pid), signal.SIGTERM)
    except OSError:
        return
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _pid_alive(pid):
            return
        time.sleep(0.1)
    try:
        os.kill(int(pid), signal.SIGKILL)
    except OSError:
        pass


def _log_tail(n=40):
    try:
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except Exception:
        return ""


def stop_engine():
    with _lock:
        st = read_state()
        pid = st.get("pid")
        killed = False
        if _pid_alive(pid):
            _kill_pid(int(pid))
            killed = True
        time.sleep(0.3)
        _write_state({"running": False, "pid": None, "port": PORT,
                      "model_id": None, "job_id": None, "stopped": _now()})
        return {"stopped": True, "killed": killed}


def _spawn(model_path):
    engine = find_engine()
    if engine is None:
        raise ValueError("sd-server not installed; run bin/install-image-engine.sh")
    if not engine.is_file():
        raise ValueError("sd-server missing at %s" % engine)
    RESULTS.mkdir(parents=True, exist_ok=True)
    argv = [
        str(engine),
        "--listen-ip", HOST,
        "--listen-port", str(PORT),
        "--model-dir", str(model_path.parent),
        "-m", str(model_path),
    ]
    try:
        logf = open(str(LOG_FILE), "ab", buffering=0)
    except Exception as e:
        raise ValueError("Cannot open image router log: %s" % e)
    try:
        logf.write(("\n=== start %s ===\n" % _now()).encode())
        proc = subprocess.Popen(
            argv, stdin=subprocess.DEVNULL, stdout=logf,
            stderr=subprocess.STDOUT, start_new_session=True, cwd=str(ROOT))
    except Exception as e:
        raise ValueError("Failed to start sd-server: %s" % e)
    finally:
        try:
            logf.close()
        except Exception:
            pass

    deadline = time.time() + START_TIMEOUT
    while time.time() < deadline:
        if proc.poll() is not None:
            raise ValueError("sd-server exited early (code %s): %s" % (
                proc.returncode, _log_tail()[-400:]))
        try:
            status, payload = _http_get("/sdcpp/v1/models/status", timeout=1.5)
            if 200 <= status < 300 and payload.get("state") == "ready":
                return proc.pid
        except Exception:
            pass
        time.sleep(0.5)
    try:
        os.kill(proc.pid, signal.SIGKILL)
    except Exception:
        pass
    raise ValueError("sd-server did not load the model: %s" % _log_tail()[-400:])


def load_model(model_id):
    from runtime.model.image_catalog import get_model, model_path
    from runtime.model.runtime_config import available_ram_mb

    entry = get_model(model_id)  # allow-list gate
    final = model_path(model_id)
    if not final.is_file():
        raise ValueError("Image model not installed: %s" % entry["filename"])

    free = available_ram_mb()
    need = int(entry.get("min_ram_mb") or 0)
    if free is not None and need and free < need - 150:
        raise ValueError("Insufficient RAM: need %s MB free, have %s MB" % (
            need, free))

    with _lock:
        st = read_state()
        resident = st.get("model_id") if _pid_alive(st.get("pid")) else None
        if resident == model_id and engine_running():
            return {"model_id": model_id, "status": "already_loaded",
                    "pid": st.get("pid"), "port": PORT}
        if _pid_alive(st.get("pid")):
            _kill_pid(int(st["pid"]))
            time.sleep(0.4)
        _write_state({"running": False, "pid": None, "port": PORT,
                      "model_id": None, "job_id": None, "starting": _now()})
        pid = _spawn(final)
        _write_state({"running": True, "pid": pid, "port": PORT,
                      "model_id": model_id, "job_id": None,
                      "started": _now()})
        return {"model_id": model_id, "status": "loaded",
                "pid": pid, "port": PORT}


def unload_model(model_id=None):
    with _lock:
        st = read_state()
        resident = st.get("model_id")
        if model_id and resident and model_id != resident:
            return {"model_id": model_id, "status": "not_loaded",
                    "resident": resident, "engine_stopped": False}
        result = stop_engine()
        return {"model_id": model_id or resident, "status": "unloaded",
                "killed": result["killed"], "engine_stopped": True}


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    try:
        if cmd == "status":
            print(json.dumps(status_summary(), indent=2))
        elif cmd == "stop":
            print(json.dumps(stop_engine(), indent=2))
        elif cmd == "load" and len(sys.argv) > 2:
            print(json.dumps(load_model(sys.argv[2]), indent=2))
        elif cmd == "unload":
            print(json.dumps(unload_model(), indent=2))
        else:
            print("usage: python3 -m runtime.model.image_router "
                  "status|stop|load <id>|unload")
            sys.exit(1)
    except ValueError as e:
        print(json.dumps({"success": False, "error": str(e)}, indent=2))
        sys.exit(1)
