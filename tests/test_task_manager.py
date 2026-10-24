"""Tests for runtime.state.task_manager using a temporary SQLite database.

The real runtime/state/state.db and the real logs/runtime.jsonl are never
touched. log_event is intercepted via mock.patch.
"""

import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

from runtime.state import task_manager as tm

REQUIRED_COLUMNS = {
    "id", "project", "title", "status", "priority", "notes",
    "created_at", "updated_at", "result", "step_count",
}


def _capture_events():
    """Return (store, patcher) that captures log_event calls into store."""
    store = []
    patcher = mock.patch(
        "runtime.monitor.monitor.log_event",
        side_effect=lambda event, data: store.append((event, data)),
    )
    return store, patcher


class TaskManagerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="pv_task_test_")
        self.db = os.path.join(self.dir, "state.db")
        tm.DB = self.db  # type: ignore[assignment]
        # Every task operation logs; keep tests out of the real runtime log.
        self._log_patcher = mock.patch("runtime.monitor.monitor.log_event")
        self._log_patcher.start()
        self.addCleanup(self._log_patcher.stop)

    def tearDown(self):
        try:
            shutil.rmtree(self.dir)
        except Exception:
            pass

    def test_schema_has_required_columns(self):
        tm.init_schema()
        db = tm.connect()
        try:
            cols = {r[1] for r in db.execute("PRAGMA table_info(tasks)").fetchall()}
        finally:
            db.close()
        self.assertEqual(cols, REQUIRED_COLUMNS)

    def test_add_task_defaults_status_and_timestamps(self):
        tm.init_schema()
        store, patcher = _capture_events()
        with patcher:
            task_id = tm.add_task("proj", "Review logs", priority=3, notes="check")
        self.assertIsInstance(task_id, int)

        db = tm.connect()
        try:
            row = db.execute(
                "SELECT status, created_at, updated_at FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
        finally:
            db.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "active")
        self.assertIsNotNone(row[1])
        self.assertIsNotNone(row[2])

        self.assertIn(("task_created", {
            "id": task_id,
            "project": "proj",
            "status": "active",
            "priority": 3,
        }), store)

    def test_add_task_logs_via_monitor(self):
        tm.init_schema()
        store, patcher = _capture_events()
        with patcher:
            tm.add_task("proj", "Task Y")
        self.assertTrue(store)
        event, data = store[0]
        self.assertEqual(event, "task_created")
        self.assertEqual(data["status"], "active")
        # Task title must NOT be logged (privacy).
        self.assertNotIn("title", data)
        self.assertNotIn("Task Y", str(data))

    def test_active_tasks_returns_added_task(self):
        tm.init_schema()
        tm.add_task("alpha", "Task A")
        tm.add_task("alpha", "Task B")
        tm.add_task("beta", "Task C")

        rows = tm.active_tasks(project="alpha")
        titles = {r[1] for r in rows}
        self.assertEqual(titles, {"Task A", "Task B"})
        self.assertTrue(all(r[2] == "active" for r in rows))

    def test_set_status_updates_and_logs(self):
        tm.init_schema()
        store, patcher = _capture_events()
        with patcher:
            task_id = tm.add_task("proj", "Task X")
            tm.set_status(task_id, "completed")

        db = tm.connect()
        try:
            status = db.execute(
                "SELECT status FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()[0]
        finally:
            db.close()
        self.assertEqual(status, "completed")
        self.assertIn(("task_updated", {"id": task_id, "status": "completed"}), store)

    def test_repeated_operations_do_not_leak_connections(self):
        tm.init_schema()
        for i in range(50):
            tm.add_task("proj", f"Task {i}")
        db = tm.connect()
        try:
            count = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        finally:
            db.close()
        self.assertEqual(count, 50)


class GetTasksFreshInstallTests(unittest.TestCase):
    """Regression: GET /api/tasks must work when state.db does not yet exist."""

    def setUp(self):
        import runtime.server.handlers as handlers
        from pathlib import Path

        self.handlers = handlers
        self._orig_state_db = handlers.STATE_DB
        self._orig_tm_db = tm.DB
        self.tmp = tempfile.mkdtemp(prefix="pv_gettasks_test_")
        self.tmp_db = Path(self.tmp) / "state.db"
        # Ensure the temp DB does not exist (fresh install simulation).
        if self.tmp_db.exists():
            self.tmp_db.unlink()
        self.handlers.STATE_DB = self.tmp_db  # type: ignore[assignment]
        tm.DB = self.tmp_db  # type: ignore[assignment]
        self._log_patcher = mock.patch("runtime.monitor.monitor.log_event")
        self._log_patcher.start()
        self.addCleanup(self._log_patcher.stop)

    def tearDown(self):
        self.handlers.STATE_DB = self._orig_state_db  # type: ignore[assignment]
        tm.DB = self._orig_tm_db  # type: ignore[assignment]
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_get_tasks_fresh_install_returns_empty_shape(self):
        result = self.handlers.get_tasks()
        self.assertEqual(result, {
            "projects": [], "active": [], "recent": [],
            "counts": {"active": 0, "completed": 0, "failed": 0,
                       "cancelled": 0, "total": 0},
        })
        # The DB file and table should now exist (schema initialized).
        self.assertTrue(os.path.exists(self.tmp_db))
        db = sqlite3.connect(self.tmp_db)
        try:
            cols = {r[1] for r in db.execute("PRAGMA table_info(tasks)").fetchall()}
        finally:
            db.close()
        self.assertEqual(cols, REQUIRED_COLUMNS)

    def test_get_tasks_preserves_existing_data(self):
        tm.init_schema()
        task_id = tm.add_task("proj", "Existing task", priority=7, notes="keep me")
        result = self.handlers.get_tasks()
        self.assertEqual(len(result["active"]), 1)
        row = result["active"][0]
        self.assertEqual(row["id"], task_id)
        self.assertEqual(row["title"], "Existing task")
        self.assertEqual(row["priority"], 7)
        self.assertEqual(row["status"], "active")
        self.assertEqual(row["notes"], "keep me")
        self.assertEqual(row["step_count"], 0)
        self.assertEqual(result["counts"], {
            "active": 1, "completed": 0, "failed": 0,
            "cancelled": 0, "total": 1,
        })
        # recent should also include it.
        self.assertEqual(len(result["recent"]), 1)
        self.assertEqual(result["projects"], ["proj"])


if __name__ == "__main__":
    unittest.main()
