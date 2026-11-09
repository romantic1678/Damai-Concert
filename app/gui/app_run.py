"""Launch the PySide6 GUI."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.gui.main_window import MainWindow
from app.lifecycle import Application
from app.logging_config import get_logger


def run_gui(
    *,
    settings_path: Path | None = None,
    database_path: Path | None = None,
) -> int:
    """Create QApplication + MainWindow. Returns process exit code."""
    # Prefer offscreen only when explicitly requested
    logger = get_logger("gui")
    qt_app = QApplication.instance() or QApplication(sys.argv)
    qt_app.setApplicationName("Damai Ticket Assistant")
    qt_app.setOrganizationName("DamaiTicketAssistant")

    app = Application.create(
        settings_path=settings_path,
        database_path=database_path,
        browser_headless=False,
    )
    window = MainWindow(app)
    window.show()
    logger.info("GUI event loop starting DISPLAY=%s", os.environ.get("DISPLAY"))
    code = qt_app.exec()
    try:
        app.shutdown()
    except Exception:  # noqa: BLE001
        logger.exception("application shutdown after GUI")
    return int(code)
