"""Local API handlers for the Local AI Control Center.

Each function returns plain dicts/lists built from the existing
runtime files. No business logic is duplicated; modules are reused
where possible. Failures return structured errors to the caller.
Read endpoints are GET; chat/model ops are localhost POST only.
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
LOGS = ROOT / "logs"
MODELS_DIR = ROOT / "models"
MEMORY_DB = ROOT / "runtime" / "memory" / "memory.db"
STATE_DB = ROOT / "runtime" / "state" / "state.db"
SKILLS_DIR = ROOT / "runtime" / "skills"

# Ensure `import runtime.xxx` works when server is run as a script.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_json(path, default=None):
    try:
        if not path.exists():
            return default if default is not None else {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Cannot read {path.name}: {e}")


def get_telemetry():
    data = _load_json(RESULTS / "telemetry_latest.json", default=None)
    if not data:
        raise FileNotFoundError("Telemetry unavailable")
    # Attach compact history for inbuilt graphs (best-effort).
    history = []
    try:
        hist_path = RESULTS / "telemetry_history.jsonl"
        if hist_path.exists():
            lines = hist_path.read_text(encoding="utf-8").splitlines()
            for line in lines[-60:]:
                line = line.strip()
                if line:
                    history.append(json.loads(line))
    except Exception:
        history = []
    data = dict(data)
    data["history"] = history
    return data


def get_profile():
    return _load_json(RESULTS / "runtime_profile.json", default={})


def get_benchmark():
    data = _load_json(RESULTS / "benchmark_latest.json", default=None)
    if not data:
        raise FileNotFoundError("No benchmark yet")
    # Attach lightweight history for the chart (best-effort).
    hist_path = RESULTS / "benchmark_history.jsonl"
    history = []
    try:
        if hist_path.exists():
            lines = hist_path.read_text(encoding="utf-8").splitlines()
            for line in lines[-50:]:
                line = line.strip()
                if line:
                    history.append(json.loads(line))
    except Exception:
        history = []
    data = dict(data)
    data["history"] = history
    return data


def get_logs(limit=100, event_filter=None):
    path = LOGS / "runtime.jsonl"
    if not path.exists():
        raise FileNotFoundError("Log file unavailable")
    limit = max(1, min(int(limit or 100), 200))
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as e:
        raise ValueError(f"Cannot read logs: {e}")
    records = []
    for line in lines[-limit * 2:]:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        records.append(rec)
    # Newest first, then apply filter, then cut to limit.
    records.reverse()
    if event_filter and event_filter.lower() != "all":
        f = event_filter.lower()
        def _match(r):
            ev = str(r.get("event", "")).lower()
            # Map UI filter buckets to raw event names.
            if f == "info":
                return ev in ("health_check", "healthcheck", "info", "memory")
            if f == "warning":
                return "warn" in ev
            if f == "error":
                return "error" in ev or "fail" in ev
            if f == "tool":
                return "tool" in ev
            if f == "model":
                return "model" in ev or "benchmark" in ev
            if f == "system":
                return ev in ("health_check", "system", "telemetry")
            return f in ev
        records = [r for r in records if _match(r)]
    return {"count": len(records), "records": records[:limit]}


def get_memory(limit=20, query=None):
    if not MEMORY_DB.exists():
        raise FileNotFoundError("Memory database unavailable")
    try:
        db = sqlite3.connect(f"file:{MEMORY_DB}?mode=ro", uri=True)
    except Exception as e:
        raise ValueError(f"Memory database unavailable: {e}")
    try:
        counts = dict(db.execute(
            "SELECT type, COUNT(*) FROM memories GROUP BY type"
        ).fetchall())
        if query:
            # Reuse the real search ranking from the runtime.
            from runtime.memory.memory_manager import search as mem_search
            scored = mem_search(query, limit=int(limit or 20))
            items = [
                {
                    "score": score,
                    "id": row[0],
                    "type": row[1],
                    "content": row[2],
                    "source": row[3] if len(row) > 3 else None,
                    "importance": row[4] if len(row) > 4 else None,
                    "created_at": row[5] if len(row) > 5 else None,
                }
                for score, row in scored
            ]
        else:
            rows = db.execute(
                """SELECT id, type, content, source, importance, created_at
                   FROM memories ORDER BY created_at DESC LIMIT ?""",
                (int(limit or 20),),
            ).fetchall()
            items = [
                {
                    "id": r[0], "type": r[1], "content": r[2],
                    "source": r[3], "importance": r[4], "created_at": r[5],
                }
                for r in rows
            ]
    finally:
        db.close()
    for key in ("procedural", "semantic", "episodic", "project"):
        counts.setdefault(key, 0)
    return {"counts": counts, "items": items, "query": query or ""}


def get_skills(name=None):
    try:
        from runtime.skills.skill_loader import list_skills, load_skill
        names = list_skills()
    except Exception as e:
        raise ValueError(f"Skills unavailable: {e}")
    if name:
        if name not in names:
            raise ValueError(f"Skill not found: {name}")
        from runtime.skills.skill_loader import load_skill
        return {"name": name, "content": load_skill(name)}
    # Light list with first heading as title; content loaded on demand.
    skills = []
    for n in names:
        title = n.replace("_", " ").title()
        try:
            text = (SKILLS_DIR / n / "SKILL.md").read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip() or title
                    break
        except Exception:
            pass
        skills.append({"name": n, "title": title})
    return {"skills": skills}


def get_tools():
    try:
        from runtime.tools.default_tools import create_registry
        return {"tools": create_registry().list_tools()}
    except Exception as e:
        raise ValueError(f"Tools unavailable: {e}")


def get_tasks():
    if not STATE_DB.exists():
        raise FileNotFoundError("Task database unavailable")
    try:
        db = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True)
    except Exception as e:
        raise ValueError(f"Task database unavailable: {e}")
    try:
        cols = [r[1] for r in db.execute("PRAGMA table_info(tasks)").fetchall()]
        active, recent = [], []
        if "status" in cols:
            active = db.execute(
                """SELECT id, project, title, status, priority, notes,
                          created_at, updated_at FROM tasks
                   WHERE status='active' ORDER BY priority DESC, updated_at DESC"""
            ).fetchall()
        recent = db.execute(
            """SELECT id, project, title, status, priority, notes,
                      created_at, updated_at FROM tasks
               ORDER BY updated_at DESC LIMIT 20"""
        ).fetchall()
        projects = [r[0] for r in db.execute(
            "SELECT DISTINCT project FROM tasks ORDER BY project").fetchall()]
    finally:
        db.close()
    def _row(r):
        return {
            "id": r[0], "project": r[1], "title": r[2], "status": r[3],
            "priority": r[4], "notes": r[5], "created_at": r[6],
            "updated_at": r[7],
        }
    return {
        "projects": projects,
        "active": [_row(r) for r in active],
        "recent": [_row(r) for r in recent],
    }


def get_models():
    from runtime.model.catalog import list_models
    from runtime.model.downloader import installed, status
    from runtime.model import router as router_mod
    catalog = list_models()
    have = {m["name"] for m in installed()}
    # Live router status (best-effort; never fails the whole endpoint).
    router_running = False
    loaded_ids = []
    router_models = []
    try:
        info = router_mod.list_models()
        router_running = bool(info.get("router_running"))
        router_models = info.get("models", [])
        loaded_ids = router_mod.loaded_model_ids()
    except Exception:
        pass
    by_stem = {}
    from pathlib import Path as _P
    for entry in catalog:
        by_stem[_P(entry["filename"]).stem] = entry["id"]
    live_by_id = {}
    for m in router_models:
        cid = by_stem.get(str(m.get("id")))
        if cid:
            live_by_id[cid] = m
    for entry in catalog:
        entry["installed"] = entry["filename"] in have
        live = live_by_id.get(entry["id"])
        entry["loaded"] = entry["id"] in loaded_ids
        entry["router_status"] = (live or {}).get("status")
    return {"catalog": catalog, "installed": installed(),
            "download": status(), "router_running": router_running,
            "loaded_ids": loaded_ids}


def get_models():
    from runtime.model.catalog import list_models
    from runtime.model.downloader import installed, status
    from runtime.model import router as router_mod
    catalog = list_models()
    have = {m["name"] for m in installed()}
    # Live router status (best-effort; never fails the whole endpoint).
    router_running = False
    loaded_ids = []
    router_models = []
    try:
        info = router_mod.list_models()
        router_running = bool(info.get("router_running"))
        router_models = info.get("models", [])
        loaded_ids = router_mod.loaded_model_ids()
    except Exception:
        pass
    by_stem = {}
    from pathlib import Path as _P
    for entry in catalog:
        by_stem[_P(entry["filename"]).stem] = entry["id"]
    live_by_id = {}
    for m in router_models:
        cid = by_stem.get(str(m.get("id")))
        if cid:
            live_by_id[cid] = m
    for entry in catalog:
        entry["installed"] = entry["filename"] in have
        live = live_by_id.get(entry["id"])
        entry["loaded"] = entry["id"] in loaded_ids
        entry["router_status"] = (live or {}).get("status")
        # Per-model efficiency summary (best-effort).
        try:
            from benchmarks.probe import summarize
            entry["stats"] = summarize(entry["id"])
        except Exception:
            entry["stats"] = None
    return {"catalog": catalog, "installed": installed(),
            "download": status(), "router_running": router_running,
            "loaded_ids": loaded_ids}


def get_model_stats(model_id=None):
    """Full per-model stats for one id, or all catalog models."""
    from runtime.model.catalog import list_models
    from benchmarks.probe import summarize
    if model_id:
        return {"model_id": model_id, "stats": summarize(model_id)}
    out = {}
    for entry in list_models():
        out[entry["id"]] = summarize(entry["id"])
    return {"models": out}


def run_benchmark(model_id=None):
    """Run one light probe against the resident model (optionally check id)."""
    from runtime.model import router as router_mod
    from benchmarks.probe import run_probe

    if model_id:
        resident = router_mod.current_model_id()
        if resident and model_id != resident:
            raise ValueError(
                f"Model {model_id} is not resident (loaded: {resident})"
            )
        if not resident and not router_mod.router_running():
            raise ValueError(
                "No model loaded. Press Load first, then benchmark."
            )
    return run_probe()


def start_download(model_id):
    from runtime.model.downloader import download_async
    if not model_id or not isinstance(model_id, str):
        raise ValueError("Missing model id")
    return download_async(model_id.strip())


def load_model(model_id):
    from runtime.model import router as router_mod
    if not model_id or not isinstance(model_id, str):
        raise ValueError("Missing model id")
    result = router_mod.load_model(model_id.strip())
    # Log load for the Logs view (model filter).
    try:
        from runtime.monitor.monitor import log_event
        log_event("model_load", {
            "model": model_id.strip(),
            "status": result.get("status"),
            "pid": result.get("pid"),
            "message": f"Model {model_id} loaded",
        })
    except Exception:
        pass
    # Kick a probe so the Home benchmark panel updates immediately.
    try:
        from threading import Thread
        Thread(target=_safe_probe, daemon=True).start()
    except Exception:
        pass
    return result


def _safe_probe():
    try:
        from benchmarks.probe import run_probe
        run_probe()
    except Exception:
        pass


def unload_model(model_id):
    from runtime.model import router as router_mod
    if not model_id or not isinstance(model_id, str):
        raise ValueError("Missing model id")
    result = router_mod.unload_model(model_id.strip())
    try:
        from runtime.monitor.monitor import log_event
        log_event("model_unload", {
            "model": model_id.strip(),
            "status": result.get("status"),
            "message": f"Model {model_id} unloaded",
        })
    except Exception:
        pass
    return result


def stop_router():
    from runtime.model import router as router_mod
    return router_mod.stop_router()


def _coerce_int(value, default, lo, hi):
    if value is None:
        value = default
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = int(default)
    return max(lo, min(n, hi))


def _coerce_float(value, default, lo, hi):
    if value is None:
        value = default
    try:
        n = float(value)
    except (TypeError, ValueError):
        n = float(default)
    return max(lo, min(n, hi))


def _clean_messages(messages):
    if not isinstance(messages, list) or not messages:
        raise ValueError("Missing messages")
    if len(messages) > 100:
        raise ValueError("Too many messages (max 100)")
    cleaned = []
    allowed = ("system", "user", "assistant")
    for i, m in enumerate(messages):
        if not isinstance(m, dict):
            raise ValueError(f"messages[{i}] must be an object")
        role = m.get("role")
        content = m.get("content")
        if role not in allowed:
            raise ValueError(f"messages[{i}].role must be system|user|assistant")
        if not isinstance(content, str):
            raise ValueError(f"messages[{i}].content must be a string")
        if len(content) > 32 * 1024:
            raise ValueError(f"messages[{i}].content too long (max 32KB)")
        cleaned.append({"role": role, "content": content})
    return cleaned


def _model_reachable(router_mod):
    if router_mod.router_running():
        return True
    # State file can be stale if llama-server was started outside the router.
    try:
        return bool(router_mod._http_health())
    except Exception:
        return False


def chat(messages, model=None, max_tokens=512, temperature=0.7):
    """Proxy a chat completion to the resident llama-server on 8081."""
    import urllib.error
    import urllib.request
    from runtime.model import router as router_mod

    if not _model_reachable(router_mod):
        raise ValueError(
            "No model loaded. Go to More → Models and press Load first."
        )
    cleaned = _clean_messages(messages)
    payload = {
        "model": model or "local",
        "messages": cleaned,
        "max_tokens": _coerce_int(max_tokens, 512, 1, 2048),
        "temperature": _coerce_float(temperature, 0.7, 0.0, 2.0),
        "stream": False,
    }
    req = urllib.request.Request(
        f"http://{router_mod.ROUTER_HOST}:{router_mod.ROUTER_PORT}"
        f"/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "User-Agent": "PilliVesh/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise ValueError(f"Model error ({e.code}): {detail}")
    except Exception as e:
        raise ValueError(f"Chat request failed: {e}")


def chat_stream_raw(messages, model=None, max_tokens=512, temperature=0.7):
    """Open a streaming chat against llama-server. Returns the urllib response.

    Caller must read SSE lines (`data: {...}` / `data: [DONE]`) and close.
    Raises ValueError when no model is loaded or the request fails to start.
    """
    import urllib.error
    import urllib.request
    from runtime.model import router as router_mod

    if not _model_reachable(router_mod):
        raise ValueError(
            "No model loaded. Go to More → Models and press Load first."
        )
    cleaned = _clean_messages(messages)
    payload = {
        "model": model or "local",
        "messages": cleaned,
        "max_tokens": _coerce_int(max_tokens, 512, 1, 2048),
        "temperature": _coerce_float(temperature, 0.7, 0.0, 2.0),
        "stream": True,
    }
    req = urllib.request.Request(
        f"http://{router_mod.ROUTER_HOST}:{router_mod.ROUTER_PORT}"
        f"/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "User-Agent": "PilliVesh/1.0"},
        method="POST",
    )
    try:
        return urllib.request.urlopen(req, timeout=180)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise ValueError(f"Model error ({e.code}): {detail}")
    except Exception as e:
        raise ValueError(f"Chat stream failed: {e}")


def free_ram():
    """Best-effort RAM cleanup (fixed steps in resource_cleaner — no shell input)."""
    from runtime.monitor.resource_cleaner import free_ram as _free
    return _free()


def get_diagnostics():
    import platform
    profile = get_profile()
    try:
        from runtime.model.downloader import installed as _installed
        models = _installed()
    except Exception:
        models = []
    files = {}
    for rel in ("results/telemetry_latest.json", "results/benchmark_latest.json",
                "results/runtime_profile.json", "logs/runtime.jsonl",
                "runtime/memory/memory.db", "runtime/state/state.db"):
        files[rel] = (ROOT / rel).exists()
    return {
        "python": platform.python_version(),
        "profile": profile,
        "models": models,
        "model_downloaded": bool(profile.get("model_downloaded")) or len(models) > 0,
        "files": files,
    }
