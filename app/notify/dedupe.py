"""Persistent notification dedupe keys (SQLite)."""

from __future__ import annotations

from app.models import dt_to_iso
from app.storage.database import Database
from app.timeutil import wall_now


class NotificationDedupeStore:
    def __init__(self, database: Database) -> None:
        self._db = database

    def already_sent(self, dedupe_key: str) -> bool:
        row = self._db.fetchone(
            "SELECT 1 AS ok FROM notification_dedupe WHERE dedupe_key = ?",
            (dedupe_key,),
        )
        return row is not None

    def mark_sent(
        self,
        dedupe_key: str,
        *,
        kind: str,
        task_id: int | None = None,
    ) -> bool:
        """Insert key. Returns True if newly inserted, False if duplicate."""
        if self.already_sent(dedupe_key):
            return False
        self._db.execute(
            """
            INSERT INTO notification_dedupe (dedupe_key, kind, task_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (dedupe_key, kind, task_id, dt_to_iso(wall_now())),
        )
        return True
