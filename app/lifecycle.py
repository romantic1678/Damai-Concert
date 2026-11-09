"""Application start / stop lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.browser.assist import BrowserAssist
from app.browser.status import StatusHub
from app.browser.takeover import HumanTakeoverService
from app.config import Settings, load_settings
from app.paths import ensure_playwright_env
from app.logging_config import get_logger, setup_logging
from app.notify.base import NotifierService
from app.notify.factory import build_notifier_service
from app.notify.gui_sink import QueueGuiSink
from app.scheduler.jobs import SchedulerService
from app.services.countdown import CountdownService
from app.services.monitor import MonitorService, RejectNetworkFetcher
from app.services.runtime import TaskRuntime, minutes_to_offset_seconds
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
    gui_sink: QueueGuiSink
    runtime: TaskRuntime
    browser: BrowserAssist
    browser_status: StatusHub
    takeover: HumanTakeoverService
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
        browser_headless: bool = False,
    ) -> Application:
        ensure_playwright_env()
        settings = load_settings(settings_path, ensure_exists=ensure_settings)
        setup_logging(settings)
        logger = get_logger("lifecycle")
        db_path = database_path or settings.database_path
        database = Database(db_path)
        database.connect()
        database.migrate()
        repo = TaskRepository(database)
        task_service = TaskService(repo, settings)

        if enable_network_fetch:
            fetcher = RejectNetworkFetcher()
            logger.warning(
                "enable_network_fetch requested but live Damai fetch is not implemented; "
                "using RejectNetworkFetcher (status → unknown)"
            )
        else:
            fetcher = RejectNetworkFetcher()

        notifier, gui_sink = build_notifier_service(settings, database)
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
        offsets = minutes_to_offset_seconds(settings.notify.reminder_offsets_minutes)
        runtime = TaskRuntime(
            database=database,
            task_service=task_service,
            countdown=countdown,
            monitor=monitor,
            scheduler=scheduler,
            notifier=notifier,
            reminder_offsets=offsets,
        )
        status_hub = StatusHub()
        takeover = HumanTakeoverService()
        user_data = settings.project_root / "data" / "browser_profile"
        browser = BrowserAssist(
            url_allowlist=settings.url_allowlist,
            notifier=notifier,
            runtime=runtime,
            takeover=takeover,
            status_hub=status_hub,
            user_data_dir=None,  # opt-in later; avoid sharing profiles in tests
            headless=browser_headless,
        )
        app = cls(
            settings=settings,
            database=database,
            task_service=task_service,
            countdown=countdown,
            monitor=monitor,
            scheduler=scheduler,
            notifier=notifier,
            gui_sink=gui_sink,
            runtime=runtime,
            browser=browser,
            browser_status=status_hub,
            takeover=takeover,
        )
        app._started = True
        if start_scheduler:
            scheduler.start()
            runtime.arm_all_watching()
        logger.info(
            "application started mode=%s db=%s scheduler=%s offsets=%s",
            settings.app.mode,
            db_path,
            start_scheduler,
            offsets,
        )
        return app

    def shutdown(self) -> None:
        if not self._started:
            return
        logger = get_logger("lifecycle")
        try:
            self.browser.close()
        except Exception:  # noqa: BLE001
            logger.exception("browser shutdown error")
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
