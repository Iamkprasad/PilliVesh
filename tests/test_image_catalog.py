"""Tests for the curated image-model allow-list."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.model import image_catalog


class ImageCatalogTests(unittest.TestCase):
    def test_get_model_unknown(self):
        with self.assertRaises(ValueError):
            image_catalog.get_model("not-a-model")

    def test_safe_url(self):
        good = image_catalog.CATALOG[0]["url"]
        self.assertTrue(image_catalog.is_safe_download_url(good))
        self.assertFalse(image_catalog.is_safe_download_url(
            "https://evil.example/model.gguf"))
        self.assertFalse(image_catalog.is_safe_download_url(
            "https://huggingface.co/x/y/resolve/main/model.safetensors"))

    def test_list_models_marks_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)
            (fake / image_catalog.CATALOG[0]["filename"]).write_bytes(b"x")
            with patch.object(image_catalog, "MODELS_DIR", fake):
                models = image_catalog.list_models()
            self.assertTrue(models[0]["installed"])
            self.assertFalse(models[1]["installed"])

    def test_first_entry_has_safe_defaults(self):
        entry = image_catalog.CATALOG[0]
        self.assertIn(entry["width"], image_catalog.ALLOWED_SIZES)
        self.assertIn(entry["height"], image_catalog.ALLOWED_SIZES)
        self.assertGreater(entry["min_ram_mb"], 0)


if __name__ == "__main__":
    unittest.main()
