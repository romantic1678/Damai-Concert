"""Resolve bundle vs writable paths for source and frozen (PyInstaller) runs.

Windows frozen layout
---------------------
* Read-only resources: ``sys._MEIPASS`` (extracted onedir/onefile payload)
* Writable data (SQLite, logs, settings, Playwright browsers):
  ``%LOCALAPPDATA%\\DamaiTicketAssistant\\``

Linux/macOS frozen (if ever built) fall back to ``~/.local/share/DamaiTicketAssistant``.
Source checkouts keep using the repository root.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "DamaiTicketAssistant"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def meipass() -> Path | None:
    raw = getattr(sys, "_MEIPASS", None)
    return Path(raw) if raw else None


def bundle_root() -> Path:
    """Read-only resources root (repo root in source; _MEIPASS when frozen)."""
    mp = meipass()
    if mp is not None:
        return mp
    return Path(__file__).resolve().parent.parent


def executable_dir() -> Path:
    """Directory containing the running EXE / python script."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return bundle_root()


def writable_root() -> Path:
    """User-writable application data directory."""
    if is_frozen():
        if sys.platform.startswith("win"):
            base = os.environ.get("LOCALAPPDATA") or str(
                Path.home() / "AppData" / "Local"
            )
            root = Path(base) / APP_DIR_NAME
        elif sys.platform == "darwin":
            root = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
        else:
            xdg = os.environ.get("XDG_DATA_HOME")
            root = (
                Path(xdg) / APP_DIR_NAME
                if xdg
                else Path.home() / ".local" / "share" / APP_DIR_NAME
            )
        root.mkdir(parents=True, exist_ok=True)
        (root / "data" / "logs").mkdir(parents=True, exist_ok=True)
        return root
    # Source tree: project root (data/ under repo)
    return bundle_root()


def resource_path(*parts: str) -> Path:
    """Path inside the read-only bundle (config examples, packaged assets)."""
    return bundle_root().joinpath(*parts)


def data_path(*parts: str) -> Path:
    """Path under writable data directory."""
    path = writable_root().joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def default_settings_path() -> Path:
    if is_frozen():
        return writable_root() / "config" / "settings.yaml"
    return bundle_root() / "config" / "settings.yaml"


def default_settings_example_path() -> Path:
    # Prefer bundled example when frozen
    candidate = resource_path("config", "settings.example.yaml")
    if candidate.is_file():
        return candidate
    return bundle_root() / "config" / "settings.example.yaml"


def playwright_browsers_dir() -> Path:
    """Directory for Playwright browser binaries (writable when frozen)."""
    env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env and env not in {"0", "1"}:
        path = Path(env)
        path.mkdir(parents=True, exist_ok=True)
        return path
    if is_frozen():
        # Prefer next to EXE if build script placed browsers there; else LocalAppData
        beside = executable_dir() / "ms-playwright"
        if beside.is_dir():
            return beside
        path = writable_root() / "ms-playwright"
        path.mkdir(parents=True, exist_ok=True)
        return path
    # Dev: let Playwright use its default cache unless overridden
    return Path.home() / ".cache" / "ms-playwright"


def ensure_playwright_env() -> Path:
    """Set PLAYWRIGHT_BROWSERS_PATH for frozen runs before launching browsers."""
    path = playwright_browsers_dir()
    if is_frozen():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(path)
    return path
