"""YAML configuration loading and typed settings."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.errors import ConfigError
from app.models import DEFAULT_URL_ALLOWLIST

# Project root: .../damai-ticket-assistant
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXAMPLE = PROJECT_ROOT / "config" / "settings.example.yaml"
DEFAULT_SETTINGS = PROJECT_ROOT / "config" / "settings.yaml"


@dataclass(slots=True)
class AppSettings:
    name: str = "Damai Ticket Assistant"
    mode: str = "monitor_reminder"


@dataclass(slots=True)
class MonitorSettings:
    poll_interval_seconds: int = 60
    timezone: str = "Asia/Shanghai"


@dataclass(slots=True)
class DatabaseSettings:
    path: str = "data/app.db"


@dataclass(slots=True)
class LoggingSettings:
    level: str = "INFO"
    console: bool = True
    file: str = "data/logs/app.log"
    max_bytes: int = 1_048_576
    backup_count: int = 5


@dataclass(slots=True)
class NotifySettings:
    channels: list[str] = field(default_factory=lambda: ["console"])


@dataclass(slots=True)
class EventPlaceholder:
    name: str
    city: str | None = None
    open_sale_at: str | None = None
    note: str | None = None


@dataclass(slots=True)
class Settings:
    app: AppSettings = field(default_factory=AppSettings)
    monitor: MonitorSettings = field(default_factory=MonitorSettings)
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    notify: NotifySettings = field(default_factory=NotifySettings)
    url_allowlist: tuple[str, ...] = DEFAULT_URL_ALLOWLIST
    events: list[EventPlaceholder] = field(default_factory=list)
    project_root: Path = PROJECT_ROOT

    def resolve_path(self, relative: str) -> Path:
        path = Path(relative)
        if path.is_absolute():
            return path
        return (self.project_root / path).resolve()

    @property
    def database_path(self) -> Path:
        return self.resolve_path(self.database.path)

    @property
    def log_file_path(self) -> Path:
        return self.resolve_path(self.logging.file)


def ensure_runtime_settings(
    settings_path: Path | None = None,
    example_path: Path | None = None,
) -> Path:
    """Copy example settings to runtime path if missing. Returns settings path."""
    target = settings_path or DEFAULT_SETTINGS
    source = example_path or DEFAULT_EXAMPLE
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_file():
        if not source.is_file():
            raise ConfigError(f"missing example config: {source}")
        shutil.copyfile(source, target)
    return target


def _require_mapping(data: Any, label: str) -> dict[str, Any]:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{label} must be a mapping")
    return data


def load_settings(
    path: Path | None = None,
    *,
    ensure_exists: bool = True,
) -> Settings:
    """Load settings from YAML. Optionally copy from example first."""
    settings_path = path or DEFAULT_SETTINGS
    if ensure_exists and path is None:
        settings_path = ensure_runtime_settings()
    if not settings_path.is_file():
        raise ConfigError(f"settings file not found: {settings_path}")

    try:
        with settings_path.open(encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("settings root must be a mapping")

    app_raw = _require_mapping(raw.get("app"), "app")
    monitor_raw = _require_mapping(raw.get("monitor"), "monitor")
    database_raw = _require_mapping(raw.get("database"), "database")
    logging_raw = _require_mapping(raw.get("logging"), "logging")
    notify_raw = _require_mapping(raw.get("notify"), "notify")

    mode = str(app_raw.get("mode", "monitor_reminder"))
    if mode != "monitor_reminder":
        raise ConfigError("app.mode must be monitor_reminder (no purchase mode)")

    poll = int(monitor_raw.get("poll_interval_seconds", 60))
    if poll < 60:
        raise ConfigError("monitor.poll_interval_seconds must be >= 60")

    allow_raw = raw.get("url_allowlist")
    if allow_raw is None:
        allowlist = DEFAULT_URL_ALLOWLIST
    elif isinstance(allow_raw, list) and all(isinstance(x, str) for x in allow_raw):
        allowlist = tuple(allow_raw)
    else:
        raise ConfigError("url_allowlist must be a list of strings")

    events: list[EventPlaceholder] = []
    for item in raw.get("events") or []:
        if not isinstance(item, dict):
            raise ConfigError("events entries must be mappings")
        events.append(
            EventPlaceholder(
                name=str(item.get("name", "")),
                city=item.get("city"),
                open_sale_at=item.get("open_sale_at"),
                note=item.get("note"),
            )
        )

    channels = notify_raw.get("channels", ["console"])
    if not isinstance(channels, list) or not all(isinstance(c, str) for c in channels):
        raise ConfigError("notify.channels must be a list of strings")

    return Settings(
        app=AppSettings(
            name=str(app_raw.get("name", "Damai Ticket Assistant")),
            mode=mode,
        ),
        monitor=MonitorSettings(
            poll_interval_seconds=poll,
            timezone=str(monitor_raw.get("timezone", "Asia/Shanghai")),
        ),
        database=DatabaseSettings(
            path=str(database_raw.get("path", "data/app.db")),
        ),
        logging=LoggingSettings(
            level=str(logging_raw.get("level", "INFO")),
            console=bool(logging_raw.get("console", True)),
            file=str(logging_raw.get("file", "data/logs/app.log")),
            max_bytes=int(logging_raw.get("max_bytes", 1_048_576)),
            backup_count=int(logging_raw.get("backup_count", 5)),
        ),
        notify=NotifySettings(channels=list(channels)),
        url_allowlist=allowlist,
        events=events,
        project_root=PROJECT_ROOT,
    )
