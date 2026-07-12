"""
Zero-dependency HTTP server for the NCI nerdcommand options-assistant dashboard.

Built on the Python standard library only (``http.server``) — no Flask/FastAPI,
no npm, no build step. Serves a self-contained single-page UI and a small JSON
API backed by :class:`DashboardAPI`.

Run:  python3 -m nci_dashboard  [--host 127.0.0.1] [--port 8765]
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .api import ApiError, DashboardAPI
from .paths import STATIC_DIR

MAX_BODY_BYTES = 1_000_000


class DashboardHandler(BaseHTTPRequestHandler):
    """Routes HTTP requests to the shared :class:`DashboardAPI` instance."""

    server_version = "NCIDashboard/1.0"
    api: DashboardAPI  # injected onto the class in ``build_server``

    # ── helpers ──────────────────────────────────────────────────────

    def _send_json(self, obj, status: int = 200) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_error_json(self, message: str, status: int = 400) -> None:
        self._send_json({"error": message, "status": status}, status=status)

    def _send_file(self, path, content_type: str) -> None:
        try:
            data = path.read_bytes()
        except OSError:
            self._send_error_json("asset not found", status=404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > MAX_BODY_BYTES:
            raise ApiError("request body too large", status=413)
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ApiError("request body must be valid JSON")
        if not isinstance(data, dict):
            raise ApiError("request body must be a JSON object")
        return data

    def log_message(self, fmt, *args):  # noqa: D401 - quieter default logging
        # Keep the console readable; comment out to restore access logs.
        return

    # ── routing ──────────────────────────────────────────────────────

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path in ("/", "/index.html"):
                self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            elif path == "/api/health":
                self._send_json(self.api.health())
            elif path == "/api/meta":
                self._send_json(self.api.meta())
            elif path == "/api/phoenix":
                self._send_json(self.api.phoenix_state())
            elif path == "/api/phoenix/versions":
                self._send_json(self.api.phoenix_versions())
            else:
                self._send_error_json("not found", status=404)
        except ApiError as e:
            self._send_error_json(e.message, status=e.status)
        except Exception as e:  # pragma: no cover - defensive
            self._send_error_json(f"internal error: {e}", status=500)

    do_HEAD = do_GET

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self._read_json_body()
            if path == "/api/strategies":
                self._send_json(self.api.select_strategies(payload))
            elif path == "/api/ask":
                self._send_json(self.api.ask(payload))
            elif path == "/api/outcome":
                self._send_json(self.api.record_outcome(payload))
            else:
                self._send_error_json("not found", status=404)
        except ApiError as e:
            self._send_error_json(e.message, status=e.status)
        except Exception as e:  # pragma: no cover - defensive
            self._send_error_json(f"internal error: {e}", status=500)


def build_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Construct a ready-to-serve HTTP server with a shared API instance."""
    handler = type("BoundDashboardHandler", (DashboardHandler,), {"api": DashboardAPI()})
    return ThreadingHTTPServer((host, port), handler)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="NCI nerdcommand dashboard server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    httpd = build_server(args.host, args.port)
    api: DashboardAPI = httpd.RequestHandlerClass.api
    mode = "LIVE (Claude)" if api.brain.claude.available else "OFFLINE (deterministic)"
    print(f"NCI nerdcommand dashboard → http://{args.host}:{args.port}")
    print(f"AI reasoning mode: {mode}")
    print("Educational analysis tooling — not investment advice.")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        httpd.server_close()
    return 0
