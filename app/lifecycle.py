"""Application start / stop lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings, load_settings
from app.logging_config import get_logger, setup_logging
from app.notify.base import NotifierService
from app.notify.console import ConsoleNotifier
from app.scheduler.jobs import SchedulerService
from app.services.countdown import CountdownService
from app.services.monitor import FixtureStatusFetcher, MonitorService, RejectNetworkFetcher
from app.services.runtime import TaskRuntime
from app.services.task_service import TaskService
from app.storage.database import Database
from app.storage.repositories import TaskRepository


@dataclass
class Application:
    """Owns config, logging, database, and core services."""

    settings: Settings
    database: Database
    task_service: TaskService
    countdown: CountdownService
    monitor: MonitorService
    scheduler: SchedulerService
    notifier: NotifierService
    runtime: TaskRuntime
    _started: bool = field(default=False, init=False, repr=False)

    @classmethod
    def create(
        cls,
        settings_path: Path | None = None,
        *,
        database_path: Path | None = None,
        ensure_settings: bool = True,
        enable_network_fetch: bool = False,
        start_scheduler: bool = False,
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

        # Default: reject network (monitor/reminder product still works with fixtures/manual).
        fetcher: object
        if enable_network_fetch:
            # Intentionally not implementing a live Damai scraper in phase 6.
            fetcher = RejectNetworkFetcher()
            logger.warning(
                "enable_network_fetch requested but live Damai fetch is not implemented; "
                "using RejectNetworkFetcher (status → unknown)"
            )
        else:
            fetcher = RejectNetworkFetcher()

        notifier = NotifierService()
        notifier.register(ConsoleNotifier())
        countdown = CountdownService(
            task_service,
            timezone=settings.monitor.timezone,
        )
        monitor = MonitorService(
            database,
            task_service,
            fetcher,  # type: ignore[arg-type]
            min_poll_interval_seconds=settings.monitor.poll_interval_seconds,
        )
        scheduler = SchedulerService(timezone=settings.monitor.timezone)
        runtime = TaskRuntime(
            database=database,
            task_service=task_service,
            countdown=countdown,
            monitor=monitor,
            scheduler=scheduler,
            notifier=notifier,
        )
        app = cls(
            settings=settings,
            database=database,
            task_service=task_service,
            countdown=countdown,
            monitor=monitor,
            scheduler=scheduler,
            notifier=notifier,
            runtime=runtime,
        )
        app._started = True
        if start_scheduler:
            scheduler.start()
            runtime.arm_all_watching()
        logger.info(
            "application started mode=%s db=%s scheduler=%s",
            settings.app.mode,
            db_path,
            start_scheduler,
        )
        return app

    def shutdown(self) -> None:
        if not self._started:
            return
        logger = get_logger("lifecycle")
        try:
            self.scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            logger.exception("scheduler shutdown error")
        self.database.close()
        self._started = False
        logger.info("application shutdown complete")

    def __enter__(self) -> Application:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self.shutdown()
