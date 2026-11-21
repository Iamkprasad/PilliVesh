"""Tests for the lazy sd-server supervisor (mocked process/network)."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from runtime.model import image_catalog, image_router


class ImageRouterTests(unittest.TestCase):
    def test_load_model_builds_fixed_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            models = Path(tmp)
            (models / image_catalog.CATALOG[0]["filename"]).write_bytes(b"x")
            fake_engine = models / "sd-server"
            fake_engine.write_bytes(b"x")
            proc = MagicMock()
            proc.pid = 4242
            proc.poll.return_value = None
            state = {"running": False, "pid": None, "port": image_router.PORT,
                     "model_id": None, "job_id": None}
            with patch.object(image_catalog, "MODELS_DIR", models), \
                 patch("runtime.model.runtime_config.available_ram_mb",
                       return_value=8000), \
                 patch.object(image_router, "find_engine",
                              return_value=fake_engine), \
                 patch.object(image_router.subprocess, "Popen",
                              return_value=proc) as popen, \
                 patch.object(image_router, "_http_get",
                              return_value=(200, {"state": "ready"})), \
                 patch.object(image_router, "_write_state"), \
                 patch.object(image_router, "read_state", return_value=dict(state)), \
                 patch.object(image_router.time, "sleep"):
                result = image_router.load_model("sd15-q8")
            self.assertEqual(result["status"], "loaded")
            argv = popen.call_args[0][0]
            self.assertIn("--listen-port", argv)
            self.assertIn("8091", argv)
            self.assertIn("-m", argv)
            self.assertTrue(any(str(models) in str(a) for a in argv))

    def test_unknown_model_rejected(self):
        with self.assertRaises(ValueError):
            image_router.load_model("evil-id")

    def test_unload_does_not_deadlock(self):
        st = {"running": True, "pid": 4242, "port": image_router.PORT,
              "model_id": "sd15-q8", "job_id": None}
        with patch.object(image_router, "read_state", return_value=dict(st)), \
             patch.object(image_router, "_pid_alive", return_value=True), \
             patch.object(image_router, "_kill_pid"), \
             patch.object(image_router, "stop_engine",
                          return_value={"stopped": True, "killed": True}) as stop:
            result = image_router.unload_model("sd15-q8")
        stop.assert_called_once()
        self.assertEqual(result["status"], "unloaded")

    def test_job_id_roundtrip(self):
        st = {"running": True, "pid": 1, "port": image_router.PORT,
              "model_id": "sd15-q8", "job_id": None}
        with patch.object(image_router, "read_state", return_value=dict(st)), \
             patch.object(image_router, "_write_state") as write:
            image_router.set_job_id("job_123")
        self.assertEqual(write.call_args[0][0]["job_id"], "job_123")


if __name__ == "__main__":
    unittest.main()
