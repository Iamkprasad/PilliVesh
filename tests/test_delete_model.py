"""Delete-model handler: allow-list gate + resident guard (temp dirs only)."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import runtime.server.handlers as handlers


class DeleteModelTests(unittest.TestCase):
    def test_rejects_resident(self):
        with mock.patch("runtime.model.router.loaded_model_ids", return_value=["lfm3-1.7b-qad-q4_0"]):
            with self.assertRaises(ValueError):
                handlers.delete_model("lfm3-1.7b-qad-q4_0")

    def test_rejects_unknown(self):
        with self.assertRaises(ValueError):
            handlers.delete_model("nope-404")

    def test_deletes_file(self):
        with tempfile.TemporaryDirectory() as d:
            model_file = Path(d) / "LFM3-1.7B-QAD-Q4_0.gguf"
            model_file.write_bytes(b"x" * 1024)
            with mock.patch.object(handlers, "MODELS_DIR", Path(d)):
                with mock.patch("runtime.model.router.loaded_model_ids", return_value=[]):
                    r = handlers.delete_model("lfm3-1.7b-qad-q4_0")
            self.assertEqual(r["status"], "deleted")
            self.assertFalse(model_file.exists())

if __name__ == "__main__":
    unittest.main()
