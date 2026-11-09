"""Pytest fixtures for Damai Ticket Assistant."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.config import Settings, load_settings
from app.lifecycle import Application
from app.logging_config import setup_logging


@pytest.fixture()
def example_settings_yaml(tmp_path: Path) -> Path:
    data = {
        "app": {"name": "Test Assistant", "mode": "monitor_reminder"},
        "monitor": {"poll_interval_seconds": 60, "timezone": "Asia/Shanghai"},
        "database": {"path": str(tmp_path / "test.db")},
        "logging": {
            "level": "WARNING",
            "console": False,
            "file": str(tmp_path / "logs" / "test.log"),
            "max_bytes": 1024,
            "backup_count": 1,
        },
        "url_allowlist": ["damai.cn", "www.damai.cn", "m.damai.cn", "detail.damai.cn"],
        "events": [
            {
                "name": "Fixture Concert",
                "city": "Shanghai",
                "open_sale_at": "2026-12-01T12:00:00+08:00",
            }
        ],
        "notify": {
            "channels": ["console", "logging", "gui"],
            "reminder_offsets_minutes": [10, 1, 0],
            "sound_enabled": False,
            "desktop_enabled": False,
            "gui_enabled": True,
        },
    }
    path = tmp_path / "settings.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


@pytest.fixture()
def settings(example_settings_yaml: Path) -> Settings:
    return load_settings(example_settings_yaml, ensure_exists=False)


@pytest.fixture()
def app(example_settings_yaml: Path, tmp_path: Path) -> Application:
    application = Application.create(
        settings_path=example_settings_yaml,
        database_path=tmp_path / "app.db",
        ensure_settings=False,
    )
    yield application
    application.shutdown()
