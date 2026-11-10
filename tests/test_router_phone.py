"""Phone efficiency: catalog ctx cap + router spawn flags (no server start)."""
import unittest
from unittest import mock

from runtime.model import catalog, router


class PhoneTuningTests(unittest.TestCase):
    def test_catalog_context_capped_at_4096(self):
        for entry in catalog.list_models():
            self.assertLessEqual(entry.get("context", 0), 4096)

    def test_spawn_uses_phone_flags(self):
        seen = {}

        def fake_popen(argv, **kwargs):
            seen["argv"] = argv
            raise RuntimeError("stop after capture")

        with mock.patch("subprocess.Popen", side_effect=fake_popen):
            with self.assertRaises(ValueError):
                router._spawn("/tmp/model.gguf", ctx_size=4096)

        argv = seen["argv"]
        self.assertIn("--threads", argv)
        self.assertIn("--parallel", argv)
        self.assertIn("1", argv)
        self.assertIn("--batch-size", argv)
        self.assertIn("512", argv)
        self.assertIn("--ubatch-size", argv)
        self.assertIn("128", argv)
        self.assertIn("--cache-type-k", argv)
        self.assertIn("q8_0", argv)
        self.assertIn("--flash-attn", argv)

    def test_load_adaptive_ctx_low_ram_picks_2048(self):
        seen = {}
        with mock.patch("runtime.model.runtime_config.available_ram_mb", return_value=1500):
            with mock.patch("runtime.model.router._spawn", return_value=999) as spawn:
                with mock.patch("runtime.model.router._write_state"):
                    r = router.load_model("qwen2.5-0.5b-q4km")
        self.assertEqual(r["status"], "loaded")
        ctx_arg = spawn.call_args[1]["ctx_size"]
        self.assertEqual(ctx_arg, 2048)


if __name__ == "__main__":
    unittest.main()
