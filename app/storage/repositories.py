"""Repository layer for concert tasks."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Sequence

from app.errors import NotFoundError, StorageError, ValidationError
from app.models import (
    ConcertTask,
    SortDir,
    SortField,
    date_to_iso,
    dt_to_iso,
    parse_date,
    parse_datetime,
    validate_task_status,
)
from app.storage.database import Database

_CST = timezone(timedelta(hours=8))

_SORT_COLUMNS: dict[str, str] = {
    "open_sale_at": "open_sale_at",
    "created_at": "created_at",
    "name": "name COLLATE NOCASE",
    "city": "city COLLATE NOCASE",
    "status": "status COLLATE NOCASE",
    "show_date": "show_date",
    "id": "id",
}


def _now() -> datetime:
    return datetime.now(_CST)


def _row_to_task(row: Any) -> ConcertTask:
    keys = set(row.keys())
    return ConcertTask(
        id=int(row["id"]),
        name=str(row["name"]),
        artist_name=row["artist_name"] if "artist_name" in keys else None,
        city=row["city"],
        official_url=row["official_url"],
        show_date=parse_date(row["show_date"]) if "show_date" in keys else None,
        session_name=row["session_name"] if "session_name" in keys else None,
        target_price=(
            float(row["target_price"])
            if "target_price" in keys and row["target_price"] is not None
            else None
        ),
        target_tier=row["target_tier"] if "target_tier" in keys else None,
        ticket_quantity=(
            int(row["ticket_quantity"])
            if "ticket_quantity" in keys and row["ticket_quantity"] is not None
            else None
        ),
        open_sale_at=parse_datetime(row["open_sale_at"]),
        status=validate_task_status(row["status"] if "status" in keys else "pending"),
        monitor_enabled=bool(row["monitor_enabled"]),
        note=row["note"],
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


class TaskRepository:
    """CRUD + search/sort for concert_tasks table."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def create(self, task: ConcertTask) -> ConcertTask:
        now = _now()
        created = task.created_at or now
        updated = task.updated_at or now
        cur = self._db.execute(
            """
            INSERT INTO concert_tasks (
              name, artist_name, city, official_url, show_date, session_name,
              target_price, target_tier, ticket_quantity, open_sale_at,
              status, monitor_enabled, note, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.name,
                task.artist_name,
                task.city,
                task.official_url,
                date_to_iso(task.show_date),
                task.session_name,
                task.target_price,
                task.target_tier,
                task.ticket_quantity,
                dt_to_iso(task.open_sale_at),
                task.status,
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

    def count(self) -> int:
        row = self._db.fetchone("SELECT COUNT(*) AS c FROM concert_tasks")
        return int(row["c"]) if row else 0

    def search(
        self,
        *,
        query: str | None = None,
        status: str | None = None,
        sort_by: SortField = "id",
        sort_dir: SortDir = "asc",
        limit: int | None = None,
        offset: int = 0,
    ) -> Sequence[ConcertTask]:
        if sort_by not in _SORT_COLUMNS:
            raise ValidationError(f"unsupported sort_by: {sort_by}")
        direction = "ASC" if sort_dir.lower() == "asc" else "DESC"
        order_expr = _SORT_COLUMNS[sort_by]

        clauses: list[str] = []
        params: list[Any] = []

        if query and query.strip():
            like = f"%{query.strip()}%"
            clauses.append(
                "("
                "name LIKE ? COLLATE NOCASE OR "
                "IFNULL(artist_name,'') LIKE ? COLLATE NOCASE OR "
                "IFNULL(city,'') LIKE ? COLLATE NOCASE OR "
                "IFNULL(status,'') LIKE ? COLLATE NOCASE OR "
                "IFNULL(session_name,'') LIKE ? COLLATE NOCASE OR "
                "IFNULL(target_tier,'') LIKE ? COLLATE NOCASE"
                ")"
            )
            params.extend([like, like, like, like, like, like])

        if status and status.strip():
            clauses.append("status = ?")
            params.append(validate_task_status(status))

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM concert_tasks {where} ORDER BY {order_expr} {direction}, id ASC"
        if limit is not None:
            if limit < 0 or offset < 0:
                raise ValidationError("limit/offset must be >= 0")
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        rows = self._db.fetchall(sql, tuple(params))
        return [_row_to_task(r) for r in rows]

    def update(self, task_id: int, **fields: Any) -> ConcertTask:
        allowed = {
            "name",
            "artist_name",
            "city",
            "official_url",
            "show_date",
            "session_name",
            "target_price",
            "target_tier",
            "ticket_quantity",
            "open_sale_at",
            "status",
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
        artist_name = fields.get("artist_name", current.artist_name)
        city = fields.get("city", current.city)
        official_url = fields.get("official_url", current.official_url)
        show_date = fields.get("show_date", current.show_date)
        if isinstance(show_date, str):
            show_date = parse_date(show_date)
        session_name = fields.get("session_name", current.session_name)
        target_price = fields.get("target_price", current.target_price)
        target_tier = fields.get("target_tier", current.target_tier)
        ticket_quantity = fields.get("ticket_quantity", current.ticket_quantity)
        open_sale_at = fields.get("open_sale_at", current.open_sale_at)
        if isinstance(open_sale_at, str):
            open_sale_at = parse_datetime(open_sale_at)
        status = fields.get("status", current.status)
        if isinstance(status, str):
            status = validate_task_status(status)
        monitor_enabled = fields.get("monitor_enabled", current.monitor_enabled)
        note = fields.get("note", current.note)
        updated_at = _now()

        self._db.execute(
            """
            UPDATE concert_tasks SET
              name = ?, artist_name = ?, city = ?, official_url = ?,
              show_date = ?, session_name = ?, target_price = ?, target_tier = ?,
              ticket_quantity = ?, open_sale_at = ?, status = ?,
              monitor_enabled = ?, note = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                name,
                artist_name,
                city,
                official_url,
                date_to_iso(show_date),
                session_name,
                target_price,
                target_tier,
                ticket_quantity,
                dt_to_iso(open_sale_at),
                status,
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
