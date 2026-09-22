"""Tiny localhost HTTP API + static frontend server (stdlib only).

Serves:
  /                  -> frontend/index.html
  /css/*, /js/*, /assets/* (static)
  /api/telemetry, /api/benchmark, /api/logs, /api/memory,
  /api/skills, /api/tools, /api/tasks, /api/diagnostics

Binds to 127.0.0.1 only. All API endpoints are read-only GET.
"""
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"

from runtime.server import handlers

HOST = os.environ.get("AI_LAB_HOST", "127.0.0.1")
PORT = int(os.environ.get("AI_LAB_PORT", "8080"))


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
        if route != "/api/models/download":
            return self._send_json(fail("Not found"), 404)
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
        try:
            return self._send_json(ok(handlers.start_download(
                body.get("id") if isinstance(body, dict) else None)))
        except ValueError as e:
            return self._send_json(fail(e), 200)
        except Exception as e:
            return self._send_json(fail(f"Internal error: {e}"), 500)

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


def run(host=HOST, port=PORT):
    server = ThreadingHTTPServer((host, port), Handler)
    print("LOCAL AI CONTROL CENTER")
    print(f"Serving: {FRONTEND}")
    print(f"Open: http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
