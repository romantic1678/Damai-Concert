"""Config loading tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.config import ensure_runtime_settings, load_settings
from app.errors import ConfigError


def test_load_settings_ok(example_settings_yaml: Path) -> None:
    settings = load_settings(example_settings_yaml, ensure_exists=False)
    assert settings.app.mode == "monitor_reminder"
    assert settings.monitor.poll_interval_seconds == 60
    assert "damai.cn" in settings.url_allowlist
    assert settings.events[0].name == "Fixture Concert"


def test_reject_purchase_mode(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "app": {"mode": "purchase"},
                "monitor": {"poll_interval_seconds": 60},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_settings(path, ensure_exists=False)


def test_reject_fast_poll(tmp_path: Path) -> None:
    path = tmp_path / "fast.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "app": {"mode": "monitor_reminder"},
                "monitor": {"poll_interval_seconds": 5},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_settings(path, ensure_exists=False)


def test_ensure_runtime_settings_copies(tmp_path: Path) -> None:
    example = tmp_path / "settings.example.yaml"
    target = tmp_path / "settings.yaml"
    example.write_text(
        yaml.safe_dump(
            {
                "app": {"mode": "monitor_reminder"},
                "monitor": {"poll_interval_seconds": 60},
            }
        ),
        encoding="utf-8",
    )
    result = ensure_runtime_settings(target, example)
    assert result == target
    assert target.is_file()
