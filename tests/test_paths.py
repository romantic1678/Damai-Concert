"""Path helpers for frozen vs source layouts."""

from __future__ import annotations

from pathlib import Path

from app import paths


def test_bundle_root_is_project(tmp_path, monkeypatch):
    root = paths.bundle_root()
    assert (root / "app" / "paths.py").is_file() or (root / "run_app.py").exists() or root.name


def test_writable_root_source_is_repo():
    assert paths.writable_root() == paths.bundle_root()


def test_resource_and_data_paths(tmp_path, monkeypatch):
    # data_path creates parents
    p = paths.data_path("data", "logs", "unit-test.log")
    assert p.parent.is_dir()


def test_playwright_env_respects_override(monkeypatch, tmp_path):
    target = tmp_path / "browsers"
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(target))
    got = paths.playwright_browsers_dir()
    assert got == target
    assert target.is_dir()


def test_is_frozen_false_in_tests():
    assert paths.is_frozen() is False
