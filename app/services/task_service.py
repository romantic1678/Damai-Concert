"""Concert task management service (CRUD against SQLite)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Sequence

from app.config import Settings
from app.errors import NotFoundError, ValidationError
from app.logging_config import get_logger
from app.models import (
    ConcertTask,
    SortDir,
    SortField,
    parse_date,
    parse_datetime,
    validate_official_url,
    validate_target_price,
    validate_task_status,
    validate_ticket_quantity,
)
from app.storage.repositories import TaskRepository

logger = get_logger("services.tasks")


class TaskService:
    """Application-facing task API with validation, search, and sort."""

    def __init__(self, repo: TaskRepository, settings: Settings) -> None:
        self._repo = repo
        self._settings = settings

    def create(self, task: ConcertTask) -> ConcertTask:
        task.validate(self._settings.url_allowlist)
        if task.monitor_enabled and not task.official_url and not task.open_sale_at:
            raise ValidationError(
                "monitor_enabled requires official_url and/or open_sale_at"
            )
        saved = self._repo.create(task)
        logger.info("created task id=%s name=%s status=%s", saved.id, saved.name, saved.status)
        return saved

    def _normalize_update_fields(self, fields: dict[str, Any]) -> dict[str, Any]:
        out = dict(fields)
        if "official_url" in out:
            out["official_url"] = validate_official_url(
                out["official_url"],
                self._settings.url_allowlist,
            )
        if "name" in out:
            if not out["name"] or not str(out["name"]).strip():
                raise ValidationError("task name is required")
            out["name"] = str(out["name"]).strip()
        if "artist_name" in out and out["artist_name"] is not None:
            out["artist_name"] = str(out["artist_name"]).strip() or None
        if "city" in out and out["city"] is not None:
            out["city"] = str(out["city"]).strip() or None
        if "session_name" in out and out["session_name"] is not None:
            out["session_name"] = str(out["session_name"]).strip() or None
        if "target_tier" in out and out["target_tier"] is not None:
            out["target_tier"] = str(out["target_tier"]).strip() or None
        if "show_date" in out:
            out["show_date"] = parse_date(out["show_date"])
        if "open_sale_at" in out:
            out["open_sale_at"] = parse_datetime(out["open_sale_at"])
        if "target_price" in out:
            out["target_price"] = validate_target_price(out["target_price"])
        if "ticket_quantity" in out:
            out["ticket_quantity"] = validate_ticket_quantity(out["ticket_quantity"])
        if "status" in out:
            out["status"] = validate_task_status(out["status"])
        return out

    def update(self, task_id: int, **fields: Any) -> ConcertTask:
        normalized = self._normalize_update_fields(fields)
        saved = self._repo.update(task_id, **normalized)
        logger.info("updated task id=%s fields=%s", task_id, sorted(normalized))
        return saved

    def delete(self, task_id: int) -> None:
        self._repo.delete(task_id)
        logger.info("deleted task id=%s", task_id)

    def get(self, task_id: int) -> ConcertTask | None:
        return self._repo.get(task_id)

    def require(self, task_id: int) -> ConcertTask:
        task = self.get(task_id)
        if task is None:
            raise NotFoundError(f"task {task_id} not found")
        return task

    def list_all(self) -> Sequence[ConcertTask]:
        return self._repo.list_all()

    def count(self) -> int:
        return self._repo.count()

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
        return self._repo.search(
            query=query,
            status=status,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )

    def set_monitor(self, task_id: int, enabled: bool) -> ConcertTask:
        task = self.require(task_id)
        if enabled and not task.official_url and not task.open_sale_at:
            raise ValidationError(
                "cannot enable monitor without official_url or open_sale_at"
            )
        updated = self._repo.set_monitor(task_id, enabled)
        # When enabling monitor, promote pending -> watching if still pending
        if enabled and updated.status == "pending":
            updated = self.update(task_id, status="watching")
        return updated

    def set_status(self, task_id: int, status: str) -> ConcertTask:
        return self.update(task_id, status=status)
