"""Tests for the sd-server API adapter."""
import unittest
from unittest.mock import patch

from runtime.model import image_adapter


def _job(status, **extra):
    job = {"id": "job_1", "status": status, "progress": {},
           "started": 1000, "completed": 2000}
    job.update(extra)
    return job


class ImageAdapterTests(unittest.TestCase):
    def test_build_request_validation(self):
        body = image_adapter.build_request({"prompt": "a cat", "steps": 8})
        self.assertEqual(body["sample_params"]["sample_steps"], 8)
        self.assertEqual(body["width"], 256)
        self.assertEqual(body["output_format"], "png")
        with self.assertRaises(ValueError):
            image_adapter.build_request({"prompt": ""})
        with self.assertRaises(ValueError):
            image_adapter.build_request({"prompt": "x", "width": 999})

    def test_generate_returns_first_image(self):
        done = _job("completed", result={"output_format": "png",
                    "images": [{"index": 0, "b64_json": "QUJD"}]})
        responses = [(202, {"id": "job_1"}),
                     (200, _job("generating", progress={
                         "stage": "sampling", "completed": 1, "total": 2})),
                     (200, done)]
        progress = []
        with patch.object(image_adapter, "_request", side_effect=responses), \
             patch.object(image_adapter.image_router, "set_job_id"), \
             patch.object(image_adapter.time, "sleep"):
            result = image_adapter.generate(
                {"prompt": "a cat"}, on_progress=progress.append)
        self.assertEqual(result["image_b64"], "QUJD")
        self.assertEqual(result["elapsed_ms"], 1000)
        self.assertEqual(progress[0]["stage"], "sampling")

    def test_generate_error(self):
        failed = _job("failed", error={"message": "boom"})
        with patch.object(image_adapter, "_request",
                          side_effect=[(202, {"id": "job_1"}), (200, failed)]), \
             patch.object(image_adapter.image_router, "set_job_id"), \
             patch.object(image_adapter.time, "sleep"):
            with self.assertRaises(ValueError):
                image_adapter.generate({"prompt": "a cat"})

    def test_cancel_uses_current_job(self):
        with patch.object(image_adapter.image_router, "current_job_id",
                          return_value="job_9"), \
             patch.object(image_adapter, "_request",
                          return_value=(200, {"cancel_requested": True})) as req:
            result = image_adapter.cancel()
        self.assertTrue(result["cancel_requested"])
        self.assertIn("job_9/cancel", req.call_args[0][1])


if __name__ == "__main__":
    unittest.main()
