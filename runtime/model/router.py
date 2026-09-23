"""Lazy single-model llama-server supervisor (stdlib only).

Battery-friendly: llama-server is spawned only on explicit Load, and killed
on Unload (or when swapping models). While unloaded there is zero background
inference drain.

Why not llama-router? Upstream disables LLAMA_SUBPROCESS on Android/iOS, so
this Termux build cannot spawn child model instances ("subprocess is not
enabled on this build"). We manage one classic single-model server instead.

Rules:
- Binds 127.0.0.1 only, fixed internal port (default 8081).
- At most one resident model (optimum phone resources); Load swaps cleanly.
- No shell; argv is a fixed list built from catalog paths only.
- State lives in results/router_state.json.
- Failures raise ValueError with the real llama-server message.
"""
import json
import os
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "models"
RESULTS = ROOT / "results"
STATE_FILE = RESULTS / "router_state.json"
LOG_FILE = RESULTS / "router.log"

ROUTER_HOST = "127.0.0.1"
ROUTER_PORT = 8081
START_TIMEOUT = 30.0
HTTP_TIMEOUT = 8.0

_lock = threading.Lock()


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
    return {"running": False, "pid": None, "port": ROUTER_PORT,
            "model_id": None}


def _pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def _http_health(timeout=1.5):
    url = f"http://{ROUTER_HOST}:{ROUTER_PORT}/health"
    req = urllib.request.Request(url, headers={"User-Agent": "PilliVesh/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return 200 <= resp.status < 300


def router_running():
    st = read_state()
    if not st.get("running") or not _pid_alive(st.get("pid")):
        return False
    try:
        return _http_health()
    except Exception:
        return False


def current_model_id():
    """Catalog id of the resident model, or None."""
    if not router_running():
        return None
    return read_state().get("model_id")


def list_models():
    """Per-catalog resident status. Router down -> nothing loaded."""
    from runtime.model.catalog import list_models as catalog_list
    running = router_running()
    resident = read_state().get("model_id") if running else None
    models = []
    for entry in catalog_list():
        loaded = bool(running and resident == entry["id"])
        models.append({
            "id": entry["id"],
            "filename": entry["filename"],
            "loaded": loaded,
            "loading": False,
            "status": "loaded" if loaded else "unloaded",
        })
    return {"router_running": running, "port": ROUTER_PORT if running else None,
            "models": models}


def loaded_model_ids():
    cur = current_model_id()
    return [cur] if cur else []


def _log_tail(path, n=40):
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except Exception:
        return ""


def _kill_pid(pid, timeout=5):
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _pid_alive(pid):
            return
        time.sleep(0.1)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def _pkill_llama_servers(exclude_pid=None):
    """Best-effort kill of llama-server processes (not ourselves).

    Uses `pgrep -x` (exact process name) so we never kill shells/tools
    whose command line merely *contains* the string "llama-server".
    """
    killed = 0
    try:
        r = subprocess.run(
            ["pgrep", "-x", "llama-server"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if not line.isdigit():
                continue
            p = int(line)
            if p in (os.getpid(), exclude_pid):
                continue
            try:
                os.kill(p, signal.SIGKILL)
                killed += 1
            except OSError:
                pass
    except Exception:
        pass
    return killed


def stop_router():
    """Kill llama-server (and any children). Safe when not running."""
    with _lock:
        st = read_state()
        pid = st.get("pid")
        killed = False
        if _pid_alive(pid):
            _kill_pid(int(pid))
            killed = True
        extra = _pkill_llama_servers()
        if extra:
            killed = True
        # Give the port a moment to free.
        time.sleep(0.3)
        _write_state({"running": False, "pid": None, "port": ROUTER_PORT,
                      "model_id": None, "stopped": _now()})
        return {"stopped": True, "killed": killed}


def _spawn(model_path, ctx_size=4096):
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    # -dev none / --no-op-offload: this Termux Vulkan build segfaults while
    # loading GGUFs; pure-CPU path is stable on this device.
    argv = [
        "llama-server",
        "-m", str(model_path),
        "--host", ROUTER_HOST,
        "--port", str(ROUTER_PORT),
        "--ctx-size", str(ctx_size),
        "-dev", "none",
        "--no-op-offload",
    ]
    try:
        logf = open(LOG_FILE, "ab", buffering=0)
    except Exception as e:
        raise ValueError(f"Cannot open router log: {e}")
    try:
        # Truncate-ish marker so each start is findable.
        logf.write(f"\n=== start {_now()} ===\n".encode())
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=logf,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=str(ROOT),
        )
    except FileNotFoundError:
        raise ValueError("llama-server not found on PATH")
    except Exception as e:
        raise ValueError(f"Failed to start llama-server: {e}")
    finally:
        try:
            logf.close()
        except Exception:
            pass
    deadline = time.time() + START_TIMEOUT
    while time.time() < deadline:
        if proc.poll() is not None:
            tail = _log_tail(LOG_FILE)
            _write_state({"running": False, "pid": None, "port": ROUTER_PORT,
                          "model_id": None, "error": "exited",
                          "log_tail": tail})
            raise ValueError(
                f"llama-server exited early (code {proc.returncode}): "
                f"{tail[-400:]}"
            )
        try:
            if _http_health():
                return proc.pid
        except Exception:
            pass
        time.sleep(0.25)
    try:
        os.kill(proc.pid, signal.SIGKILL)
    except Exception:
        pass
    tail = _log_tail(LOG_FILE)
    _write_state({"running": False, "pid": None, "port": ROUTER_PORT,
                  "model_id": None, "error": "start_timeout",
                  "log_tail": tail})
    raise ValueError(f"llama-server did not become ready: {tail[-400:]}")


def load_model(model_id, swap=True):
    """Load a catalog model (swaps out any currently loaded model)."""
    from runtime.model.catalog import get_model
    from runtime.model.runtime_config import available_ram_mb

    entry = get_model(model_id)  # allow-list gate
    final = MODELS_DIR / entry["filename"]
    if not final.exists():
        raise ValueError(f"Model file not installed: {entry['filename']}")

    free_mb = available_ram_mb()
    need = int(entry.get("min_ram_mb") or 0)
    if free_mb is not None and need and free_mb < need:
        raise ValueError(
            f"Insufficient RAM: need {need} MB free, have {free_mb} MB"
        )

    with _lock:
        st = read_state()
        resident = st.get("model_id") if _pid_alive(st.get("pid")) else None
        if resident == model_id and router_running():
            return {"model_id": model_id, "status": "already_loaded",
                    "pid": st.get("pid"), "port": ROUTER_PORT}
        if resident and resident != model_id:
            if not swap:
                raise ValueError(
                    f"Another model is loaded ({resident}); unload first"
                )
            # Swap: kill current first (frees RAM), then start target.
            old_pid = st.get("pid")
            if _pid_alive(old_pid):
                _kill_pid(int(old_pid))
            _pkill_llama_servers()
            time.sleep(0.4)
        elif st.get("pid") and _pid_alive(st.get("pid")):
            # Same-model stale process / unhealthy — restart it.
            _kill_pid(int(st["pid"]))
            time.sleep(0.3)

        ctx = int(entry.get("context") or 4096)
        # Cap context for phone RAM (llama-3.2 lists 131072 which is not
        # practical on this device).
        if ctx > 8192:
            ctx = 8192
        pid = _spawn(final, ctx_size=ctx)
        _write_state({"running": True, "pid": pid, "port": ROUTER_PORT,
                      "model_id": model_id, "started": _now()})
        return {"model_id": model_id, "status": "loaded",
                "pid": pid, "port": ROUTER_PORT}


def unload_model(model_id=None):
    """Unload the resident model (any id, or the known resident)."""
    with _lock:
        st = read_state()
        resident = st.get("model_id")
        if model_id and resident and model_id != resident:
            # Requested unload of a model that is not resident.
            return {"model_id": model_id, "status": "not_loaded",
                    "resident": resident, "router_stopped": False}
        pid = st.get("pid")
        killed = False
        if _pid_alive(pid):
            _kill_pid(int(pid))
            killed = True
        extra = _pkill_llama_servers()
        if extra:
            killed = True
        time.sleep(0.3)
        _write_state({"running": False, "pid": None, "port": ROUTER_PORT,
                      "model_id": None, "stopped": _now()})
        return {"model_id": model_id or resident, "status": "unloaded",
                "killed": killed, "router_stopped": True}


def status_summary():
    st = read_state()
    running = router_running()
    return {
        "router_running": running,
        "port": ROUTER_PORT if running else None,
        "pid": st.get("pid") if running else None,
        "loaded_id": st.get("model_id") if running else None,
        "state": st,
    }


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    try:
        if cmd == "status":
            print(json.dumps(status_summary(), indent=2))
        elif cmd == "stop":
            print(json.dumps(stop_router(), indent=2))
        elif cmd == "load" and len(sys.argv) > 2:
            print(json.dumps(load_model(sys.argv[2]), indent=2))
        elif cmd == "unload":
            mid = sys.argv[2] if len(sys.argv) > 2 else None
            print(json.dumps(unload_model(mid), indent=2))
        else:
            print("usage: python3 -m runtime.model.router "
                  "status|stop|load <id>|unload [id]")
            sys.exit(1)
    except ValueError as e:
        print(json.dumps({"success": False, "error": str(e)}, indent=2))
        sys.exit(1)
