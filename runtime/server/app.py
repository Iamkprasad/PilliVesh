"""Tiny localhost HTTP API + static frontend server (stdlib only).

Serves:
  /                  -> frontend/index.html
  /css/*, /js/*, /assets/* (static)
  GET /api/telemetry, /api/benchmark, /api/logs, /api/memory,
      /api/skills, /api/tools, /api/tasks, /api/diagnostics,
      /api/models, /api/model-stats, /api/health
  POST /api/chat (optional stream), /api/benchmark/run,
       and allow-listed model/RAM/stop actions

Background threads (daemon):
  - telemetry sampler (results/telemetry_latest.json every ~5s)
  - light benchmark probe (every ~30s while a model is resident)
  - best-effort auto-load of the first installed catalog model

Binds to 127.0.0.1 only. No auth, no shell, no remote control.
"""
import json
import mimetypes
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"

from runtime.server import handlers

HOST = os.environ.get("AI_LAB_HOST", "127.0.0.1")
PORT = int(os.environ.get("AI_LAB_PORT", "8080"))
TELEMETRY_INTERVAL = float(os.environ.get("AI_LAB_TELEMETRY_INTERVAL", "5"))
BENCH_INTERVAL = float(os.environ.get("AI_LAB_BENCH_INTERVAL", "30"))
AUTOLOAD = os.environ.get("AI_LAB_AUTOLOAD", "1") not in ("0", "false", "no")

_probe_lock = threading.Lock()


def ok(data):
    return {"success": True, "data": data}


def fail(message):
    return {"success": False, "error": str(message)}


class Handler(BaseHTTPRequestHandler):
    server_version = "AILab/1.0"

    def log_message(self, fmt, *args):
        pass  # keep Termux output quiet; errors go to JSON

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path):
        try:
            data = path.read_bytes()
        except Exception:
            self._send_json(fail("File not found"), 404)
            return
        ctype, _ = mimetypes.guess_type(str(path))
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        parsed = urlparse(self.path)
        route = parsed.path.rstrip("/") or "/"
        if route == "/api/server/stop":
            # Localhost-only exit button: respond first, then stop.
            # shutdown() must run on a different thread than serve_forever.
            import threading
            import time as _time
            server = self.server
            def _stop():
                _time.sleep(0.5)
                server.shutdown()
            threading.Thread(target=_stop, daemon=True).start()
            return self._send_json(ok({"stopping": True}))
        if route == "/api/memory/free":
            try:
                return self._send_json(ok(handlers.free_ram()))
            except Exception as e:
                return self._send_json(fail(f"Internal error: {e}"), 500)
        if route == "/api/models/router/stop":
            try:
                return self._send_json(ok(handlers.stop_router()))
            except Exception as e:
                return self._send_json(fail(f"Internal error: {e}"), 500)
        if route == "/api/chat":
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except Exception:
                length = 0
            if length <= 0 or length > 256 * 1024:
                return self._send_json(fail("Bad request"), 400)
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                return self._send_json(fail("Bad request"), 400)
            if not isinstance(body, dict):
                return self._send_json(fail("Bad request"), 400)
            if body.get("stream"):
                return self._stream_chat(body)
            try:
                result = handlers.chat(
                    messages=body.get("messages"),
                    model=body.get("model"),
                    max_tokens=body.get("max_tokens", 512),
                    temperature=body.get("temperature", 0.7),
                )
                return self._send_json(ok(result))
            except ValueError as e:
                return self._send_json(fail(e), 200)
            except Exception as e:
                return self._send_json(fail(f"Internal error: {e}"), 500)
        if route == "/api/benchmark/run":
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except Exception:
                length = 0
            body = {}
            if length > 0:
                if length > 4096:
                    return self._send_json(fail("Bad request"), 400)
                try:
                    parsed = json.loads(self.rfile.read(length).decode("utf-8"))
                    if isinstance(parsed, dict):
                        body = parsed
                except Exception:
                    return self._send_json(fail("Bad request"), 400)
            try:
                if not _probe_lock.acquire(blocking=False):
                    return self._send_json(
                        ok({"status": "in_progress",
                            "message": "Probe already running."})
                    )
                try:
                    result = handlers.run_benchmark(body.get("id"))
                finally:
                    _probe_lock.release()
                return self._send_json(ok(result))
            except ValueError as e:
                return self._send_json(fail(e), 200)
            except Exception as e:
                return self._send_json(fail(f"Internal error: {e}"), 500)
        if route in ("/api/models/download", "/api/models/load",
                     "/api/models/unload"):
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except Exception:
                length = 0
            if length <= 0 or length > 1024:
                return self._send_json(fail("Bad request"), 400)
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                return self._send_json(fail("Bad request"), 400)
            model_id = body.get("id") if isinstance(body, dict) else None
            try:
                if route == "/api/models/download":
                    return self._send_json(ok(handlers.start_download(model_id)))
                if route == "/api/models/load":
                    return self._send_json(ok(handlers.load_model(model_id)))
                return self._send_json(ok(handlers.unload_model(model_id)))
            except ValueError as e:
                return self._send_json(fail(e), 200)
            except Exception as e:
                return self._send_json(fail(f"Internal error: {e}"), 500)
        return self._send_json(fail("Not found"), 404)

    def _stream_chat(self, body):
        """NDJSON stream: lines of {t:d,c:delta} | {t:done} | {t:error,e}."""
        try:
            upstream = handlers.chat_stream_raw(
                messages=body.get("messages"),
                model=body.get("model"),
                max_tokens=body.get("max_tokens", 512),
                temperature=body.get("temperature", 0.7),
            )
        except ValueError as e:
            return self._send_json(fail(e), 200)
        except Exception as e:
            return self._send_json(fail(f"Internal error: {e}"), 500)

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        sent_done = False
        try:
            while True:
                line = upstream.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if not text.startswith("data:"):
                    continue
                data = text[5:].strip()
                if data == "[DONE]":
                    self.wfile.write(b'{"t":"done"}\n')
                    sent_done = True
                    break
                try:
                    obj = json.loads(data)
                except Exception:
                    continue
                choices = obj.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        chunk = json.dumps(
                            {"t": "d", "c": content}, ensure_ascii=False
                        ).encode("utf-8")
                        self.wfile.write(chunk + b"\n")
                    usage = obj.get("usage")
                    if usage:
                        u = json.dumps({"t": "usage", "u": usage})
                        self.wfile.write(u.encode("utf-8") + b"\n")
            if not sent_done:
                self.wfile.write(b'{"t":"done"}\n')
            self.wfile.flush()
        except Exception:
            try:
                self.wfile.write(
                    json.dumps({"t": "error", "e": "stream closed"}).encode()
                    + b"\n"
                )
                self.wfile.flush()
            except Exception:
                pass
        finally:
            try:
                upstream.close()
            except Exception:
                pass

    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)

        def q(name, default=None):
            vals = qs.get(name)
            return vals[0] if vals else default

        try:
            if route == "/api/telemetry":
                return self._send_json(ok(handlers.get_telemetry()))
            if route == "/api/benchmark":
                return self._send_json(ok(handlers.get_benchmark()))
            if route == "/api/logs":
                return self._send_json(ok(handlers.get_logs(
                    limit=q("limit", "100"), event_filter=q("type", "all"))))
            if route == "/api/memory":
                return self._send_json(ok(handlers.get_memory(
                    limit=q("limit", "20"), query=q("q"))))
            if route == "/api/skills":
                return self._send_json(ok(handlers.get_skills(name=q("name"))))
            if route == "/api/tools":
                return self._send_json(ok(handlers.get_tools()))
            if route == "/api/tasks":
                return self._send_json(ok(handlers.get_tasks()))
            if route == "/api/diagnostics":
                return self._send_json(ok(handlers.get_diagnostics()))
            if route == "/api/models":
                return self._send_json(ok(handlers.get_models()))
            if route == "/api/model-stats":
                return self._send_json(ok(handlers.get_model_stats(q("id"))))
            if route == "/api/health":
                return self._send_json(ok({"status": "ok"}))
        except FileNotFoundError as e:
            return self._send_json(fail(e), 200)
        except ValueError as e:
            return self._send_json(fail(e), 200)
        except Exception as e:
            return self._send_json(fail(f"Internal error: {e}"), 500)

        # Static frontend (no directory listing, no traversal).
        rel = parsed.path.lstrip("/")
        if rel == "":
            rel = "index.html"
        target = (FRONTEND / rel).resolve()
        try:
            frontend_root = FRONTEND.resolve()
        except Exception:
            frontend_root = FRONTEND
        if frontend_root not in target.parents and target != frontend_root:
            # Allow exact frontend root files only inside frontend/.
            if not str(target).startswith(str(frontend_root)):
                return self._send_json(fail("Not found"), 404)
        if target.is_dir():
            target = target / "index.html"
        if not target.exists() or not target.is_file():
            # SPA fallback: unknown non-API routes go to index.html
            index = FRONTEND / "index.html"
            if index.exists():
                return self._send_file(index)
            return self._send_json(fail("Not found"), 404)
        return self._send_file(target)


def _telemetry_loop():
    from runtime.monitor import telemetry
    # Seed once immediately so boot is not empty.
    try:
        telemetry.save()
    except Exception:
        pass
    while True:
        time.sleep(max(1.0, TELEMETRY_INTERVAL))
        try:
            telemetry.save()
        except Exception:
            pass


def _probe_loop():
    while True:
        time.sleep(max(5.0, BENCH_INTERVAL))
        if not _probe_lock.acquire(blocking=False):
            continue
        try:
            from benchmarks.probe import run_probe
            run_probe()
        except Exception:
            pass
        finally:
            _probe_lock.release()


def _autoload_model():
    """Best-effort: load the first installed catalog model so port 8081
    (and the opencode llamacpp provider) is ready without a manual Load."""
    if not AUTOLOAD:
        return
    try:
        from runtime.model import router as router_mod
        from runtime.model.catalog import list_models
        from runtime.model.downloader import installed
        if router_mod.router_running():
            return
        have = {m.get("name") for m in installed()}
        for entry in list_models():
            if entry["filename"] in have:
                try:
                    router_mod.load_model(entry["id"])
                except Exception:
                    pass
                return
    except Exception:
        pass


def start_background_threads():
    threading.Thread(target=_telemetry_loop, daemon=True).start()
    threading.Thread(target=_probe_loop, daemon=True).start()
    # Give the HTTP port a moment, then auto-load off the main thread.
    def _delayed_autoload():
        time.sleep(1.0)
        _autoload_model()
    threading.Thread(target=_delayed_autoload, daemon=True).start()


def run(host=HOST, port=PORT):
    server = ThreadingHTTPServer((host, port), Handler)
    print("LOCAL AI CONTROL CENTER")
    print(f"Serving: {FRONTEND}")
    print(f"Open: http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    start_background_threads()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
