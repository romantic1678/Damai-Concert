"""Notifier protocols and fan-out service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, Sequence

from app.logging_config import get_logger
from app.timeutil import wall_now

logger = get_logger("notify")


@dataclass(frozen=True, slots=True)
class NotificationEvent:
    kind: str
    title: str
    message: str
    task_id: int | None = None
    urgent: bool = False
    created_at: datetime = field(default_factory=wall_now)


class Notifier(Protocol):
    name: str

    def send(self, title: str, message: str, *, urgent: bool = False) -> bool: ...


class NotifierService:
    """Fan-out to registered notifiers; records successes for auditing in-memory."""

    def __init__(self) -> None:
        self._notifiers: list[Notifier] = []
        self.events: list[NotificationEvent] = []

    def register(self, notifier: Notifier) -> None:
        self._notifiers.append(notifier)

    def notify(
        self,
        title: str,
        message: str,
        *,
        kind: str = "generic",
        task_id: int | None = None,
        urgent: bool = False,
    ) -> NotificationEvent:
        event = NotificationEvent(
            kind=kind,
            title=title,
            message=message,
            task_id=task_id,
            urgent=urgent,
        )
        self.events.append(event)
        for notifier in self._notifiers:
            try:
                ok = notifier.send(title, message, urgent=urgent)
                if not ok:
                    logger.warning("notifier %s returned False", getattr(notifier, "name", "?"))
            except Exception:  # noqa: BLE001 — never crash caller
                logger.exception("notifier %s failed", getattr(notifier, "name", "?"))
        return event

    def of_kind(self, kind: str) -> Sequence[NotificationEvent]:
        return [e for e in self.events if e.kind == kind]
