"""Browser connection status for GUI / observers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable

from app.timeutil import wall_now


class BrowserConnectionStatus(str, Enum):
    DISCONNECTED = "disconnected"
    LAUNCHING = "launching"
    CONNECTED = "connected"
    NAVIGATING = "navigating"
    PAGE_READY = "page_ready"
    PAGE_ERROR = "page_error"
    HUMAN_TAKEOVER = "human_takeover"
    PAUSED = "paused"
    CLOSING = "closing"


StatusListener = Callable[["BrowserStatusEvent"], None]


@dataclass(frozen=True, slots=True)
class BrowserStatusEvent:
    task_id: int | None
    status: BrowserConnectionStatus
    detail: str = ""
    url: str | None = None
    at: datetime = field(default_factory=wall_now)


@dataclass
class StatusHub:
    """Observable connection status for future GUI binding."""

    status: BrowserConnectionStatus = BrowserConnectionStatus.DISCONNECTED
    task_id: int | None = None
    last_url: str | None = None
    last_detail: str = ""
    _listeners: list[StatusListener] = field(default_factory=list, repr=False)

    def add_listener(self, callback: StatusListener) -> None:
        self._listeners.append(callback)

    def set(
        self,
        status: BrowserConnectionStatus,
        *,
        task_id: int | None = None,
        detail: str = "",
        url: str | None = None,
    ) -> BrowserStatusEvent:
        self.status = status
        if task_id is not None:
            self.task_id = task_id
        if url is not None:
            self.last_url = url
        self.last_detail = detail
        event = BrowserStatusEvent(
            task_id=self.task_id,
            status=status,
            detail=detail,
            url=url if url is not None else self.last_url,
        )
        for cb in list(self._listeners):
            try:
                cb(event)
            except Exception:  # noqa: BLE001
                pass
        return event
