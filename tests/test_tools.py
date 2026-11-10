"""Tests for the bounded file and web tools.

Tests use real files inside the project root (README.md) and verify that
path traversal and absolute paths are rejected. Web fetch is mocked so no
network is required.
"""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from runtime.tools.file_ops import file_read, list_dir
from runtime.tools.web_fetch import fetch_url
from runtime.model.tool_executor import ToolExecutor


class FileOpsTests(unittest.TestCase):
    def test_file_read_returns_content(self):
        content, err = file_read("README.md")
        self.assertIsNone(err)
        self.assertIn("PilliVesh", content)

    def test_file_read_blocks_path_traversal(self):
        content, err = file_read("../../../etc/passwd")
        self.assertIsNotNone(err)
        self.assertEqual(content, "")

    def test_file_read_nonexistent(self):
        content, err = file_read("does_not_exist_xyz.txt")
        self.assertIsNotNone(err)
        self.assertEqual(content, "")

    def test_list_dir_returns_entries(self):
        entries, err = list_dir("runtime")
        self.assertIsNone(err)
        names = [e["name"] for e in entries]
        self.assertIn("tools", names)
        self.assertIn("memory", names)

    def test_list_dir_blocks_absolute_path(self):
        entries, err = list_dir("/tmp")
        self.assertIsNotNone(err)
        self.assertEqual(entries, [])


class WebFetchTests(unittest.TestCase):
    def test_fetch_url_rejects_bad_scheme(self):
        text, err = fetch_url("ftp://example.com")
        self.assertIsNotNone(err)
        self.assertEqual(text, "")

    def test_fetch_url_rejects_empty_url(self):
        text, err = fetch_url("")
        self.assertIsNotNone(err)
        self.assertEqual(text, "")

    @mock.patch("runtime.tools.web_fetch.urllib.request.urlopen")
    def test_fetch_url_returns_text(self, mock_urlopen):
        class MockResp:
            def __init__(self):
                self.code = 200
                self.headers = {"Content-Type": "text/html; charset=utf-8"}
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
            def getcode(self):
                return 200
            def read(self, n=200 * 1024):
                return b"<html><body><p>Hello web</p></body></html>"
        mock_urlopen.return_value = MockResp()
        text, err = fetch_url("https://example.com")
        self.assertIsNone(err)
        self.assertIn("Hello web", text)


class ToolExecutorWebTests(unittest.TestCase):
    def test_web_fetch_gated_by_use_web(self):
        executor = ToolExecutor()
        # Web disabled → rejected
        result = executor.execute(
            '{"tool": "web_fetch", "arguments": {"url": "https://example.com"}}',
            use_web=False,
        )
        self.assertFalse(result["success"])
        self.assertIn("Web access is disabled", result.get("message", ""))

        # Web enabled → works (mocked)
        with mock.patch(
            "runtime.tools.web_fetch.fetch_url",
            return_value=("fetched page content", None),
        ):
            result = executor.execute(
                '{"tool": "web_fetch", "arguments": {"url": "https://example.com"}}',
                use_web=True,
            )
            self.assertTrue(result["success"])
            self.assertTrue(result["verified"])

    def test_web_fetch_requires_url(self):
        executor = ToolExecutor()
        result = executor.execute(
            '{"tool": "web_fetch", "arguments": {}}',
            use_web=True,
        )
        self.assertFalse(result["success"])
        self.assertIn("url", result.get("message", "").lower())


if __name__ == "__main__":
    unittest.main()
