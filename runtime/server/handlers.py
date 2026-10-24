"""Local API handlers for the PilliVesh chat harness.

Each function returns plain dicts/lists built from the existing
runtime files. No business logic is duplicated; modules are reused
where possible. Failures return structured errors to the caller.
Read endpoints are GET; chat/model ops are localhost POST only.
"""
import json
import sqlite3
import sys
import threading
import uuid
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


def get_logs(limit=100, event_filter=None, query=None, offset=0):
    path = LOGS / "runtime.jsonl"
    if not path.exists():
        raise FileNotFoundError("Log file unavailable")
    limit = max(1, min(int(limit or 100), 200))
    offset = max(0, int(offset or 0))
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as e:
        raise ValueError(f"Cannot read logs: {e}")
    records = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        records.append(rec)
    # Newest first, then apply filters, then page.
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
    if query:
        needle = str(query).lower()
        records = [
            r for r in records
            if needle in json.dumps(r, ensure_ascii=False).lower()
        ]
    total = len(records)
    return {
        "count": total,
        "records": records[offset:offset + limit],
        "offset": offset,
        "limit": limit,
        "query": query or "",
    }


def get_memory(limit=20, query=None):
    # Memory is created on first use; a fresh install is empty, not broken.
    try:
        from runtime.memory.memory_manager import init_schema
        init_schema()
    except Exception as e:
        raise ValueError(f"Memory database unavailable: {e}")
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
    except sqlite3.Error as e:
        raise ValueError(f"Memory database unavailable: {e}")
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


def create_task(project=None, title=None, priority=5, notes=""):
    """Create a new task with validation. Returns the task id."""
    # Validate project.
    if not isinstance(project, str) or not project.strip():
        raise ValueError("Missing or invalid project")
    project = project.strip()
    if len(project) > 100:
        raise ValueError("Project too long (max 100 chars)")
    # Validate title.
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Missing or invalid title")
    title = title.strip()
    if len(title) > 200:
        raise ValueError("Title too long (max 200 chars)")
    # Validate priority.
    try:
        priority = int(priority)
    except (TypeError, ValueError):
        raise ValueError("Priority must be an integer")
    if priority < 1 or priority > 10:
        raise ValueError("Priority must be between 1 and 10")
    # Validate notes.
    if not isinstance(notes, str):
        notes = str(notes) if notes is not None else ""
    if len(notes) > 500:
        raise ValueError("Notes too long (max 500 chars)")

    from runtime.state.task_manager import add_task
    task_id = add_task(project, title, priority=priority, notes=notes)
    return {"id": task_id, "project": project, "title": title,
            "priority": priority, "status": "active"}


def update_task_status(task_id=None, status=None):
    """Update a task's status with validation."""
    # Validate task_id.
    try:
        task_id = int(task_id)
    except (TypeError, ValueError):
        raise ValueError("Missing or invalid task id")
    if task_id < 1:
        raise ValueError("Invalid task id")
    # Validate status.
    allowed = ("active", "completed", "cancelled", "failed")
    if status not in allowed:
        raise ValueError(
            f"Invalid status: {status}. Allowed: {', '.join(allowed)}"
        )
    from runtime.state.task_manager import set_status
    set_status(task_id, status)
    return {"id": task_id, "status": status}


# In-memory set of task IDs currently being executed (concurrency guard).
_running_tasks = set()
_running_lock = threading.Lock()


def run_task(task_id=None):
    """Execute a task through the bounded tool loop.

    Uses the task title as the prompt and the existing system_info tool.
    Marks the task completed only on successful execution + validation.
    On failure, sets status to 'failed' (retryable).
    Prevents duplicate concurrent execution of the same task.
    """
    # Validate task_id.
    try:
        task_id = int(task_id)
    except (TypeError, ValueError):
        raise ValueError("Missing or invalid task id")
    if task_id < 1:
        raise ValueError("Invalid task id")

    # Get task from DB.
    from runtime.state.task_manager import get_task, set_status
    task = get_task(task_id)
    if not task:
        raise ValueError("Task not found")

    # task tuple: (id, project, title, status, priority, notes, created_at, updated_at, result)
    task_title = task[2]
    task_notes = task[5] if len(task) > 5 else ""
    if not task_title or not str(task_title).strip():
        raise ValueError("Task has no title")

    # Build prompt from title + notes (notes are task instructions, not sensitive content).
    prompt_parts = [str(task_title).strip()]
    notes_str = str(task_notes).strip() if task_notes else ""
    if notes_str:
        prompt_parts.append(f"Notes: {notes_str}")
    prompt = "\n".join(prompt_parts)

    # Prevent duplicate concurrent execution.
    with _running_lock:
        if task_id in _running_tasks:
            raise ValueError("Task already running")
        _running_tasks.add(task_id)

    try:
        set_status(task_id, "active")
        _log_event("task_started", {"id": task_id})

        result = chat(
            [{"role": "user", "content": prompt}],
            use_tools=True,
        )

        # Persist step count regardless of outcome.
        from runtime.state.task_manager import save_step_count
        save_step_count(task_id, result.get("steps", 0))

        # Validate result — must have a non-empty response.
        choices = result.get("choices") or []
        if not choices:
            raise ValueError("No response from model")
        content = (choices[0].get("message") or {}).get("content") or ""
        if not content.strip():
            raise ValueError("Empty response from model")

        # Check if execution hit the iteration limit (not a success).
        if result.get("max_iterations_reached"):
            raise ValueError("Max tool iterations reached without final answer")

        # Persist the execution result.
        from runtime.state.task_manager import save_result
        save_result(task_id, result)

        set_status(task_id, "completed")
        _log_event("task_completed", {"id": task_id})
        return {"id": task_id, "status": "completed", "result": result, "steps": result.get("steps", 0)}
    except Exception as e:
        set_status(task_id, "failed")
        _log_event("task_failed", {"id": task_id})
        raise
    finally:
        with _running_lock:
            _running_tasks.discard(task_id)


def get_task_result(task_id=None):
    """Retrieve a persisted task execution result."""
    try:
        task_id = int(task_id)
    except (TypeError, ValueError):
        raise ValueError("Missing or invalid task id")
    if task_id < 1:
        raise ValueError("Invalid task id")
    from runtime.state.task_manager import get_task
    task = get_task(task_id)
    if not task:
        raise ValueError("Task not found")
    result_json = task[8] if len(task) > 8 else None
    if not result_json:
        raise ValueError("No result available for this task")
    import json
    try:
        result = json.loads(result_json)
    except (json.JSONDecodeError, TypeError, ValueError):
        raise ValueError("Corrupted result data")
    return {"id": task_id, "result": result}


def get_tasks():
    # Ensure the tasks table exists (idempotent; creates empty DB on fresh install).
    try:
        from runtime.state.task_manager import init_schema
        init_schema()
    except Exception:
        pass
    empty_counts = {"active": 0, "completed": 0, "failed": 0,
                    "cancelled": 0, "total": 0}
    if not STATE_DB.exists():
        return {"projects": [], "active": [], "recent": [],
                "counts": empty_counts}
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
                          created_at, updated_at, step_count FROM tasks
                   WHERE status='active' ORDER BY priority DESC, updated_at DESC"""
            ).fetchall()
        recent = db.execute(
            """SELECT id, project, title, status, priority, notes,
                      created_at, updated_at, step_count FROM tasks
               ORDER BY updated_at DESC LIMIT 20"""
        ).fetchall()
        projects = [r[0] for r in db.execute(
            "SELECT DISTINCT project FROM tasks ORDER BY project").fetchall()]
        counts = dict(db.execute(
            "SELECT status, COUNT(*) FROM tasks GROUP BY status"
        ).fetchall())
    finally:
        db.close()
    counts = {k: int(counts.get(k, 0)) for k in
              ("active", "completed", "failed", "cancelled")}
    counts["total"] = sum(counts.values())
    def _row(r):
        return {
            "id": r[0], "project": r[1], "title": r[2], "status": r[3],
            "priority": r[4], "notes": r[5], "created_at": r[6],
            "updated_at": r[7], "step_count": r[8],
        }
    return {
        "projects": projects,
        "active": [_row(r) for r in active],
        "recent": [_row(r) for r in recent],
        "counts": counts,
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
        # Per-model efficiency summary (best-effort).
        try:
            from benchmarks.probe import summarize
            entry["stats"] = summarize(entry["id"])
        except Exception:
            entry["stats"] = None
    return {"catalog": catalog, "installed": installed(),
            "download": status(), "router_running": router_running,
            "loaded_ids": loaded_ids}


def get_providers():
    """Configured chat providers with keys masked (never exported)."""
    from runtime.model.providers import state
    return state()


def save_provider(data):
    from runtime.model.providers import save_provider as _save
    result = _save(data)
    _log_event("provider_saved", {
        "provider_type": result.get("type"),
        "has_key": result.get("has_key"),
    })
    return result


def delete_provider(provider_id):
    from runtime.model.providers import delete_provider as _delete
    result = _delete(provider_id)
    _log_event("provider_deleted", {"provider_id": result.get("deleted")})
    return result


def set_active_provider(provider_id):
    from runtime.model.providers import set_active
    return set_active(provider_id)


def test_provider(provider_id):
    from runtime.model.providers import test_provider as _test
    return _test(provider_id)


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
    allowed = ("system", "user", "assistant")
    system = []
    turns = []
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
        if role == "system":
            system.append(content)
        elif turns and turns[-1]["role"] == role:
            # Stale histories can contain two user turns in a row (a failed
            # reply is dropped by the client). Chat templates require
            # alternating roles, so merge instead of rejecting the chat.
            turns[-1]["content"] += "\n\n" + content
        else:
            turns.append({"role": role, "content": content})
    while turns and turns[0]["role"] != "user":
        turns.pop(0)
    if not turns:
        raise ValueError("Missing messages")
    if system:
        turns.insert(0, {"role": "system", "content": "\n\n".join(system)})
    return turns


def _model_reachable(router_mod):
    if router_mod.router_running():
        return True
    # State file can be stale if llama-server was started outside the router.
    try:
        return bool(router_mod._http_health())
    except Exception:
        return False


def _log_chat_request(messages, model, request_id=None, use_tools=False):
    """Log a chat request without message bodies, prompts, or personal data."""
    try:
        from runtime.monitor.monitor import log_event
        count = len(messages) if isinstance(messages, list) else 0
        log_event("chat_request", {
            "request_id": request_id,
            "messages": count,
            "model": model or "local",
            "use_tools": bool(use_tools),
        })
    except Exception:
        pass


def _log_chat_terminal(request_id, model, success, category=None):
    """Log a terminal chat outcome without message bodies or raw errors."""
    try:
        from runtime.monitor.monitor import log_event
        payload = {
            "request_id": request_id,
            "model": model or "local",
            "success": success,
        }
        if category:
            payload["category"] = category
        log_event("chat_success" if success else "chat_failure", payload)
    except Exception:
        pass


def _activity_status(event, data):
    """Derive a human-readable status from an event and its data.

    Mirrors the frontend logStatus() helper.  Returns a short label.
    """
    ev = str(event or "").lower()
    d = data if isinstance(data, dict) else {}
    if d.get("success") is True:
        return "Success"
    if d.get("success") is False:
        return "Failed"
    if "success" in ev:
        return "Success"
    if "fail" in ev or "not_found" in ev:
        return "Failed"
    if "created" in ev:
        return "Created"
    if "updated" in ev:
        return "Updated"
    if "unload" in ev:
        return "Unloaded"
    if "download" in ev:
        return "Downloaded"
    if "load" in ev:
        return "Loaded"
    if "check" in ev:
        return "OK"
    return "—"


def _log_event(event, data):
    """Log a runtime event without message bodies or personal data."""
    try:
        from runtime.monitor.monitor import log_event
        log_event(event, data)
    except Exception:
        pass


def _chat_remote(provider, messages, max_tokens, temperature, request_id, use_tools):
    """Completion against a configured remote provider (key stays here)."""
    from runtime.model import providers as provider_mod
    from runtime.model.tool_loop import parse_tool_request
    from runtime.model.tool_executor import ToolExecutor

    name = provider.get("name") or provider.get("id")
    model_label = provider.get("model") or name
    cleaned = _clean_messages(messages)
    _log_chat_request(messages, model_label, request_id, use_tools=use_tools)

    def _call(conversation):
        try:
            return provider_mod.complete(
                provider, conversation,
                max_tokens=max_tokens, temperature=temperature,
            )
        except ValueError as e:
            _log_chat_terminal(
                request_id, model_label, False, category="provider_error"
            )
            raise
        except Exception as e:
            _log_chat_terminal(
                request_id, model_label, False, category="request_failed"
            )
            raise ValueError(f"{name} request failed: {e}")

    if not use_tools:
        result = _call(cleaned)
        _log_chat_terminal(request_id, model_label, True)
        return result

    executor = ToolExecutor()
    max_tool_iterations = 2
    tool_used = None
    steps = 0

    for _ in range(max_tool_iterations + 1):
        result = _call(cleaned)
        choices = result.get("choices") or []
        text = ""
        if choices:
            text = (choices[0].get("message") or {}).get("content") or ""
        request = parse_tool_request(text)
        if not request:
            _log_chat_terminal(request_id, model_label, True)
            result["steps"] = steps
            if tool_used:
                result["tool_used"] = tool_used
            return result
        if steps >= max_tool_iterations:
            _log_chat_terminal(
                request_id, model_label, False, category="max_iterations"
            )
            result["steps"] = steps
            result["max_iterations_reached"] = True
            if tool_used:
                result["tool_used"] = tool_used
            return result

        steps += 1
        _log_event("tool_request", {"tool": request.tool, "step": steps})
        execution = executor.execute(text)
        if execution.get("success"):
            _log_event("tool_executed", {"tool": request.tool, "step": steps})
            output = execution.get("output", "")
            if not isinstance(output, str):
                output = json.dumps(output)
            tool_used = {"tool": request.tool, "executed": True}
        else:
            _log_event("tool_error", {
                "tool": request.tool,
                "step": steps,
                "error": execution.get("message", ""),
            })
            output = f"Tool error: {execution.get('message', '')}"
        cleaned.append({"role": "assistant", "content": text})
        cleaned.append({
            "role": "user",
            "content": f"Tool result for {request.tool}:\n{output}",
        })

    _log_chat_terminal(
        request_id, model_label, False, category="max_iterations"
    )
    result["steps"] = steps
    result["max_iterations_reached"] = True
    if tool_used:
        result["tool_used"] = tool_used
    return result


def chat(messages, model=None, max_tokens=512, temperature=0.7, request_id=None, use_tools=True, provider=None):
    """Proxy a chat completion to the selected provider.

    Local llama.cpp is the default for backwards compatibility. Remote
    providers are resolved from results/providers.json and their API key
    stays server-side. Native tool calling is unsupported by the local
    llama-server build, so tools use a bounded text-JSON loop instead.
    """
    import urllib.error
    import urllib.request
    from runtime.model import router as router_mod
    from runtime.model.providers import resolve as resolve_provider
    from runtime.model.tool_loop import parse_tool_request
    from runtime.model.tool_executor import ToolExecutor

    if request_id is None:
        request_id = uuid.uuid4().hex

    if provider and provider != "local":
        return _chat_remote(
            resolve_provider(provider), messages, max_tokens, temperature,
            request_id, use_tools,
        )

    _log_chat_request(messages, model, request_id, use_tools=use_tools)

    if not _model_reachable(router_mod):
        _log_chat_terminal(request_id, model, False, category="model_unreachable")
        raise ValueError(
            "No model loaded. Open Settings → Models and press Load first."
        )
    cleaned = _clean_messages(messages)

    # When tool use is disabled, do a single model call with no tool loop.
    if not use_tools:
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
                result = json.loads(resp.read().decode("utf-8"))
            _log_chat_terminal(request_id, model, True)
            return result
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:500]
            _log_chat_terminal(request_id, model, False, category="upstream_http_error")
            raise ValueError(f"Model error ({e.code}): {detail}")
        except Exception as e:
            _log_chat_terminal(request_id, model, False, category="request_failed")
            raise ValueError(f"Chat request failed: {e}")

    executor = ToolExecutor()

    # Bounded tool-use loop (text-based; native tool calling unsupported).
    MAX_TOOL_ITERATIONS = 2
    tool_used = None
    step_count = 0

    for _ in range(MAX_TOOL_ITERATIONS + 1):
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
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:500]
            _log_chat_terminal(request_id, model, False, category="upstream_http_error")
            raise ValueError(f"Model error ({e.code}): {detail}")
        except Exception as e:
            _log_chat_terminal(request_id, model, False, category="request_failed")
            raise ValueError(f"Chat request failed: {e}")

        # Extract response text from the chat completion.
        choices = result.get("choices") or []
        response_text = ""
        if choices:
            message = choices[0].get("message") or {}
            response_text = message.get("content") or ""

        # Check for a tool request in the model's text output.
        tool_request = parse_tool_request(response_text)
        if not tool_request:
            # No tool requested — this is the final response.
            _log_chat_terminal(request_id, model, True)
            result["steps"] = step_count
            if tool_used:
                result["tool_used"] = tool_used
            return result

        # Guard: don't execute more tools than the limit.
        if step_count >= MAX_TOOL_ITERATIONS:
            _log_chat_terminal(request_id, model, False, category="max_iterations")
            result["steps"] = step_count
            result["max_iterations_reached"] = True
            if tool_used:
                result["tool_used"] = tool_used
            return result

        # Tool requested — execute it read-only.
        step_count += 1
        _log_event("tool_request", {"tool": tool_request.tool, "step": step_count})

        exec_result = executor.execute(response_text)
        if exec_result.get("success"):
            _log_event("tool_executed", {"tool": tool_request.tool, "step": step_count})
            tool_content = exec_result.get("output", "")
            if not isinstance(tool_content, str):
                tool_content = json.dumps(tool_content)
            tool_used = {"tool": tool_request.tool, "executed": True}
        else:
            _log_event("tool_error", {
                "tool": tool_request.tool,
                "step": step_count,
                "error": exec_result.get("message", ""),
            })
            tool_content = f"Tool error: {exec_result.get('message', '')}"

        # Feed the request and result back as alternating turns; llama-server
        # chat templates reject the "tool" role.
        cleaned.append({"role": "assistant", "content": response_text})
        cleaned.append({
            "role": "user",
            "content": f"Tool result for {tool_request.tool}:\n{tool_content}",
        })

    # Max tool iterations reached — return the last result (not success).
    _log_chat_terminal(request_id, model, False, category="max_iterations")
    result["steps"] = step_count
    result["max_iterations_reached"] = True
    if tool_used:
        result["tool_used"] = tool_used
    return result


def chat_stream_raw(messages, model=None, max_tokens=512, temperature=0.7, request_id=None):
    """Open a streaming chat against llama-server. Returns the urllib response.

    Caller must read SSE lines (`data: {...}` / `data: [DONE]`) and close.
    Raises ValueError when no model is loaded or the request fails to start.
    """
    import urllib.error
    import urllib.request
    from runtime.model import router as router_mod

    if request_id is None:
        request_id = uuid.uuid4().hex

    _log_chat_request(messages, model, request_id)

    if not _model_reachable(router_mod):
        _log_chat_terminal(request_id, model, False, category="model_unreachable")
        raise ValueError(
            "No model loaded. Open Settings → Models and press Load first."
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
        upstream = urllib.request.urlopen(req, timeout=180)
    except urllib.error.HTTPError as e:
        _log_chat_terminal(request_id, model, False, category="upstream_http_error")
        raise ValueError(f"Model error ({e.code})")
    except Exception as e:
        _log_chat_terminal(request_id, model, False, category="request_failed")
        raise ValueError(f"Chat stream failed: {e}")
    return upstream, request_id


def _iter_local_stream(upstream):
    """Yield text deltas from llama-server's OpenAI-style SSE stream."""
    try:
        for raw in upstream:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                return
            try:
                obj = json.loads(data)
            except ValueError:
                continue
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            content = delta.get("content")
            if content:
                yield content
    finally:
        try:
            upstream.close()
        except Exception:
            pass


def stream_chat(messages, model=None, max_tokens=512, temperature=0.7, request_id=None, provider=None):
    """Open a token stream against local or remote provider.

    Returns (request_id, provider_config, text_deltas_iterator). The
    caller is responsible for logging the terminal event once the stream
    finishes or fails.
    """
    from runtime.model import providers as provider_mod

    if request_id is None:
        request_id = uuid.uuid4().hex

    if provider and provider != "local":
        config = provider_mod.resolve(provider)
        label = config.get("model") or config.get("name")
        _log_chat_request(
            messages, label, request_id, use_tools=False
        )
        cleaned = _clean_messages(messages)
        deltas = provider_mod.stream(
            config, cleaned,
            max_tokens=max_tokens, temperature=temperature,
        )
        return request_id, config, deltas

    upstream, request_id = chat_stream_raw(
        messages=messages, model=model, max_tokens=max_tokens,
        temperature=temperature, request_id=request_id,
    )
    return request_id, {"id": "local", "name": "Local llama.cpp",
                        "type": "local", "model": model or "local"}, \
        _iter_local_stream(upstream)


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
