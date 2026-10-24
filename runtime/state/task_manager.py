import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "state.db"

# Seconds to wait for SQLite locks before failing.
SQLITE_TIMEOUT = 30

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    priority INTEGER NOT NULL DEFAULT 5,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    result TEXT,
    step_count INTEGER NOT NULL DEFAULT 0
)
"""


def _migrate(db):
    """Add missing columns for backward compatibility with older schemas."""
    cols = {r[1] for r in db.execute("PRAGMA table_info(tasks)").fetchall()}
    if "result" not in cols:
        db.execute("ALTER TABLE tasks ADD COLUMN result TEXT")
        db.commit()
    if "step_count" not in cols:
        db.execute("ALTER TABLE tasks ADD COLUMN step_count INTEGER NOT NULL DEFAULT 0")
        db.commit()


def init_schema(db=None):
    """Create the tasks table if missing. Idempotent and safe on existing DBs."""
    own = db is None
    if own:
        db = sqlite3.connect(DB, timeout=SQLITE_TIMEOUT)
    try:
        db.execute(SCHEMA)
        db.commit()
        _migrate(db)
    finally:
        if own:
            db.close()


def connect():
    db = sqlite3.connect(DB, timeout=SQLITE_TIMEOUT)
    db.execute(SCHEMA)
    db.commit()
    _migrate(db)
    return db


def _log_event(event, data):
    try:
        from runtime.monitor.monitor import log_event
        log_event(event, data)
    except Exception:
        pass


def add_task(project, title, priority=5, notes=""):
    db = connect()
    try:
        cur = db.execute(
            """
            INSERT INTO tasks (project, title, priority, notes)
            VALUES (?, ?, ?, ?)
            """,
            (project, title, priority, notes),
        )
        task_id = cur.lastrowid
        db.commit()
    finally:
        db.close()
    _log_event("task_created", {
        "id": task_id,
        "project": project,
        "status": "active",
        "priority": priority,
    })
    return task_id


def set_status(task_id, status):
    """Mark a task with a new status and log the state change."""
    db = connect()
    try:
        db.execute(
            "UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, task_id),
        )
        db.commit()
    finally:
        db.close()
    _log_event("task_updated", {
        "id": task_id,
        "status": status,
    })


def get_task(task_id):
    """Retrieve a single task by id, or None if not found."""
    db = connect()
    try:
        return db.execute(
            """
            SELECT id, project, title, status, priority, notes,
                   created_at, updated_at, result, step_count
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()
    finally:
        db.close()


def save_result(task_id, result):
    """Persist an execution result (as JSON) for a task."""
    import json
    db = connect()
    try:
        db.execute(
            "UPDATE tasks SET result = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (json.dumps(result), task_id),
        )
        db.commit()
    finally:
        db.close()


def save_step_count(task_id, count):
    """Persist the step count for a task."""
    db = connect()
    try:
        db.execute(
            "UPDATE tasks SET step_count = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (count, task_id),
        )
        db.commit()
    finally:
        db.close()


def active_tasks(project=None):
    db = connect()
    try:
        if project:
            return db.execute(
                """
                SELECT id, title, status, priority, notes
                FROM tasks
                WHERE project = ? AND status = 'active'
                ORDER BY priority DESC, updated_at DESC
                """,
                (project,),
            ).fetchall()

        return db.execute(
            """
            SELECT id, project, title, status, priority, notes
            FROM tasks
            WHERE status = 'active'
            ORDER BY priority DESC, updated_at DESC
            """
        ).fetchall()
    finally:
        db.close()


if __name__ == "__main__":
    print("Task manager ready.")
