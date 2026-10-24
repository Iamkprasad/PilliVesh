"""Tests for the provider registry and wire adapters.

Uses a temporary config file; the real results/providers.json is untouched.
API keys must never appear in public state or normalized results.
"""
import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime.model import providers


class ProviderStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pv_provider_test_")
        self._results = providers.RESULTS
        self._config = providers.CONFIG_FILE
        providers.RESULTS = Path(self.tmp)
        providers.CONFIG_FILE = Path(self.tmp) / "providers.json"

    def tearDown(self):
        providers.RESULTS = self._results
        providers.CONFIG_FILE = self._config
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _save(self, **overrides):
        data = {
            "name": "Test Cloud",
            "type": "openai",
            "base_url": "https://api.example.com/v1",
            "model": "test-model",
            "api_key": "sk-super-secret-1234",
        }
        data.update(overrides)
        return providers.save_provider(data)

    def test_save_masks_key_and_writes_private_file(self):
        saved = self._save()
        self.assertTrue(saved["has_key"])
        self.assertTrue(saved["key_hint"].endswith("1234"))
        self.assertNotIn("api_key", saved)
        self.assertNotIn("sk-super-secret", json.dumps(saved))

        mode = stat.S_IMODE(os.stat(providers.CONFIG_FILE).st_mode)
        self.assertEqual(mode, 0o600)
        raw = providers.CONFIG_FILE.read_text(encoding="utf-8")
        self.assertIn("sk-super-secret-1234", raw)

        with mock.patch("runtime.model.router.router_running", return_value=False):
            state = providers.state()
        self.assertNotIn("sk-super-secret", json.dumps(state))
        self.assertEqual(state["providers"][1]["key_hint"], "••••1234")

    def test_edit_with_blank_key_keeps_existing(self):
        saved = self._save()
        providers.save_provider({
            "id": saved["id"], "name": "Renamed", "type": "openai",
            "base_url": "https://api.example.com/v1", "model": "new-model",
            "api_key": "",
        })
        config = providers._read_config()
        self.assertEqual(config["providers"][0]["api_key"], "sk-super-secret-1234")
        self.assertEqual(config["providers"][0]["name"], "Renamed")

    def test_active_provider_and_delete_fallback(self):
        saved = self._save()
        with mock.patch("runtime.model.router.router_running", return_value=False):
            providers.set_active(saved["id"])
            self.assertEqual(providers.resolve()["name"], "Test Cloud")
            result = providers.delete_provider(saved["id"])
        self.assertEqual(result["active"], "local")
        self.assertEqual(providers.resolve()["id"], "local")
        with self.assertRaises(ValueError):
            providers.delete_provider(saved["id"])

    def test_local_provider_cannot_be_deleted(self):
        with self.assertRaises(ValueError):
            providers.delete_provider("local")

    def test_validation_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            self._save(type="unknown")
        with self.assertRaises(ValueError):
            self._save(base_url="file:///etc/passwd")
        with self.assertRaises(ValueError):
            self._save(base_url="https://user:pass@example.com/v1")
        with self.assertRaises(ValueError):
            self._save(name="")
        with self.assertRaises(ValueError):
            self._save(model="")
        with self.assertRaises(ValueError):
            providers.resolve("nope")
        with self.assertRaises(ValueError):
            providers.test_provider("nope")

    def test_no_key_hint_when_empty(self):
        saved = self._save(api_key="")
        self.assertFalse(saved["has_key"])
        self.assertEqual(saved["key_hint"], "")


class ProviderSSEParserTests(unittest.TestCase):
    def test_openai_delta_and_done(self):
        self.assertEqual(
            providers._parse_openai_sse(
                '{"choices":[{"delta":{"content":"hi"}}]}'
            ),
            {"text": "hi"},
        )
        self.assertEqual(providers._parse_openai_sse("[DONE]"), {"done": True})
        self.assertIsNone(providers._parse_openai_sse('{"choices":[]}'))
        with self.assertRaises(ValueError):
            providers._parse_openai_sse('{"error":{"message":"bad"}}')

    def test_anthropic_delta_and_stop(self):
        self.assertEqual(
            providers._parse_anthropic_sse(
                '{"type":"content_block_delta","delta":{"text":"yo"}}'
            ),
            {"text": "yo"},
        )
        self.assertEqual(
            providers._parse_anthropic_sse('{"type":"message_stop"}'),
            {"done": True},
        )
        with self.assertRaises(ValueError):
            providers._parse_anthropic_sse(
                '{"type":"error","error":{"message":"nope"}}'
            )

    def test_google_chunks_skip_thought_parts(self):
        line = json.dumps({
            "candidates": [{"content": {"parts": [
                {"text": "thinking", "thought": True},
                {"text": "answer"},
            ]}}]
        })
        self.assertEqual(providers._parse_google_sse(line), {"text": "answer"})


class ProviderWireTests(unittest.TestCase):
    def _provider(self, ptype="openai"):
        return {
            "id": "p-test", "name": "Test Cloud", "type": ptype,
            "base_url": "https://api.example.com/v1", "model": "test-model",
            "api_key": "sk-secret-9999",
        }

    def _response(self, payload):
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps(payload).encode("utf-8")
        resp.__enter__ = mock.Mock(return_value=resp)
        resp.__exit__ = mock.Mock(return_value=False)
        return resp

    def test_openai_complete_normalizes_and_authorizes(self):
        payload = {
            "model": "test-model",
            "choices": [{"message": {"content": "hello"}}],
        }
        with mock.patch(
            "urllib.request.urlopen", return_value=self._response(payload)
        ) as urlopen:
            result = providers.complete(
                self._provider(), [{"role": "user", "content": "hi"}]
            )
        self.assertEqual(
            result["choices"][0]["message"]["content"], "hello"
        )
        request = urlopen.call_args[0][0]
        self.assertEqual(
            request.headers.get("Authorization"), "Bearer sk-secret-9999"
        )
        self.assertIn("/v1/chat/completions", request.full_url)
        self.assertNotIn("sk-secret-9999", json.dumps(result))

    def test_anthropic_splits_system_and_uses_header(self):
        payload = {"content": [{"type": "text", "text": "answer"}]}
        with mock.patch(
            "urllib.request.urlopen", return_value=self._response(payload)
        ) as urlopen:
            result = providers.complete(
                self._provider("anthropic"),
                [
                    {"role": "system", "content": "be terse"},
                    {"role": "user", "content": "hi"},
                ],
            )
        self.assertEqual(result["choices"][0]["message"]["content"], "answer")
        request = urlopen.call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["system"], "be terse")
        self.assertEqual(body["messages"], [{"role": "user", "content": "hi"}])
        self.assertEqual(request.headers.get("X-api-key"), "sk-secret-9999")
        self.assertEqual(request.headers.get("Anthropic-version"), "2023-06-01")

    def test_google_requires_key(self):
        provider = self._provider("google")
        provider["api_key"] = ""
        with self.assertRaises(ValueError):
            providers.complete(
                provider, [{"role": "user", "content": "hi"}]
            )

    def test_http_error_does_not_leak_key(self):
        import urllib.error

        def boom(*args, **kwargs):
            raise urllib.error.HTTPError(
                "https://api.example.com", 401, "Unauthorized", {},
                None,
            )

        with mock.patch("urllib.request.urlopen", side_effect=boom):
            with self.assertRaises(ValueError) as ctx:
                providers.complete(
                    self._provider(), [{"role": "user", "content": "hi"}]
                )
        self.assertIn("authentication failed", str(ctx.exception))
        self.assertNotIn("sk-secret-9999", str(ctx.exception))

    def test_scrub_removes_raw_and_url_encoded_key(self):
        provider = self._provider()
        provider["api_key"] = "sk/a+b"
        text = providers._scrub(
            provider, "raw sk/a+b and encoded sk%2Fa%2Bb"
        )
        self.assertNotIn("sk/a+b", text)
        self.assertNotIn("sk%2Fa%2Bb", text)


if __name__ == "__main__":
    unittest.main()
