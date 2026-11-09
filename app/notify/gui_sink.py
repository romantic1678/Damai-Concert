"""In-app GUI message sink (queue for future PySide6)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Deque, Protocol

from app.timeutil import wall_now


@dataclass(frozen=True, slots=True)
class GuiMessage:
    title: str
    message: str
    urgent: bool
    created_at: datetime


class GuiMessageSink(Protocol):
    def push(self, title: str, message: str, *, urgent: bool = False) -> None: ...


class QueueGuiSink:
    """Thread-safe-enough deque sink for GUI polling."""

    name = "gui"

    def __init__(self, maxlen: int = 200) -> None:
        self._q: Deque[GuiMessage] = deque(maxlen=maxlen)
        self._listeners: list[Callable[[GuiMessage], None]] = []

    def add_listener(self, callback: Callable[[GuiMessage], None]) -> None:
        self._listeners.append(callback)

    def push(self, title: str, message: str, *, urgent: bool = False) -> None:
        msg = GuiMessage(
            title=title,
            message=message,
            urgent=urgent,
            created_at=wall_now(),
        )
        self._q.append(msg)
        for cb in self._listeners:
            try:
                cb(msg)
            except Exception:  # noqa: BLE001
                pass

    def drain(self) -> list[GuiMessage]:
        items = list(self._q)
        self._q.clear()
        return items

    def peek(self) -> list[GuiMessage]:
        return list(self._q)

    # Notifier-compatible
    def send(self, title: str, message: str, *, urgent: bool = False) -> bool:
        self.push(title, message, urgent=urgent)
        return True


class RecordingGuiSink(QueueGuiSink):
    """Alias used in tests."""

    name = "gui_recording"
