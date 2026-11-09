"""Offscreen Qt smoke test for MainWindow."""

from __future__ import annotations

import os

import pytest

# Must set before QApplication
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.gui.main_window import MainWindow
from app.gui.status_labels import LABEL_MONITORING, LABEL_WAIT_SALE, display_status
from app.lifecycle import Application
from app.models import ConcertTask


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    yield app


def test_display_status_labels() -> None:
    t = ConcertTask(name="A", status="pending")
    assert display_status(t) == LABEL_WAIT_SALE
    t2 = ConcertTask(name="B", status="watching", monitor_enabled=True)
    assert display_status(t2) == LABEL_MONITORING


def test_main_window_offscreen(qapp: QApplication, example_settings_yaml, tmp_path) -> None:
    application = Application.create(
        settings_path=example_settings_yaml,
        database_path=tmp_path / "gui.db",
        ensure_settings=False,
        browser_headless=True,
    )
    try:
        window = MainWindow(application)
        window.show()
        qapp.processEvents()
        assert "大麦开票助手" in window.windowTitle() or "Damai" in window.windowTitle()
        assert window.task_panel is not None
        assert window.log_panel is not None
        window.close()
        qapp.processEvents()
    finally:
        application.shutdown()
