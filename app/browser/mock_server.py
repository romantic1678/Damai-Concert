"""Tiny local static server for browser mock fixtures (tests / demos)."""

from __future__ import annotations

import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class _Utf8Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **getattr(SimpleHTTPRequestHandler, "extensions_map", {}),
        ".html": "text/html; charset=utf-8",
        ".htm": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
    }

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


class MockBrowserServer:
    def __init__(self, directory: Path, host: str = "127.0.0.1", port: int = 0) -> None:
        handler = partial(_Utf8Handler, directory=str(directory))
        self._httpd = ThreadingHTTPServer((host, port), handler)
        self.host = host
        self.port = int(self._httpd.server_address[1])
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def url(self, name: str) -> str:
        return f"{self.base_url}/{name.lstrip('/')}"

    def start(self) -> None:
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
