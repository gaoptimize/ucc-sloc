"""Local report server. It binds to 127.0.0.1 only."""

from __future__ import annotations

import csv
import io
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from uccskill.report import csv_rows
from uccskill.report_html import render_header, render_page, render_progress, render_rules, rules_text
from uccskill.snapshot import find_snapshot, load_snapshots


class ReportState:
    """Progress for a count that is still running, then the finished snapshots."""

    def __init__(self, echo: bool = False):
        self.echo = echo
        self._lock = threading.Lock()
        self.phase = "listing"
        self.total = 0
        self.done = 0
        self.current = ""
        self.snapshots = None

    def scanning(self, path: str) -> None:
        with self._lock:
            if self.phase == "listing":
                self.current = path

    def found(self, total: int) -> None:
        with self._lock:
            self.total = total
            self.done = 0
            self.phase = "counting"
            self.current = ""
        if self.echo:
            print(f"Counting {total} files", flush=True)

    def tick(self, done: int, current: str) -> None:
        with self._lock:
            self.done = done
            self.current = current
            self.phase = "counting"

    def saving(self) -> None:
        with self._lock:
            self.phase = "saving"
            self.done = self.total
            self.current = ""

    def finish(self, snapshots: list[dict]) -> None:
        with self._lock:
            self.snapshots = snapshots
            self.phase = "done"
            self.done = self.total

    def view(self) -> dict:
        with self._lock:
            return {
                "phase": self.phase,
                "total": self.total,
                "done": self.done,
                "current": self.current,
                "snapshots": self.snapshots,
            }


def serve(history, port: int = 8765, open_browser: bool = True) -> ThreadingHTTPServer:
    snapshots = load_snapshots(history)
    handler = _handler(snapshots)
    httpd = _bind(handler, port)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    httpd.report_thread = thread
    thread.start()
    host, bound = httpd.server_address[:2]
    url = f"http://{host}:{bound}/"
    print(f"Report at {url}")
    if open_browser:
        webbrowser.open(url)
    return httpd


def serve_state(state: ReportState, port: int = 8765, open_browser: bool = True) -> ThreadingHTTPServer:
    handler = _handler(state)
    httpd = _bind(handler, port)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    httpd.report_thread = thread
    thread.start()
    host, bound = httpd.server_address[:2]
    url = f"http://{host}:{bound}/"
    print(f"Report at {url}")
    if open_browser:
        webbrowser.open(url)
    return httpd


def _bind(handler, port: int) -> ThreadingHTTPServer:
    if port == 0:
        return ThreadingHTTPServer(("127.0.0.1", 0), handler)
    last_error = None
    for candidate in range(port, port + 10):
        try:
            return ThreadingHTTPServer(("127.0.0.1", candidate), handler)
        except OSError as exc:
            last_error = exc
    raise OSError(f"no free port from {port} to {port + 9}: {last_error}")


def _handler(snapshots):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if isinstance(snapshots, ReportState):
                view = snapshots.view()
                if view["snapshots"] is None:
                    page = render_progress(
                        view["phase"], view["total"], view["done"], view["current"]
                    ).encode("utf-8")
                    self._send(200, "text/html; charset=utf-8", page)
                    return
                loaded = view["snapshots"]
            else:
                loaded = snapshots
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            snapshot_id = query.get("snapshot", [None])[0]
            if snapshot_id and not _safe_id(snapshot_id):
                self._send(400, "text/plain; charset=utf-8", b"bad snapshot id")
                return
            if parsed.path in {"/", "/index.html"}:
                page = render_page(loaded, snapshot_id).encode("utf-8")
                self._send(200, "text/html; charset=utf-8", page)
                return
            if parsed.path == "/rules":
                page = render_rules(rules_text()).encode("utf-8")
                self._send(200, "text/html; charset=utf-8", page)
                return
            if parsed.path == "/header":
                snapshot = find_snapshot(loaded, snapshot_id)
                path = query.get("path", [None])[0]
                record = _file_in(snapshot, path)
                if snapshot is None or record is None:
                    self._send(404, "text/plain; charset=utf-8", b"not found")
                    return
                back = "/" if not snapshot_id else "/?snapshot=" + snapshot_id
                page = render_header(record.path, record.header, back).encode("utf-8")
                self._send(200, "text/html; charset=utf-8", page)
                return
            if parsed.path == "/export.csv":
                snapshot = find_snapshot(loaded, snapshot_id)
                if snapshot is None:
                    self._send(404, "text/plain; charset=utf-8", b"no snapshot")
                    return
                buffer = io.StringIO()
                writer = csv.writer(buffer)
                writer.writerows(csv_rows(snapshot["files"]))
                payload = buffer.getvalue().encode("utf-8-sig")
                self._send(200, "text/csv; charset=utf-8", payload)
                return
            if parsed.path == "/export.json":
                snapshot = find_snapshot(loaded, snapshot_id)
                if snapshot is None:
                    self._send(404, "text/plain; charset=utf-8", b"no snapshot")
                    return
                payload = json.dumps(_public_snapshot(snapshot), indent=2).encode("utf-8")
                self._send(200, "application/json; charset=utf-8", payload)
                return
            self._send(404, "text/plain; charset=utf-8", b"not found")

        def log_message(self, fmt, *args):
            return

        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _file_in(snapshot: dict | None, path: str | None):
    if snapshot is None or not path or "\\" in path or path.startswith("/"):
        return None
    for record in snapshot["files"]:
        if record.path == path:
            return record
    return None


def _safe_id(value: str) -> bool:
    return bool(value) and all(ch.isalnum() or ch in "T._-" for ch in value)


def _public_snapshot(snapshot: dict) -> dict:
    return {
        "version": snapshot.get("version"),
        "id": snapshot.get("id"),
        "created": snapshot.get("created"),
        "root": snapshot.get("root"),
        "label": snapshot.get("label"),
        "git_ref": snapshot.get("git_ref"),
        "files": [record.to_json() for record in snapshot["files"]],
    }
