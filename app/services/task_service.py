"""Concert task management service (CRUD against SQLite)."""

from __future__ import annotations

from typing import Any, Sequence

from app.config import Settings
from app.errors import NotFoundError, ValidationError
from app.logging_config import get_logger
from app.models import ConcertTask, validate_official_url
from app.storage.repositories import TaskRepository

logger = get_logger("services.tasks")


class TaskService:
    """Application-facing task API with validation."""

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
        logger.info("created task id=%s name=%s", saved.id, saved.name)
        return saved

    def update(self, task_id: int, **fields: Any) -> ConcertTask:
        if "official_url" in fields:
            fields["official_url"] = validate_official_url(
                fields["official_url"],
                self._settings.url_allowlist,
            )
        if "name" in fields and (not fields["name"] or not str(fields["name"]).strip()):
            raise ValidationError("task name is required")
        if "name" in fields:
            fields["name"] = str(fields["name"]).strip()
        saved = self._repo.update(task_id, **fields)
        logger.info("updated task id=%s fields=%s", task_id, sorted(fields))
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

    def set_monitor(self, task_id: int, enabled: bool) -> ConcertTask:
        task = self.require(task_id)
        if enabled and not task.official_url and not task.open_sale_at:
            raise ValidationError(
                "cannot enable monitor without official_url or open_sale_at"
            )
        return self._repo.set_monitor(task_id, enabled)
