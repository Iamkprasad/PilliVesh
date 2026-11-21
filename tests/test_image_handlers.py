"""Tests for the /image handlers."""
import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.server import handlers


PNG = b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes"


class ImageHandlerTests(unittest.TestCase):
    def test_stream_generation_emits_done_and_saves_png(self):
        fake = {"image_b64": base64.b64encode(PNG).decode(),
                "output_format": "png", "elapsed_ms": 1234}
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(handlers, "IMAGE_DIR", Path(tmp)), \
             patch("runtime.model.image_adapter.generate",
                   return_value=fake) as gen:
            events = list(handlers.stream_image_generation({
                "prompt": "a cat", "width": 256, "height": 256, "steps": 10}))
            gen.assert_called_once()
            kinds = [e["t"] for e in events]
            self.assertIn("done", kinds)
            done = [e for e in events if e["t"] == "done"][0]
            self.assertTrue((Path(tmp) / (done["id"] + ".png")).is_file())
            self.assertEqual(done["ms"], 1234)

    def test_stream_generation_error_event(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(handlers, "IMAGE_DIR", Path(tmp)), \
             patch("runtime.model.image_adapter.generate",
                   side_effect=ValueError("engine offline")):
            events = list(handlers.stream_image_generation({"prompt": "a cat"}))
        self.assertEqual(events[-1], {"t": "error", "e": "engine offline"})

    def test_get_image_file_rejects_bad_id(self):
        with self.assertRaises(ValueError):
            handlers.get_image_file("../etc/passwd")

    def test_search_sanitises_query_and_parses_results(self):
        payload = json.dumps([{
            "id": "owner/sd-gguf",
            "downloads": 10,
            "pipeline_tag": "text-to-image",
            "siblings": [{"rfilename": "sd-v1-5-Q8_0.gguf"}],
        }]).encode("utf-8")
        with patch.object(handlers.urllib.request, "urlopen",
                          return_value=io.BytesIO(payload)) as call:
            results = handlers.search_hf_models("sd 1.5<script>")
        url = call.call_args[0][0].full_url
        self.assertIn("search=sd%201.5script", url)
        self.assertEqual(results[0]["file"], "sd-v1-5-Q8_0.gguf")
        self.assertIn("owner/sd-gguf", results[0]["source_url"])

    def test_search_empty_query(self):
        with self.assertRaises(ValueError):
            handlers.search_hf_models("!!!")


if __name__ == "__main__":
    unittest.main()
