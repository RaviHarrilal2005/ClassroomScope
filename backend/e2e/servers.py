"""
The backend and the built frontend, served from threads for one session.

Both bind to free ports on 127.0.0.1, so they never collide with dev
servers on 5000 or 5173, and both stop when the session ends.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from werkzeug.serving import make_server

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


class FrontendBuildError(RuntimeError):
    """The frontend could not be built; the message says how to fix it."""


class ServerThread:
    """A server running on a background thread, used as a context manager."""

    def __init__(self, server: Any) -> None:
        self.server = server
        self.thread = threading.Thread(target=server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self.server.server_address[:2]
        return f"http://{host}:{port}"

    def __enter__(self) -> "ServerThread":
        self.thread.start()
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=10)


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:   # keeps pytest's output readable
        pass


def serve_backend(app: Any) -> ServerThread:
    return ServerThread(make_server("127.0.0.1", 0, app, threaded=True))


def serve_static(directory: Path) -> ServerThread:
    return ServerThread(ThreadingHTTPServer(("127.0.0.1", 0), partial(_QuietHandler, directory=str(directory))))


def build_frontend(out_dir: Path, api_base_url: str, frontend_dir: Path = FRONTEND, timeout: int = 60) -> None:
    """The production build, pointed at `api_base_url`, written to `out_dir`."""
    node = shutil.which("node")
    if node is None:
        raise FrontendBuildError("Node.js is not installed or not on PATH: install it from "
                                 "https://nodejs.org, then run `npm install` in frontend/.")
    vite = frontend_dir / "node_modules" / "vite" / "bin" / "vite.js"
    if not vite.is_file():
        raise FrontendBuildError(f"Vite is not installed in {frontend_dir}: run `npm install` there first.")
    env = {**os.environ, "VITE_API_URL": api_base_url}
    try:
        result = subprocess.run(
            [node, str(vite), "build", "--outDir", str(out_dir), "--emptyOutDir"],
            cwd=frontend_dir, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise FrontendBuildError(f"The frontend build took longer than {timeout}s.") from None
    if result.returncode != 0:
        raise FrontendBuildError("The frontend build failed:\n" + (result.stdout + result.stderr)[-3000:])
