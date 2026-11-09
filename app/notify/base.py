"""Notifier protocols and fan-out service with dedupe."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, Sequence

from app.logging_config import get_logger
from app.notify.dedupe import NotificationDedupeStore
from app.storage.database import Database
from app.timeutil import wall_now

logger = get_logger("notify")


@dataclass(frozen=True, slots=True)
class NotificationEvent:
    kind: str
    title: str
    message: str
    task_id: int | None = None
    urgent: bool = False
    dedupe_key: str | None = None
    delivered: bool = True
    created_at: datetime = field(default_factory=wall_now)


class Notifier(Protocol):
    name: str

    def send(self, title: str, message: str, *, urgent: bool = False) -> bool: ...


class NotifierService:
    """Fan-out to channels; persists dedupe keys; never raises to callers."""

    def __init__(
        self,
        *,
        database: Database | None = None,
        dedupe: NotificationDedupeStore | None = None,
    ) -> None:
        self._notifiers: list[Notifier] = []
        self.events: list[NotificationEvent] = []
        self._db = database
        self._dedupe = dedupe
        if dedupe is None and database is not None:
            self._dedupe = NotificationDedupeStore(database)

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
        dedupe_key: str | None = None,
        force: bool = False,
    ) -> NotificationEvent:
        """Send notification. Returns event; delivered=False if deduped or all channels failed softly."""
        key = dedupe_key or f"{kind}:{task_id}:{title}:{message}"
        try:
            if not force and self._dedupe is not None:
                if self._dedupe.already_sent(key):
                    logger.info("dedupe skip kind=%s key=%s", kind, key)
                    event = NotificationEvent(
                        kind=kind,
                        title=title,
                        message=message,
                        task_id=task_id,
                        urgent=urgent,
                        dedupe_key=key,
                        delivered=False,
                    )
                    self.events.append(event)
                    return event

            any_ok = False
            for notifier in self._notifiers:
                try:
                    ok = notifier.send(title, message, urgent=urgent)
                    any_ok = any_ok or bool(ok)
                except Exception:  # noqa: BLE001 — never crash main app
                    logger.exception(
                        "notifier %s failed kind=%s",
                        getattr(notifier, "name", "?"),
                        kind,
                    )

            if self._dedupe is not None and not force:
                try:
                    self._dedupe.mark_sent(key, kind=kind, task_id=task_id)
                except Exception:  # noqa: BLE001
                    logger.exception("dedupe mark failed key=%s", key)

            if self._db is not None:
                try:
                    self._db.execute(
                        """
                        INSERT INTO notification_logs (
                          task_id, channel, title, body, success, error_message, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            task_id,
                            "fanout",
                            title,
                            message,
                            1 if any_ok else 0,
                            None if any_ok else "all channels soft-failed",
                            wall_now().isoformat(),
                        ),
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("notification_logs insert failed")

            event = NotificationEvent(
                kind=kind,
                title=title,
                message=message,
                task_id=task_id,
                urgent=urgent,
                dedupe_key=key,
                delivered=True,
            )
            self.events.append(event)
            return event
        except Exception:  # noqa: BLE001 — absolute isolation
            logger.exception("notify() crashed; swallowing")
            event = NotificationEvent(
                kind=kind,
                title=title,
                message=message,
                task_id=task_id,
                urgent=urgent,
                dedupe_key=key,
                delivered=False,
            )
            self.events.append(event)
            return event

    def of_kind(self, kind: str) -> Sequence[NotificationEvent]:
        return [e for e in self.events if e.kind == kind]

    def delivered_of_kind(self, kind: str) -> Sequence[NotificationEvent]:
        return [e for e in self.events if e.kind == kind and e.delivered]
