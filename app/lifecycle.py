"""Application start / stop lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings, load_settings
from app.logging_config import get_logger, setup_logging
from app.services.task_service import TaskService
from app.storage.database import Database
from app.storage.repositories import TaskRepository


@dataclass
class Application:
    """Owns config, logging, database, and core services."""

    settings: Settings
    database: Database
    task_service: TaskService
    _started: bool = field(default=False, init=False, repr=False)

    @classmethod
    def create(
        cls,
        settings_path: Path | None = None,
        *,
        database_path: Path | None = None,
        ensure_settings: bool = True,
    ) -> Application:
        settings = load_settings(settings_path, ensure_exists=ensure_settings)
        setup_logging(settings)
        logger = get_logger("lifecycle")
        db_path = database_path or settings.database_path
        database = Database(db_path)
        database.connect()
        database.migrate()
        repo = TaskRepository(database)
        task_service = TaskService(repo, settings)
        app = cls(settings=settings, database=database, task_service=task_service)
        app._started = True
        logger.info(
            "application started mode=%s db=%s",
            settings.app.mode,
            db_path,
        )
        return app

    def shutdown(self) -> None:
        if not self._started:
            return
        logger = get_logger("lifecycle")
        self.database.close()
        self._started = False
        logger.info("application shutdown complete")

    def __enter__(self) -> Application:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self.shutdown()
