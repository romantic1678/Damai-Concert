"""System log panel with logging.Handler bridge."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget


class _LogBridge(QObject):
    message = Signal(str)


class QtLogHandler(logging.Handler):
    def __init__(self, bridge: _LogBridge) -> None:
        super().__init__()
        self._bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._bridge.message.emit(msg)
        except Exception:  # noqa: BLE001
            pass


class LogPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view = QPlainTextEdit()
        self.view.setObjectName("LogView")
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(2000)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self._bridge = _LogBridge()
        self._bridge.message.connect(self._append)
        self._handler = QtLogHandler(self._bridge)
        self._handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s", "%H:%M:%S")
        )
        logging.getLogger().addHandler(self._handler)

    @Slot(str)
    def _append(self, text: str) -> None:
        self.view.appendPlainText(text)

    def detach(self) -> None:
        logging.getLogger().removeHandler(self._handler)
