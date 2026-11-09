"""Repository layer for concert tasks."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Sequence

from app.errors import NotFoundError, StorageError, ValidationError
from app.models import ConcertTask, dt_to_iso, parse_datetime
from app.storage.database import Database

_CST = timezone(timedelta(hours=8))


def _now() -> datetime:
    return datetime.now(_CST)


def _row_to_task(row: Any) -> ConcertTask:
    return ConcertTask(
        id=int(row["id"]),
        name=str(row["name"]),
        city=row["city"],
        official_url=row["official_url"],
        open_sale_at=parse_datetime(row["open_sale_at"]),
        monitor_enabled=bool(row["monitor_enabled"]),
        note=row["note"],
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


class TaskRepository:
    """CRUD for concert_tasks table."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def create(self, task: ConcertTask) -> ConcertTask:
        now = _now()
        created = task.created_at or now
        updated = task.updated_at or now
        cur = self._db.execute(
            """
            INSERT INTO concert_tasks (
              name, city, official_url, open_sale_at, monitor_enabled, note,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.name,
                task.city,
                task.official_url,
                dt_to_iso(task.open_sale_at),
                1 if task.monitor_enabled else 0,
                task.note,
                dt_to_iso(created),
                dt_to_iso(updated),
            ),
        )
        task_id = int(cur.lastrowid)
        saved = self.get(task_id)
        if saved is None:
            raise StorageError("failed to read task after insert")
        return saved

    def get(self, task_id: int) -> ConcertTask | None:
        row = self._db.fetchone(
            "SELECT * FROM concert_tasks WHERE id = ?",
            (task_id,),
        )
        return _row_to_task(row) if row else None

    def list_all(self) -> Sequence[ConcertTask]:
        rows = self._db.fetchall("SELECT * FROM concert_tasks ORDER BY id ASC")
        return [_row_to_task(r) for r in rows]

    def update(self, task_id: int, **fields: Any) -> ConcertTask:
        allowed = {
            "name",
            "city",
            "official_url",
            "open_sale_at",
            "monitor_enabled",
            "note",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValidationError(f"unknown fields: {sorted(unknown)}")
        if not fields:
            raise ValidationError("no fields to update")

        current = self.get(task_id)
        if current is None:
            raise NotFoundError(f"task {task_id} not found")

        name = fields.get("name", current.name)
        city = fields.get("city", current.city)
        official_url = fields.get("official_url", current.official_url)
        open_sale_at = fields.get("open_sale_at", current.open_sale_at)
        if isinstance(open_sale_at, str):
            open_sale_at = parse_datetime(open_sale_at)
        monitor_enabled = fields.get("monitor_enabled", current.monitor_enabled)
        note = fields.get("note", current.note)
        updated_at = _now()

        self._db.execute(
            """
            UPDATE concert_tasks SET
              name = ?, city = ?, official_url = ?, open_sale_at = ?,
              monitor_enabled = ?, note = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                name,
                city,
                official_url,
                dt_to_iso(open_sale_at),
                1 if monitor_enabled else 0,
                note,
                dt_to_iso(updated_at),
                task_id,
            ),
        )
        saved = self.get(task_id)
        if saved is None:
            raise StorageError("task missing after update")
        return saved

    def delete(self, task_id: int) -> None:
        cur = self._db.execute("DELETE FROM concert_tasks WHERE id = ?", (task_id,))
        if cur.rowcount == 0:
            raise NotFoundError(f"task {task_id} not found")

    def set_monitor(self, task_id: int, enabled: bool) -> ConcertTask:
        return self.update(task_id, monitor_enabled=enabled)
