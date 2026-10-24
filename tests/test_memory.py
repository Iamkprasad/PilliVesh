"""Memory database initialization and read-API tests.

Uses a temporary database; the real runtime/memory/memory.db is untouched.
"""

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from runtime.memory import memory_manager as mm
from runtime.server import handlers


class MemoryAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pv_mem_test_")
        self.db = Path(self.tmp) / "memory.db"
        self._orig_mm_db = mm.DB
        self._orig_handler_db = handlers.MEMORY_DB
        mm.DB = self.db
        handlers.MEMORY_DB = self.db

    def tearDown(self):
        mm.DB = self._orig_mm_db
        handlers.MEMORY_DB = self._orig_handler_db
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_fresh_install_initializes_empty_database(self):
        self.assertFalse(self.db.exists())
        result = handlers.get_memory()
        self.assertTrue(self.db.exists())
        self.assertEqual(result["items"], [])
        self.assertEqual(result["counts"], {
            "procedural": 0, "semantic": 0, "episodic": 0, "project": 0,
        })
        db = sqlite3.connect(self.db)
        try:
            cols = {r[1] for r in db.execute("PRAGMA table_info(memories)").fetchall()}
        finally:
            db.close()
        self.assertEqual(
            cols,
            {"id", "type", "content", "source", "importance", "created_at"},
        )

    def test_init_schema_is_idempotent_and_keeps_records(self):
        mm.remember("semantic", "first", source="test")
        mm.init_schema()
        mm.init_schema()
        result = handlers.get_memory()
        self.assertEqual(result["counts"]["semantic"], 1)
        self.assertEqual(result["items"][0]["content"], "first")

    def test_stored_records_are_returned(self):
        mm.remember("semantic", "The phone runs Android", source="test",
                    importance=0.9)
        mm.remember("project", "PilliVesh is local-first", source="test")
        result = handlers.get_memory()
        self.assertEqual(result["counts"]["semantic"], 1)
        self.assertEqual(result["counts"]["project"], 1)
        contents = {item["content"] for item in result["items"]}
        self.assertIn("The phone runs Android", contents)
        self.assertIn("PilliVesh is local-first", contents)

    def test_search_uses_runtime_ranking(self):
        mm.remember("semantic", "llama.cpp runs on the phone", source="test")
        mm.remember("semantic", "unrelated note about shopping", source="test")
        result = handlers.get_memory(query="llama phone")
        self.assertEqual(len(result["items"]), 1)
        self.assertIn("llama.cpp", result["items"][0]["content"])

    def test_unavailable_database_reports_actionable_error(self):
        blocker = Path(self.tmp) / "blocked"
        blocker.write_text("not a directory", encoding="utf-8")
        mm.DB = blocker / "memory.db"
        handlers.MEMORY_DB = mm.DB
        with self.assertRaises(ValueError) as caught:
            handlers.get_memory()
        self.assertIn("Memory database unavailable", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
