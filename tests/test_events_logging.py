"""Tests for genuine execution-event logging.

The real logs/runtime.jsonl is never touched. log_event is intercepted via
mock.patch.
"""

import unittest
import json
import os
import shutil
import tempfile
import urllib.error
from pathlib import Path
from unittest import mock

from runtime.model.tool_executor import ToolExecutor
from runtime.orchestrator import Orchestrator
from runtime.server import handlers as h
from runtime.tools.default_tools import create_registry
from runtime.tools.registry import Tool


def _raising_handler():
    raise RuntimeError("boom")


class OrchestratorEventTests(unittest.TestCase):
    def _run_with_capture(self, fn):
        store = []
        with mock.patch(
            "runtime.monitor.monitor.log_event",
            side_effect=lambda event, data: store.append((event, data)),
        ):
            fn(store)
        return store

    def test_tool_not_found_logged(self):
        orch = Orchestrator()

        def fn(store):
            result = orch.run_tool("no_such_tool")
            store.append(("result", result.success))

        store = self._run_with_capture(fn)
        self.assertIn(("result", False), store)
        self.assertIn(("tool_not_found", {"tool": "no_such_tool"}), store)

    def test_tool_start_and_success_logged(self):
        orch = Orchestrator()
        orch.tools.tools["fake_ok"] = Tool("fake_ok", "desc", lambda: "ok")

        def fn(store):
            result = orch.run_tool("fake_ok")
            store.append(("result", result.success))

        store = self._run_with_capture(fn)
        self.assertIn(("result", True), store)
        names = [name for name, _ in store]
        self.assertIn("tool_start", names)
        self.assertIn("tool_success", names)
        # Tool name only; never the task content.
        for _, data in store:
            if isinstance(data, dict):
                self.assertNotIn("task", data)

    def test_tool_failure_logged_without_task_content(self):
        orch = Orchestrator()
        orch.tools.tools["fake_bad"] = Tool("fake_bad", "desc", _raising_handler)

        def fn(store):
            result = orch.run_tool("fake_bad")
            store.append(("result", (result.success, result.error)))

        store = self._run_with_capture(fn)
        self.assertIn(("result", (False, "boom")), store)
        self.assertIn(("tool_failure", {"tool": "fake_bad", "error": "boom"}), store)


class ChatRequestEventTests(unittest.TestCase):
    def test_log_chat_request_records_count_and_model_only(self):
        store = []
        with mock.patch(
            "runtime.monitor.monitor.log_event",
            side_effect=lambda event, data: store.append((event, data)),
        ):
            h._log_chat_request(
                [{"role": "user", "content": "private prompt"}],
                "local-model",
                request_id="req-abc",
            )
        # Only the message count, model, and request ID are logged - never
        # the body or prompts.
        self.assertEqual(
            store,
            [("chat_request", {"request_id": "req-abc", "messages": 1, "model": "local-model", "use_tools": False})],
        )

    def test_log_chat_terminal_success_only_safe_fields(self):
        store = []
        with mock.patch(
            "runtime.monitor.monitor.log_event",
            side_effect=lambda event, data: store.append((event, data)),
        ):
            h._log_chat_terminal("req-abc", "test-model", True)
        self.assertEqual(
            store,
            [("chat_success", {"request_id": "req-abc", "model": "test-model", "success": True})],
        )

    def test_log_chat_terminal_failure_with_coarse_category(self):
        store = []
        with mock.patch(
            "runtime.monitor.monitor.log_event",
            side_effect=lambda event, data: store.append((event, data)),
        ):
            h._log_chat_terminal("req-abc", "test-model", False, category="model_unreachable")
        self.assertEqual(
            store,
            [("chat_failure", {"request_id": "req-abc", "model": "test-model", "success": False, "category": "model_unreachable"})],
        )


class ChatLifecycleEventTests(unittest.TestCase):
    """Test chat request/success/failure events with request ID correlation."""

    def _capture_events(self):
        store = []
        patcher = mock.patch(
            "runtime.monitor.monitor.log_event",
            side_effect=lambda event, data: store.append((event, data)),
        )
        return store, patcher

    def _mock_urlopen_success(self):
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = b'{"choices":[{"message":{"content":"hi"}}]}'
        mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
        mock_resp.__exit__ = mock.Mock(return_value=False)
        return mock_resp

    def test_chat_success_emits_request_and_terminal_with_same_id(self):
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_urlopen_success()
            with patcher:
                h.chat(
                    [{"role": "user", "content": "private prompt"}],
                    model="test-model",
                    request_id="req-123",
                )
        events = {name: data for name, data in store}
        self.assertIn("chat_request", events)
        self.assertIn("chat_success", events)
        self.assertEqual(events["chat_request"]["request_id"], "req-123")
        self.assertEqual(events["chat_success"]["request_id"], "req-123")
        self.assertTrue(events["chat_success"]["success"])
        # Privacy: no message bodies, prompts, or raw content in any event.
        for _, data in store:
            if isinstance(data, dict):
                self.assertNotIn("content", data)
                self.assertNotIn("prompt", data)

    def test_chat_generates_unique_request_id_when_none_provided(self):
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_urlopen_success()
            with patcher:
                h.chat([{"role": "user", "content": "hi"}], model="test-model")
                h.chat([{"role": "user", "content": "hi"}], model="test-model")
        ids = [data["request_id"] for name, data in store if name == "chat_request"]
        self.assertEqual(len(ids), 2)
        self.assertEqual(len(set(ids)), 2)  # unique IDs

    def test_chat_failure_model_unreachable(self):
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=False
        ), mock.patch(
            "runtime.model.router._http_health", return_value=False
        ):
            with patcher:
                with self.assertRaises(ValueError):
                    h.chat(
                        [{"role": "user", "content": "hi"}],
                        model="test-model",
                        request_id="req-fail",
                    )
        events = {name: data for name, data in store}
        self.assertIn("chat_request", events)
        self.assertIn("chat_failure", events)
        self.assertEqual(events["chat_failure"]["request_id"], "req-fail")
        self.assertFalse(events["chat_failure"]["success"])
        self.assertEqual(events["chat_failure"]["category"], "model_unreachable")
        # Privacy: no raw exception or message content.
        for _, data in store:
            if isinstance(data, dict):
                self.assertNotIn("content", data)
                self.assertNotIn("error", data)

    def test_chat_failure_upstream_http_error(self):
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                "http://example.com", 502, "Bad Gateway", {}, None
            )
            with patcher:
                with self.assertRaises(ValueError):
                    h.chat(
                        [{"role": "user", "content": "hi"}],
                        model="test-model",
                        request_id="req-http",
                    )
        events = {name: data for name, data in store}
        self.assertIn("chat_request", events)
        self.assertIn("chat_failure", events)
        self.assertEqual(events["chat_failure"]["request_id"], "req-http")
        self.assertEqual(events["chat_failure"]["category"], "upstream_http_error")

    def test_chat_stream_logs_request_with_id_and_returns_it(self):
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = mock.MagicMock()
            mock_resp.readline.return_value = b"data: [DONE]\n"
            mock_urlopen.return_value = mock_resp
            with patcher:
                upstream, req_id = h.chat_stream_raw(
                    [{"role": "user", "content": "hi"}],
                    model="test-model",
                    request_id="req-stream",
                )
            # Drain the stream
            for _ in upstream:
                pass
            upstream.close()
        events = {name: data for name, data in store}
        self.assertIn("chat_request", events)
        self.assertEqual(events["chat_request"]["request_id"], "req-stream")
        # Returned request_id matches the one we passed in.
        self.assertEqual(req_id, "req-stream")

    def test_chat_stream_terminal_success_after_done(self):
        """Simulates what app.py:_stream_chat() does after [DONE]."""
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = mock.MagicMock()
            mock_resp.readline.side_effect = [
                b'data: {"choices":[{"delta":{"content":"hello"}}]}\n',
                b"data: [DONE]\n",
            ]
            mock_urlopen.return_value = mock_resp
            with patcher:
                upstream, req_id = h.chat_stream_raw(
                    [{"role": "user", "content": "hi"}],
                    model="test-model",
                    request_id="req-stream-ok",
                )
                for _ in upstream:
                    pass
                upstream.close()
                # app.py:_stream_chat() logs terminal success after stream completes.
                h._log_chat_terminal(req_id, "test-model", True)
        events = {name: data for name, data in store}
        self.assertIn("chat_success", events)
        self.assertEqual(events["chat_success"]["request_id"], "req-stream-ok")
        self.assertTrue(events["chat_success"]["success"])

    def test_chat_stream_terminal_failure_on_interruption(self):
        """Simulates what app.py:_stream_chat() does on stream error."""
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = mock.MagicMock()
            mock_resp.readline.side_effect = OSError("connection reset")
            mock_urlopen.return_value = mock_resp
            with patcher:
                upstream, req_id = h.chat_stream_raw(
                    [{"role": "user", "content": "hi"}],
                    model="test-model",
                    request_id="req-stream-err",
                )
                try:
                    for _ in upstream:
                        pass
                except OSError:
                    pass
                upstream.close()
                # app.py:_stream_chat() logs terminal failure on interruption.
                h._log_chat_terminal(
                    req_id, "test-model", False, category="stream_interrupted"
                )
        events = {name: data for name, data in store}
        self.assertIn("chat_failure", events)
        self.assertEqual(events["chat_failure"]["request_id"], "req-stream-err")
        self.assertFalse(events["chat_failure"]["success"])
        self.assertEqual(events["chat_failure"]["category"], "stream_interrupted")

    def test_chat_stream_model_unreachable_emits_failure(self):
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=False
        ), mock.patch(
            "runtime.model.router._http_health", return_value=False
        ):
            with patcher:
                with self.assertRaises(ValueError):
                    h.chat_stream_raw(
                        [{"role": "user", "content": "hi"}],
                        model="test-model",
                        request_id="req-stream-fail",
                    )
        events = {name: data for name, data in store}
        self.assertIn("chat_request", events)
        self.assertIn("chat_failure", events)
        self.assertEqual(events["chat_failure"]["request_id"], "req-stream-fail")
        self.assertEqual(events["chat_failure"]["category"], "model_unreachable")

    def test_chat_stream_eof_without_done_is_failure(self):
        """Stream ending without [DONE] must be logged as chat_failure, not
        chat_success (defect: truncated stream was previously marked success)."""
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = mock.MagicMock()
            mock_resp.readline.return_value = b""  # EOF, no [DONE]
            mock_urlopen.return_value = mock_resp
            with patcher:
                upstream, req_id = h.chat_stream_raw(
                    [{"role": "user", "content": "hi"}],
                    model="test-model",
                    request_id="req-eof",
                )
                try:
                    for _ in upstream:
                        pass
                except Exception:
                    pass
                upstream.close()
                # app.py:_stream_chat() logs terminal after stream ends.
                if not any(
                    name == "chat_failure" for name, _ in store
                ):
                    h._log_chat_terminal(
                        req_id, "test-model", False, category="stream_interrupted"
                    )
        events = {name: data for name, data in store}
        self.assertIn("chat_request", events)
        self.assertIn("chat_failure", events)
        self.assertEqual(events["chat_failure"]["request_id"], "req-eof")
        self.assertFalse(events["chat_failure"]["success"])
        self.assertEqual(events["chat_failure"]["category"], "stream_interrupted")
        self.assertNotIn("chat_success", events)

    def test_no_duplicate_terminal_events(self):
        """Exactly one terminal event per request, even on success."""
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_urlopen_success()
            with patcher:
                h.chat(
                    [{"role": "user", "content": "hi"}],
                    model="test-model",
                    request_id="req-once",
                )
        terminal = [name for name, _ in store if name in ("chat_success", "chat_failure")]
        self.assertEqual(len(terminal), 1)


class ToolExecutorTests(unittest.TestCase):
    """Tests for runtime.model.tool_executor.ToolExecutor using mocks."""

    def test_validate_arguments_valid(self):
        executor = ToolExecutor()
        ok, error = executor._validate_arguments("system_info", {})
        self.assertTrue(ok)
        self.assertIsNone(error)

    def test_validate_arguments_not_dict(self):
        executor = ToolExecutor()
        ok, error = executor._validate_arguments("system_info", "not-a-dict")
        self.assertFalse(ok)
        self.assertEqual(error, "arguments must be an object")

    def test_validate_arguments_extra_arguments(self):
        executor = ToolExecutor()
        ok, error = executor._validate_arguments("system_info", {"foo": "bar"})
        self.assertFalse(ok)
        self.assertEqual(error, "system_info takes no arguments")

    def test_validate_arguments_unknown_tool(self):
        executor = ToolExecutor()
        ok, error = executor._validate_arguments("no_such_tool", {})
        self.assertFalse(ok)
        self.assertEqual(error, "Unknown tool: no_such_tool")

    def test_execute_valid_tool_request(self):
        executor = ToolExecutor()
        # Replace the handler on the registry tool object (handler refs are
        # captured at registry creation time, so module-level mocking won't work).
        tool = executor.registry.get("system_info")
        original_handler = tool.handler
        tool.handler = lambda: {"cpu_cores": 4, "memory": "Mem: 4096"}
        try:
            result = executor.execute(
                '{"tool": "system_info", "arguments": {}}'
            )
        finally:
            tool.handler = original_handler
        self.assertTrue(result["success"])
        self.assertEqual(result["tool"], "system_info")
        self.assertEqual(result["output"], {"cpu_cores": 4, "memory": "Mem: 4096"})

    def test_execute_unknown_tool(self):
        executor = ToolExecutor()
        result = executor.execute(
            '{"tool": "no_such_tool", "arguments": {}}'
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["tool"], "no_such_tool")
        self.assertIn("Unknown tool", result["message"])

    def test_execute_no_tool_request(self):
        executor = ToolExecutor()
        result = executor.execute("Just some plain text response.")
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "No valid tool request.")

    def test_execute_invalid_arguments(self):
        executor = ToolExecutor()
        result = executor.execute(
            '{"tool": "system_info", "arguments": {"foo": "bar"}}'
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["tool"], "system_info")
        self.assertIn("takes no arguments", result["message"])


class ChatToolLoopTests(unittest.TestCase):
    """Tests for handlers.chat() tool-use loop using mocks (no real model)."""

    def _capture_events(self):
        store = []
        patcher = mock.patch(
            "runtime.monitor.monitor.log_event",
            side_effect=lambda event, data: store.append((event, data)),
        )
        return store, patcher

    def _mock_urlopen_response(self, content_text):
        """Return a mock urllib response with a chat completion containing text."""
        mock_resp = mock.MagicMock()
        body = {
            "choices": [{"message": {"role": "assistant", "content": content_text}}],
            "model": "test-model",
        }
        mock_resp.read.return_value = json.dumps(body).encode("utf-8")
        mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
        mock_resp.__exit__ = mock.Mock(return_value=False)
        return mock_resp

    def test_chat_no_tool_request_returns_directly(self):
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_urlopen_response(
                "Hello, how can I help?"
            )
            with patcher:
                result = h.chat(
                    [{"role": "user", "content": "hi"}],
                    model="test-model",
                    request_id="req-direct",
                )
        events = {name: data for name, data in store}
        self.assertIn("chat_request", events)
        self.assertIn("chat_success", events)
        self.assertEqual(result["choices"][0]["message"]["content"], "Hello, how can I help?")
        # No tool events.
        self.assertNotIn("tool_request", events)
        self.assertNotIn("tool_executed", events)

    def test_chat_use_tools_false_skips_tool_loop(self):
        """When use_tools=False, tool requests in model output are ignored."""
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            # Model output contains a tool request, but use_tools=False
            mock_urlopen.return_value = self._mock_urlopen_response(
                '{"tool": "system_info", "arguments": {}}'
            )
            with patcher:
                result = h.chat(
                    [{"role": "user", "content": "hi"}],
                    model="test-model",
                    request_id="req-no-tools",
                    use_tools=False,
                )
        # Only one model call — no tool loop.
        self.assertEqual(mock_urlopen.call_count, 1)
        events = {name: data for name, data in store}
        self.assertIn("chat_request", events)
        self.assertIn("chat_success", events)
        # use_tools recorded in request event.
        self.assertFalse(events["chat_request"]["use_tools"])
        # No tool events.
        self.assertNotIn("tool_request", events)
        self.assertNotIn("tool_executed", events)
        # No tool_used in result.
        self.assertNotIn("tool_used", result)

    def test_chat_use_tools_true_records_in_event(self):
        """When use_tools=True (default), use_tools is recorded in event."""
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_urlopen_response(
                "Hello, how can I help?"
            )
            with patcher:
                h.chat(
                    [{"role": "user", "content": "hi"}],
                    model="test-model",
                    request_id="req-tools-on",
                    use_tools=True,
                )
        events = {name: data for name, data in store}
        self.assertTrue(events["chat_request"]["use_tools"])

    def test_chat_tool_used_indicator_in_result(self):
        """When a tool is executed, result includes tool_used real event data."""
        store, patcher = self._capture_events()
        reg = create_registry()
        tool = reg.get("system_info")
        original_handler = tool.handler
        tool.handler = lambda: {"cpu_cores": 4}
        try:
            with mock.patch(
                "runtime.model.router.router_running", return_value=True
            ), mock.patch("urllib.request.urlopen") as mock_urlopen:
                mock_urlopen.side_effect = [
                    self._mock_urlopen_response(
                        '{"tool": "system_info", "arguments": {}}'
                    ),
                    self._mock_urlopen_response("Here is your system info."),
                ]
                with patcher:
                    result = h.chat(
                        [{"role": "user", "content": "system info"}],
                        model="test-model",
                        request_id="req-tool-indicator",
                        use_tools=True,
                    )
        finally:
            tool.handler = original_handler
        # Result includes tool_used with real tool name.
        self.assertIn("tool_used", result)
        self.assertEqual(result["tool_used"]["tool"], "system_info")
        self.assertTrue(result["tool_used"]["executed"])

    def test_chat_tool_request_executed_then_final(self):
        store, patcher = self._capture_events()
        # Replace the handler on the registry tool object.
        from runtime.tools.default_tools import create_registry
        reg = create_registry()
        tool = reg.get("system_info")
        original_handler = tool.handler
        tool.handler = lambda: {"cpu_cores": 4, "memory": "Mem: 4096 MB"}
        try:
            with mock.patch(
                "runtime.model.router.router_running", return_value=True
            ), mock.patch("urllib.request.urlopen") as mock_urlopen:
                mock_urlopen.side_effect = [
                    self._mock_urlopen_response(
                        '{"tool": "system_info", "arguments": {}}'
                    ),
                    self._mock_urlopen_response("Here is your system info."),
                ]
                with patcher:
                    result = h.chat(
                        [{"role": "user", "content": "system info"}],
                        model="test-model",
                        request_id="req-tool",
                    )
        finally:
            tool.handler = original_handler
        events = {name: data for name, data in store}
        self.assertIn("chat_request", events)
        self.assertIn("tool_request", events)
        self.assertEqual(events["tool_request"]["tool"], "system_info")
        self.assertIn("tool_executed", events)
        self.assertEqual(events["tool_executed"]["tool"], "system_info")
        self.assertIn("chat_success", events)
        # Final response from second model call.
        self.assertEqual(result["choices"][0]["message"]["content"], "Here is your system info.")
        # Privacy: no message content, no raw output text in events.
        for _, data in store:
            if isinstance(data, dict):
                self.assertNotIn("content", data)
                self.assertNotIn("Mem:", str(data))

    def test_chat_tool_request_invalid_arguments(self):
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_urlopen_response(
                '{"tool": "system_info", "arguments": {"extra": true}}'
            )
            with patcher:
                result = h.chat(
                    [{"role": "user", "content": "hi"}],
                    model="test-model",
                    request_id="req-bad-args",
                )
        events = {name: data for name, data in store}
        self.assertIn("tool_request", events)
        self.assertIn("tool_error", events)
        self.assertEqual(events["tool_error"]["tool"], "system_info")
        # Privacy: no raw exception text in events.
        self.assertNotIn("message", events["tool_error"])
        # Loop completes and returns last result (no crash).
        self.assertIsNotNone(result)

    def test_chat_max_tool_iterations(self):
        store, patcher = self._capture_events()
        # Replace the handler on the registry tool object.
        from runtime.tools.default_tools import create_registry
        reg = create_registry()
        tool = reg.get("system_info")
        original_handler = tool.handler
        tool.handler = lambda: {"cpu_cores": 4}
        try:
            with mock.patch(
                "runtime.model.router.router_running", return_value=True
            ), mock.patch("urllib.request.urlopen") as mock_urlopen:
                # Model keeps requesting tools — should stop after MAX_TOOL_ITERATIONS + 1 calls.
                mock_urlopen.side_effect = [
                    self._mock_urlopen_response(
                        '{"tool": "system_info", "arguments": {}}'
                    ),
                    self._mock_urlopen_response(
                        '{"tool": "system_info", "arguments": {}}'
                    ),
                    self._mock_urlopen_response(
                        '{"tool": "system_info", "arguments": {}}'
                    ),
                ]
                with patcher:
                    result = h.chat(
                        [{"role": "user", "content": "hi"}],
                        model="test-model",
                        request_id="req-max",
                    )
        finally:
            tool.handler = original_handler
        events = {name: data for name, data in store}
        # urlopen called 3 times (MAX_TOOL_ITERATIONS + 1).
        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertIn("chat_failure", events)
        self.assertEqual(events["chat_failure"]["category"], "max_iterations")
        self.assertTrue(result.get("max_iterations_reached"))
        self.assertEqual(result["steps"], 2)


    def test_chat_merges_consecutive_user_turns(self):
        """A stale history with two user turns is merged, not rejected."""
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_urlopen_response("ok")
            with patcher:
                h.chat(
                    [
                        {"role": "user", "content": "first"},
                        {"role": "user", "content": "second"},
                    ],
                    model="test-model",
                    request_id="req-merge",
                    use_tools=False,
                )
        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["messages"], [
            {"role": "user", "content": "first\n\nsecond"},
        ])

    def test_chat_tool_loop_sends_alternating_roles(self):
        """Tool results are fed back as assistant/user turns, not role=tool."""
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch(
            "runtime.model.tool_executor.ToolExecutor.execute",
            return_value={"success": True, "tool": "system_info",
                          "output": {"cpu_cores": 4}},
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [
                self._mock_urlopen_response(
                    '{"tool": "system_info", "arguments": {}}'
                ),
                self._mock_urlopen_response("Here is your system info."),
            ]
            with patcher:
                result = h.chat(
                    [{"role": "user", "content": "system info"}],
                    model="test-model",
                    request_id="req-alternate",
                    use_tools=True,
                )
        second = mock_urlopen.call_args_list[1].args[0]
        roles = [m["role"] for m in json.loads(second.data.decode("utf-8"))["messages"]]
        self.assertEqual(roles, ["user", "assistant", "user"])
        self.assertEqual(
            result["choices"][0]["message"]["content"],
            "Here is your system info.",
        )


class ActivityStatusTests(unittest.TestCase):
    """Tests for handlers._activity_status: status mapping from events."""

    def test_success_from_data(self):
        self.assertEqual(h._activity_status("chat_request", {"success": True}), "Success")

    def test_failed_from_data(self):
        self.assertEqual(h._activity_status("chat_request", {"success": False}), "Failed")

    def test_success_from_event_name(self):
        self.assertEqual(h._activity_status("chat_success", {}), "Success")
        self.assertEqual(h._activity_status("tool_success", {}), "Success")

    def test_failed_from_event_name(self):
        self.assertEqual(h._activity_status("chat_failure", {}), "Failed")
        self.assertEqual(h._activity_status("tool_failure", {}), "Failed")
        self.assertEqual(h._activity_status("tool_not_found", {}), "Failed")

    def test_task_events(self):
        self.assertEqual(h._activity_status("task_created", {}), "Created")
        self.assertEqual(h._activity_status("task_updated", {}), "Updated")

    def test_model_events(self):
        self.assertEqual(h._activity_status("model_load", {}), "Loaded")
        self.assertEqual(h._activity_status("model_unload", {}), "Unloaded")
        self.assertEqual(h._activity_status("model_download", {}), "Downloaded")

    def test_health_check(self):
        self.assertEqual(h._activity_status("health_check", {}), "OK")

    def test_unknown_event(self):
        self.assertEqual(h._activity_status("something_unknown", {}), "—")

    def test_none_data(self):
        self.assertEqual(h._activity_status("chat_success", None), "Success")

    def test_task_progress_from_get_tasks(self):
        """get_tasks returns task progress with status fields."""
        import tempfile, os, shutil
        from pathlib import Path
        import runtime.state.task_manager as tm
        orig_tm_db = tm.DB
        tmp = tempfile.mkdtemp(prefix="pv_act_test_")
        tmp_db = os.path.join(tmp, "state.db")
        tm.DB = tmp_db
        tm.init_schema()
        with mock.patch("runtime.monitor.monitor.log_event"):
            tid = tm.add_task("proj", "Task A", priority=3)
            tm.set_status(tid, "completed")
            tm.add_task("proj", "Task B")
        # Monkeypatch handlers.STATE_DB
        import runtime.server.handlers as handlers
        orig = handlers.STATE_DB
        handlers.STATE_DB = Path(tmp_db)
        try:
            result = handlers.get_tasks()
        finally:
            handlers.STATE_DB = orig
            tm.DB = orig_tm_db
        # Active should only include the pending one
        self.assertEqual(len(result["active"]), 1)
        self.assertEqual(result["active"][0]["status"], "active")
        # Recent should include both
        self.assertEqual(len(result["recent"]), 2)
        statuses = {r["status"] for r in result["recent"]}
        self.assertIn("active", statuses)
        self.assertIn("completed", statuses)
        self.assertEqual(result["counts"]["active"], 1)
        self.assertEqual(result["counts"]["completed"], 1)
        self.assertEqual(result["counts"]["total"], 2)
        shutil.rmtree(tmp, ignore_errors=True)

    def test_empty_logs_and_tasks(self):
        """Empty logs and fresh DB produce empty but valid structures."""
        import tempfile, os, shutil
        from pathlib import Path
        import runtime.server.handlers as handlers
        import runtime.state.task_manager as tm
        tmp = tempfile.mkdtemp(prefix="pv_empty_test_")
        tmp_db = os.path.join(tmp, "state.db")
        tmp_log = Path(tmp) / "runtime.jsonl"
        orig_db = handlers.STATE_DB
        orig_logs = handlers.LOGS
        orig_tm_db = tm.DB
        handlers.STATE_DB = Path(tmp_db)
        handlers.LOGS = Path(tmp)
        tm.DB = tmp_db
        tm.init_schema()
        try:
            # Empty log file
            tmp_log.write_text("", encoding="utf-8")
            log_result = handlers.get_logs()
            self.assertEqual(log_result["count"], 0)
            self.assertEqual(log_result["records"], [])
            # Empty tasks
            task_result = handlers.get_tasks()
            self.assertEqual(task_result["active"], [])
            self.assertEqual(task_result["recent"], [])
            self.assertEqual(task_result["projects"], [])
            self.assertEqual(task_result["counts"]["total"], 0)
        finally:
            handlers.STATE_DB = orig_db
            handlers.LOGS = orig_logs
            tm.DB = orig_tm_db
            shutil.rmtree(tmp, ignore_errors=True)

    def test_api_error_states(self):
        """Missing log file and missing DB are handled gracefully."""
        import tempfile, os, shutil
        from pathlib import Path
        import runtime.server.handlers as handlers
        tmp = tempfile.mkdtemp(prefix="pv_err_test_")
        orig_logs = handlers.LOGS
        handlers.LOGS = Path(tmp)
        # No log file exists
        try:
            with self.assertRaises(FileNotFoundError):
                handlers.get_logs()
        finally:
            handlers.LOGS = orig_logs
            shutil.rmtree(tmp, ignore_errors=True)


class TaskAPITests(unittest.TestCase):
    """Tests for task creation, validation, status updates, and privacy."""

    def setUp(self):
        import runtime.server.handlers as handlers
        import runtime.state.task_manager as tm
        self.handlers = handlers
        self._orig_db = handlers.STATE_DB
        self._orig_tm_db = tm.DB
        self.tmp = tempfile.mkdtemp(prefix="pv_taskapi_test_")
        self.tmp_db = os.path.join(self.tmp, "state.db")
        handlers.STATE_DB = Path(self.tmp_db)
        tm.DB = self.tmp_db
        tm.init_schema()
        # Task operations log through the monitor; keep the real log untouched.
        self._log_patcher = mock.patch("runtime.monitor.monitor.log_event")
        self._log_patcher.start()
        self.addCleanup(self._log_patcher.stop)

    def tearDown(self):
        import runtime.state.task_manager as tm
        self.handlers.STATE_DB = self._orig_db
        tm.DB = self._orig_tm_db
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_create_task_valid(self):
        result = self.handlers.create_task(
            project="proj", title="Do something", priority=3, notes="note"
        )
        self.assertEqual(result["project"], "proj")
        self.assertEqual(result["title"], "Do something")
        self.assertEqual(result["priority"], 3)
        self.assertEqual(result["status"], "active")
        self.assertIsInstance(result["id"], int)

    def test_create_task_missing_project(self):
        with self.assertRaises(ValueError):
            self.handlers.create_task(project="", title="title")

    def test_create_task_missing_title(self):
        with self.assertRaises(ValueError):
            self.handlers.create_task(project="proj", title="")

    def test_create_task_invalid_priority(self):
        with self.assertRaises(ValueError):
            self.handlers.create_task(project="proj", title="title", priority=0)
        with self.assertRaises(ValueError):
            self.handlers.create_task(project="proj", title="title", priority=11)
        with self.assertRaises(ValueError):
            self.handlers.create_task(project="proj", title="title", priority="abc")

    def test_create_task_title_too_long(self):
        with self.assertRaises(ValueError):
            self.handlers.create_task(project="proj", title="x" * 201)

    def test_create_task_notes_too_long(self):
        with self.assertRaises(ValueError):
            self.handlers.create_task(project="proj", title="title", notes="x" * 501)

    def test_create_task_privacy_event(self):
        store = []
        with mock.patch(
            "runtime.monitor.monitor.log_event",
            side_effect=lambda event, data: store.append((event, data)),
        ):
            self.handlers.create_task(project="proj", title="Secret title", priority=5)
        self.assertEqual(len(store), 1)
        event, data = store[0]
        self.assertEqual(event, "task_created")
        self.assertNotIn("title", data)
        self.assertNotIn("Secret title", str(data))
        self.assertNotIn("notes", data)

    def test_update_task_status_valid(self):
        result = self.handlers.create_task(project="proj", title="Task", priority=5)
        task_id = result["id"]
        update = self.handlers.update_task_status(task_id=task_id, status="completed")
        self.assertEqual(update["status"], "completed")
        self.assertEqual(update["id"], task_id)

    def test_update_task_status_invalid_status(self):
        result = self.handlers.create_task(project="proj", title="Task", priority=5)
        with self.assertRaises(ValueError):
            self.handlers.update_task_status(task_id=result["id"], status="invalid")

    def test_update_task_status_missing_id(self):
        with self.assertRaises(ValueError):
            self.handlers.update_task_status(task_id=None, status="completed")

    def test_update_task_status_privacy_event(self):
        result = self.handlers.create_task(project="proj", title="Secret", priority=5)
        store = []
        with mock.patch(
            "runtime.monitor.monitor.log_event",
            side_effect=lambda event, data: store.append((event, data)),
        ):
            self.handlers.update_task_status(task_id=result["id"], status="completed")
        self.assertEqual(len(store), 1)
        event, data = store[0]
        self.assertEqual(event, "task_updated")
        self.assertNotIn("title", data)
        self.assertNotIn("Secret", str(data))

    def test_task_persistence(self):
        result = self.handlers.create_task(project="proj", title="Persist me", priority=7)
        task_id = result["id"]
        # Verify task persists in DB
        import runtime.state.task_manager as tm
        tm.DB = self.tmp_db
        rows = tm.active_tasks(project="proj")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "Persist me")

    def test_run_task_success(self):
        result = self.handlers.create_task(project="proj", title="Check system", priority=5)
        task_id = result["id"]
        # Mock chat to return a valid response (no tool request needed).
        mock_result = {"choices": [{"message": {"content": "System is healthy."}}]}
        store = []
        with mock.patch(
            "runtime.monitor.monitor.log_event",
            side_effect=lambda event, data: store.append((event, data)),
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = mock.MagicMock()
            mock_resp.read.return_value = json.dumps(mock_result).encode("utf-8")
            mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
            mock_resp.__exit__ = mock.Mock(return_value=False)
            mock_urlopen.return_value = mock_resp
            with mock.patch(
                "runtime.model.router.router_running", return_value=True
            ):
                run_result = self.handlers.run_task(task_id=task_id)
        self.assertEqual(run_result["status"], "completed")
        self.assertEqual(run_result["id"], task_id)
        # Task status in DB should be completed.
        import runtime.state.task_manager as tm
        tm.DB = self.tmp_db
        task = tm.get_task(task_id)
        self.assertEqual(task[3], "completed")
        # Step count persisted.
        self.assertEqual(task[9], 0)  # no tool called in this test
        # Events logged.
        event_names = [e for e, _ in store]
        self.assertIn("task_started", event_names)
        self.assertIn("task_completed", event_names)
        self.assertNotIn("task_failed", event_names)
        # Privacy: no title in events.
        for _, data in store:
            if isinstance(data, dict):
                self.assertNotIn("title", data)
                self.assertNotIn("Check system", str(data))

    def test_run_task_failure_no_model(self):
        result = self.handlers.create_task(project="proj", title="Check system", priority=5)
        task_id = result["id"]
        store = []
        with mock.patch(
            "runtime.monitor.monitor.log_event",
            side_effect=lambda event, data: store.append((event, data)),
        ), mock.patch(
            "runtime.model.router.router_running", return_value=False
        ), mock.patch(
            "runtime.model.router._http_health", return_value=False
        ):
            with self.assertRaises(ValueError):
                self.handlers.run_task(task_id=task_id)
        # Task status should be failed.
        import runtime.state.task_manager as tm
        tm.DB = self.tmp_db
        task = tm.get_task(task_id)
        self.assertEqual(task[3], "failed")
        event_names = [e for e, _ in store]
        self.assertIn("task_started", event_names)
        self.assertIn("task_failed", event_names)
        self.assertNotIn("task_completed", event_names)

    def test_run_task_invalid_id(self):
        with self.assertRaises(ValueError):
            self.handlers.run_task(task_id=None)
        with self.assertRaises(ValueError):
            self.handlers.run_task(task_id=0)
        with self.assertRaises(ValueError):
            self.handlers.run_task(task_id="abc")

    def test_run_task_not_found(self):
        with self.assertRaises(ValueError):
            self.handlers.run_task(task_id=99999)

    def test_run_task_duplicate_prevention(self):
        result = self.handlers.create_task(project="proj", title="Task", priority=5)
        task_id = result["id"]
        # Simulate concurrent execution by adding to running set.
        import runtime.server.handlers as handlers_mod
        handlers_mod._running_tasks.add(task_id)
        try:
            with self.assertRaises(ValueError) as ctx:
                handlers_mod.run_task(task_id=task_id)
            self.assertIn("already running", str(ctx.exception))
        finally:
            handlers_mod._running_tasks.discard(task_id)

    def test_run_task_privacy_events(self):
        result = self.handlers.create_task(project="proj", title="Secret task title", priority=5)
        task_id = result["id"]
        store = []
        with mock.patch(
            "runtime.monitor.monitor.log_event",
            side_effect=lambda event, data: store.append((event, data)),
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = mock.MagicMock()
            mock_resp.read.return_value = json.dumps(
                {"choices": [{"message": {"content": "done"}}]}
            ).encode("utf-8")
            mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
            mock_resp.__exit__ = mock.Mock(return_value=False)
            mock_urlopen.return_value = mock_resp
            with mock.patch(
                "runtime.model.router.router_running", return_value=True
            ):
                self.handlers.run_task(task_id=task_id)
        # No event should contain the task title.
        for _, data in store:
            if isinstance(data, dict):
                self.assertNotIn("title", data)
                self.assertNotIn("Secret task title", str(data))

    def test_run_task_multi_step_success(self):
        """Multi-step: tool called then final answer. Task completed with step count."""
        result = self.handlers.create_task(project="proj", title="Check system", priority=5)
        task_id = result["id"]
        store = []
        with mock.patch(
            "runtime.monitor.monitor.log_event",
            side_effect=lambda event, data: store.append((event, data)),
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp1 = mock.MagicMock()
            mock_resp1.read.return_value = json.dumps(
                {"choices": [{"message": {"content": '{"tool": "system_info", "arguments": {}}'}}]}
            ).encode("utf-8")
            mock_resp1.__enter__ = mock.Mock(return_value=mock_resp1)
            mock_resp1.__exit__ = mock.Mock(return_value=False)
            mock_resp2 = mock.MagicMock()
            mock_resp2.read.return_value = json.dumps(
                {"choices": [{"message": {"content": "Your system has 8 cores and 7.5Gi RAM."}}]}
            ).encode("utf-8")
            mock_resp2.__enter__ = mock.Mock(return_value=mock_resp2)
            mock_resp2.__exit__ = mock.Mock(return_value=False)
            mock_urlopen.side_effect = [mock_resp1, mock_resp2]
            with mock.patch(
                "runtime.model.router.router_running", return_value=True
            ), mock.patch(
                "runtime.tools.system_info.run",
                return_value={"cpu_cores": 8, "memory": "Mem: 7.5Gi"},
            ):
                run_result = self.handlers.run_task(task_id=task_id)
        self.assertEqual(run_result["status"], "completed")
        self.assertEqual(run_result["steps"], 1)
        # Task in DB has step_count=1 and result persisted.
        import runtime.state.task_manager as tm
        tm.DB = self.tmp_db
        task = tm.get_task(task_id)
        self.assertEqual(task[3], "completed")
        self.assertEqual(task[9], 1)  # step_count
        self.assertIsNotNone(task[8])  # result
        # Events logged include tool_request and tool_executed with step.
        event_names = [e for e, _ in store]
        self.assertIn("task_started", event_names)
        self.assertIn("task_completed", event_names)
        tool_req_events = [d for e, d in store if e == "tool_request"]
        self.assertEqual(tool_req_events[0].get("step"), 1)
        tool_exec_events = [d for e, d in store if e == "tool_executed"]
        self.assertEqual(tool_exec_events[0].get("step"), 1)
        # Privacy: no title or result content in events.
        for _, data in store:
            if isinstance(data, dict):
                self.assertNotIn("title", data)
                self.assertNotIn("8 cores", str(data))

    def test_run_task_step_limit_exhaustion(self):
        """Task fails when model keeps requesting tools (max iterations)."""
        result = self.handlers.create_task(project="proj", title="Loop forever", priority=5)
        task_id = result["id"]
        store = []
        with mock.patch(
            "runtime.monitor.monitor.log_event",
            side_effect=lambda event, data: store.append((event, data)),
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = mock.MagicMock()
            mock_resp.read.return_value = json.dumps(
                {"choices": [{"message": {"content": '{"tool": "system_info", "arguments": {}}'}}]}
            ).encode("utf-8")
            mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
            mock_resp.__exit__ = mock.Mock(return_value=False)
            mock_urlopen.return_value = mock_resp
            with mock.patch(
                "runtime.model.router.router_running", return_value=True
            ), mock.patch(
                "runtime.tools.system_info.run",
                return_value={"cpu_cores": 4},
            ):
                with self.assertRaises(ValueError):
                    self.handlers.run_task(task_id=task_id)
        # Task status should be failed.
        import runtime.state.task_manager as tm
        tm.DB = self.tmp_db
        task = tm.get_task(task_id)
        self.assertEqual(task[3], "failed")
        # step_count persisted (2 = max iterations).
        self.assertEqual(task[9], 2)
        event_names = [e for e, _ in store]
        self.assertIn("task_failed", event_names)
        self.assertNotIn("task_completed", event_names)

    def test_run_task_prompt_includes_notes(self):
        """Task execution passes title + notes as the prompt to the model."""
        result = self.handlers.create_task(
            project="proj", title="Check system", priority=5, notes="focus on CPU"
        )
        task_id = result["id"]
        captured_payloads = []
        with mock.patch(
            "runtime.monitor.monitor.log_event",
            side_effect=lambda event, data: None,
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = mock.MagicMock()
            mock_resp.read.return_value = json.dumps(
                {"choices": [{"message": {"content": "done"}}]}
            ).encode("utf-8")
            mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
            mock_resp.__exit__ = mock.Mock(return_value=False)
            mock_urlopen.return_value = mock_resp
            with mock.patch(
                "runtime.model.router.router_running", return_value=True
            ):
                # Intercept the request payload to check the prompt.
                original_urlopen = mock_urlopen.side_effect
                def capture_urlopen(req, timeout=180):
                    import json as _json
                    captured_payloads.append(_json.loads(req.data.decode("utf-8")))
                    return mock_resp
                mock_urlopen.side_effect = capture_urlopen
                self.handlers.run_task(task_id=task_id)
        # Verify the prompt includes both title and notes.
        self.assertEqual(len(captured_payloads), 1)
        messages = captured_payloads[0]["messages"]
        self.assertEqual(len(messages), 1)
        content = messages[0]["content"]
        self.assertIn("Check system", content)
        self.assertIn("Notes: focus on CPU", content)

    def test_result_persistence_and_retrieval(self):
        """Execution result is persisted and retrievable via get_task_result."""
        result = self.handlers.create_task(project="proj", title="Persist result", priority=5)
        task_id = result["id"]
        with mock.patch(
            "runtime.monitor.monitor.log_event",
            side_effect=lambda event, data: None,
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = mock.MagicMock()
            mock_resp.read.return_value = json.dumps(
                {"choices": [{"message": {"content": "result text"}}], "model": "m"}
            ).encode("utf-8")
            mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
            mock_resp.__exit__ = mock.Mock(return_value=False)
            mock_urlopen.return_value = mock_resp
            with mock.patch(
                "runtime.model.router.router_running", return_value=True
            ):
                self.handlers.run_task(task_id=task_id)
        # Retrieve result.
        retrieved = self.handlers.get_task_result(task_id=task_id)
        self.assertEqual(retrieved["id"], task_id)
        self.assertIn("result", retrieved)
        self.assertEqual(
            retrieved["result"]["choices"][0]["message"]["content"], "result text"
        )

    def test_get_task_result_no_result(self):
        """get_task_result raises ValueError when no result is stored."""
        result = self.handlers.create_task(project="proj", title="No result", priority=5)
        with self.assertRaises(ValueError):
            self.handlers.get_task_result(task_id=result["id"])

    def test_get_task_result_invalid_id(self):
        """get_task_result raises ValueError for invalid IDs."""
        with self.assertRaises(ValueError):
            self.handlers.get_task_result(task_id=None)
        with self.assertRaises(ValueError):
            self.handlers.get_task_result(task_id=0)

    def test_get_task_result_not_found(self):
        """get_task_result raises ValueError for non-existent tasks."""
        with self.assertRaises(ValueError):
            self.handlers.get_task_result(task_id=99999)

    def test_schema_migration_adds_result_column(self):
        """Older DB without result column gets migrated on connect."""
        import sqlite3
        # Create an old-style DB without the result column.
        old_db = os.path.join(self.tmp, "old.db")
        conn = sqlite3.connect(old_db)
        conn.execute("""
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                priority INTEGER NOT NULL DEFAULT 5,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("INSERT INTO tasks (project, title) VALUES ('p', 't')")
        conn.commit()
        conn.close()
        # Point task_manager at the old DB and connect (should migrate).
        import runtime.state.task_manager as tm
        orig_tm_db = tm.DB
        tm.DB = old_db
        db = tm.connect()
        cols = {r[1] for r in db.execute("PRAGMA table_info(tasks)").fetchall()}
        db.close()
        self.assertIn("result", cols)
        # Existing data preserved.
        db = tm.connect()
        row = db.execute("SELECT title FROM tasks WHERE id = 1").fetchone()
        db.close()
        self.assertEqual(row[0], "t")
        tm.DB = orig_tm_db

    def test_get_tasks_after_create(self):
        self.handlers.create_task(project="proj", title="Task 1", priority=5)
        self.handlers.create_task(project="proj", title="Task 2", priority=3)
        result = self.handlers.get_tasks()
        self.assertEqual(len(result["active"]), 2)
        self.assertEqual(result["projects"], ["proj"])


class LocalModelDiscoveryTests(unittest.TestCase):
    """Tests for local model discovery in catalog."""

    def setUp(self):
        import tempfile, os
        self.tmp = tempfile.mkdtemp(prefix="pv_localmodel_test_")
        self.approved_dir = os.path.join(self.tmp, "models")
        os.makedirs(self.approved_dir)
        # Monkeypatch approved dirs
        import runtime.model.catalog as cat
        self._orig_approved = cat.APPROVED_MODEL_DIRS
        self._orig_models_dir = cat.MODELS_DIR
        self._orig_handy = cat.HANDY_COMPUTER_MODELS_DIR
        cat.MODELS_DIR = Path(self.approved_dir)
        cat.HANDY_COMPUTER_MODELS_DIR = Path(os.path.join(self.tmp, "handy"))
        cat.APPROVED_MODEL_DIRS = (cat.MODELS_DIR, cat.HANDY_COMPUTER_MODELS_DIR)

    def tearDown(self):
        import runtime.model.catalog as cat
        cat.APPROVED_MODEL_DIRS = self._orig_approved
        cat.MODELS_DIR = self._orig_models_dir
        cat.HANDY_COMPUTER_MODELS_DIR = self._orig_handy
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_discover_regular_gguf(self):
        import runtime.model.catalog as cat
        gguf = os.path.join(self.approved_dir, "test-model.gguf")
        with open(gguf, "wb") as f:
            f.write(b"\x00" * 1024)
        models = cat._discover_local_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["filename"], "test-model.gguf")
        self.assertTrue(models[0].get("local"))
        self.assertIn("path", models[0])

    def test_discover_valid_symlink(self):
        import runtime.model.catalog as cat
        handy_dir = os.path.join(self.tmp, "handy")
        os.makedirs(handy_dir)
        target = os.path.join(handy_dir, "real-model.gguf")
        with open(target, "wb") as f:
            f.write(b"\x00" * 2048)
        link = os.path.join(self.approved_dir, "linked-model.gguf")
        os.symlink(target, link)
        models = cat._discover_local_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["filename"], "real-model.gguf")

    def test_broken_symlink_rejected(self):
        import runtime.model.catalog as cat
        link = os.path.join(self.approved_dir, "broken.gguf")
        os.symlink("/nonexistent/path/model.gguf", link)
        models = cat._discover_local_models()
        self.assertEqual(len(models), 0)

    def test_non_gguf_rejected(self):
        import runtime.model.catalog as cat
        txt = os.path.join(self.approved_dir, "readme.txt")
        with open(txt, "w") as f:
            f.write("hello")
        models = cat._discover_local_models()
        self.assertEqual(len(models), 0)

    def test_directory_rejected(self):
        import runtime.model.catalog as cat
        subdir = os.path.join(self.approved_dir, "subdir.gguf")
        os.makedirs(subdir)
        models = cat._discover_local_models()
        self.assertEqual(len(models), 0)

    def test_path_traversal_rejected(self):
        import runtime.model.catalog as cat
        # Create a file outside approved dirs
        outside = os.path.join(self.tmp, "evil.gguf")
        with open(outside, "wb") as f:
            f.write(b"\x00" * 512)
        # Try to create a symlink with traversal in name (should be rejected)
        link = os.path.join(self.approved_dir, "..", "evil.gguf")
        try:
            os.symlink(outside, link)
        except FileExistsError:
            pass
        models = cat._discover_local_models()
        # The traversal symlink should not be discovered
        filenames = [m["filename"] for m in models]
        self.assertNotIn("evil.gguf", filenames)

    def test_preserve_existing_catalog(self):
        import runtime.model.catalog as cat
        models = cat.list_models()
        ids = [m["id"] for m in models]
        self.assertIn("smollm2-360m-q8", ids)
        self.assertIn("qwen2.5-0.5b-q4km", ids)
        self.assertIn("llama-3.2-1b-q4km", ids)

    def test_local_model_no_url(self):
        import runtime.model.catalog as cat
        gguf = os.path.join(self.approved_dir, "local-only.gguf")
        with open(gguf, "wb") as f:
            f.write(b"\x00" * 1024)
        models = cat._discover_local_models()
        self.assertEqual(len(models), 1)
        self.assertIsNone(models[0].get("url"))
        self.assertTrue(models[0].get("local"))

    def test_is_safe_gguf_rejects_outside_approved(self):
        import runtime.model.catalog as cat
        # Create a .gguf outside approved dirs
        outside = os.path.join(self.tmp, "outside.gguf")
        with open(outside, "wb") as f:
            f.write(b"\x00" * 512)
        path = Path(outside)
        self.assertFalse(cat._is_safe_gguf(path))

    def test_local_model_entry_has_size(self):
        import runtime.model.catalog as cat
        gguf = os.path.join(self.approved_dir, "sized-model.gguf")
        with open(gguf, "wb") as f:
            f.write(b"\x00" * (5 * 1024 * 1024))  # 5 MB
        models = cat._discover_local_models()
        self.assertEqual(len(models), 1)
        self.assertGreaterEqual(models[0]["size_mb"], 4)


class GetLogsTests(unittest.TestCase):
    """Tests for handlers.get_logs: parsing, ordering, filtering, empty/missing."""

    def setUp(self):
        import runtime.server.handlers as handlers
        self.handlers = handlers
        self._orig_logs = handlers.LOGS
        self.tmp = tempfile.mkdtemp(prefix="pv_logs_test_")
        self.tmp_log = Path(self.tmp) / "runtime.jsonl"
        handlers.LOGS = Path(self.tmp)  # type: ignore[assignment]

    def tearDown(self):
        self.handlers.LOGS = self._orig_logs  # type: ignore[assignment]
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_log(self, lines):
        self.tmp_log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_get_logs_parses_jsonl(self):
        self._write_log([
            json.dumps({"timestamp":"2026-01-01T00:00:00+00:00","event":"chat_request","data":{"request_id":"r1","messages":1,"model":"m"}}),
            json.dumps({"timestamp":"2026-01-01T00:01:00+00:00","event":"chat_success","data":{"request_id":"r1","model":"m","success":True}}),
        ])
        result = self.handlers.get_logs()
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["records"]), 2)

    def test_get_logs_newest_first(self):
        self._write_log([
            json.dumps({"timestamp":"2026-01-01T00:00:00+00:00","event":"chat_request","data":{}}),
            json.dumps({"timestamp":"2026-01-01T00:01:00+00:00","event":"chat_success","data":{}}),
        ])
        result = self.handlers.get_logs()
        self.assertEqual(result["records"][0]["event"], "chat_success")
        self.assertEqual(result["records"][1]["event"], "chat_request")

    def test_get_logs_filters_by_event_type(self):
        self._write_log([
            json.dumps({"timestamp":"2026-01-01T00:00:00+00:00","event":"chat_request","data":{}}),
            json.dumps({"timestamp":"2026-01-01T00:01:00+00:00","event":"tool_success","data":{}}),
            json.dumps({"timestamp":"2026-01-01T00:02:00+00:00","event":"chat_failure","data":{}}),
        ])
        result = self.handlers.get_logs(event_filter="tool")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["records"][0]["event"], "tool_success")

    def test_get_logs_error_filter_matches_fail(self):
        self._write_log([
            json.dumps({"timestamp":"2026-01-01T00:00:00+00:00","event":"chat_failure","data":{}}),
            json.dumps({"timestamp":"2026-01-01T00:01:00+00:00","event":"tool_failure","data":{}}),
        ])
        result = self.handlers.get_logs(event_filter="error")
        self.assertEqual(result["count"], 2)

    def test_get_logs_empty_file(self):
        self._write_log([])
        result = self.handlers.get_logs()
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["records"], [])

    def test_get_logs_missing_file(self):
        if self.tmp_log.exists():
            self.tmp_log.unlink()
        with self.assertRaises(FileNotFoundError):
            self.handlers.get_logs()

    def test_get_logs_skips_invalid_json(self):
        self._write_log([
            "not json at all",
            json.dumps({"timestamp":"2026-01-01T00:00:00+00:00","event":"chat_request","data":{}}),
            "",
            "{broken",
        ])
        result = self.handlers.get_logs()
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["records"][0]["event"], "chat_request")


class LocalModelConnectionTests(unittest.TestCase):
    """Tests for local model connection failure and recovery."""

    def _capture_events(self):
        store = []
        patcher = mock.patch(
            "runtime.monitor.monitor.log_event",
            side_effect=lambda event, data: store.append((event, data)),
        )
        return store, patcher

    def test_chat_connection_refused(self):
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
            with patcher:
                with self.assertRaises(ValueError) as ctx:
                    h.chat(
                        [{"role": "user", "content": "hi"}],
                        model="test-model",
                        request_id="req-conn-refused",
                    )
        self.assertIn("Chat request failed", str(ctx.exception))
        events = {name: data for name, data in store}
        self.assertIn("chat_request", events)
        self.assertIn("chat_failure", events)
        self.assertEqual(events["chat_failure"]["request_id"], "req-conn-refused")
        self.assertEqual(events["chat_failure"]["category"], "request_failed")

    def test_chat_stream_connection_refused(self):
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
            with patcher:
                with self.assertRaises(ValueError):
                    h.chat_stream_raw(
                        [{"role": "user", "content": "hi"}],
                        model="test-model",
                        request_id="req-stream-conn",
                    )
        events = {name: data for name, data in store}
        self.assertIn("chat_request", events)
        self.assertIn("chat_failure", events)
        self.assertEqual(events["chat_failure"]["request_id"], "req-stream-conn")
        self.assertEqual(events["chat_failure"]["category"], "request_failed")

    def test_chat_malformed_json_response(self):
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = mock.MagicMock()
            mock_resp.read.return_value = b"not valid json"
            mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
            mock_resp.__exit__ = mock.Mock(return_value=False)
            mock_urlopen.return_value = mock_resp
            with patcher:
                with self.assertRaises(ValueError):
                    h.chat(
                        [{"role": "user", "content": "hi"}],
                        model="test-model",
                        request_id="req-bad-json",
                    )
        events = {name: data for name, data in store}
        self.assertIn("chat_request", events)
        self.assertIn("chat_failure", events)
        self.assertEqual(events["chat_failure"]["request_id"], "req-bad-json")
        self.assertEqual(events["chat_failure"]["category"], "request_failed")

    def test_chat_recovery_model_becomes_available(self):
        """Model unreachable on first call, available on second."""
        store, patcher = self._capture_events()
        # First call: model unreachable.
        with mock.patch(
            "runtime.model.router.router_running", return_value=False
        ), mock.patch(
            "runtime.model.router._http_health", return_value=False
        ):
            with patcher:
                with self.assertRaises(ValueError):
                    h.chat(
                        [{"role": "user", "content": "hi"}],
                        model="test-model",
                        request_id="req-recover-1",
                    )
        events1 = {name: data for name, data in store}
        self.assertIn("chat_failure", events1)
        self.assertEqual(events1["chat_failure"]["category"], "model_unreachable")

        # Second call: model now available.
        store2 = []
        patcher2 = mock.patch(
            "runtime.monitor.monitor.log_event",
            side_effect=lambda event, data: store2.append((event, data)),
        )
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = mock.MagicMock()
            mock_resp.read.return_value = b'{"choices":[{"message":{"content":"hi"}}]}'
            mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
            mock_resp.__exit__ = mock.Mock(return_value=False)
            mock_urlopen.return_value = mock_resp
            with patcher2:
                result = h.chat(
                    [{"role": "user", "content": "hi"}],
                    model="test-model",
                    request_id="req-recover-2",
                )
        events2 = {name: data for name, data in store2}
        self.assertIn("chat_success", events2)
        self.assertEqual(events2["chat_success"]["request_id"], "req-recover-2")

    def test_chat_stream_connection_refused(self):
        store, patcher = self._capture_events()
        with mock.patch(
            "runtime.model.router.router_running", return_value=True
        ), mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
            with patcher:
                with self.assertRaises(ValueError):
                    h.chat_stream_raw(
                        [{"role": "user", "content": "hi"}],
                        model="test-model",
                        request_id="req-stream-conn-refused",
                    )
        events = {name: data for name, data in store}
        self.assertIn("chat_request", events)
        self.assertIn("chat_failure", events)
        self.assertEqual(events["chat_failure"]["request_id"], "req-stream-conn-refused")
        self.assertEqual(events["chat_failure"]["category"], "request_failed")


if __name__ == "__main__":
    unittest.main()
