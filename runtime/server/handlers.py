"""Read-only data handlers for the Local AI Control Center.

Each function returns plain dicts/lists built from the existing
runtime files. No business logic is duplicated; modules are reused
where possible. All failures return structured errors to the caller.
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


def start_download(model_id):
    from runtime.model.downloader import download_async
    if not model_id or not isinstance(model_id, str):
        raise ValueError("Missing model id")
    return download_async(model_id.strip())


def load_model(model_id):
    from runtime.model import router as router_mod
    if not model_id or not isinstance(model_id, str):
        raise ValueError("Missing model id")
    return router_mod.load_model(model_id.strip())


def unload_model(model_id):
    from runtime.model import router as router_mod
    if not model_id or not isinstance(model_id, str):
        raise ValueError("Missing model id")
    return router_mod.unload_model(model_id.strip())


def stop_router():
    from runtime.model import router as router_mod
    return router_mod.stop_router()


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
