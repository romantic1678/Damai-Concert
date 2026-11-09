"""APScheduler BackgroundScheduler wrapper."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import STATE_RUNNING

from app.errors import ScheduleError
from app.logging_config import get_logger
from app.timeutil import ensure_aware

logger = get_logger("scheduler")

JobFunc = Callable[..., Any]


class SchedulerService:
    def __init__(self, *, timezone: str = "Asia/Shanghai") -> None:
        self._timezone = timezone
        self._scheduler = BackgroundScheduler(timezone=timezone)
        # Never let job exceptions kill the process
        from apscheduler.events import EVENT_JOB_ERROR

        self._scheduler.add_listener(self._on_event, EVENT_JOB_ERROR)

    def _on_event(self, event: object) -> None:
        # Import lazily to avoid hard dep on event types in tests
        try:
            from apscheduler.events import EVENT_JOB_ERROR, JobExecutionEvent

            if getattr(event, "code", None) == EVENT_JOB_ERROR and isinstance(
                event, JobExecutionEvent
            ):
                logger.error(
                    "job error id=%s exc=%s",
                    event.job_id,
                    event.exception,
                    exc_info=event.exception,
                )
        except Exception:  # noqa: BLE001
            logger.exception("scheduler listener failure")

    @property
    def running(self) -> bool:
        return self._scheduler.state == STATE_RUNNING

    def start(self) -> None:
        if not self.running:
            self._scheduler.start()
            logger.info("scheduler started tz=%s", self._timezone)

    def shutdown(self, wait: bool = True) -> None:
        if self._scheduler.state != 0:  # STATE_STOPPED == 0
            self._scheduler.shutdown(wait=wait)
            logger.info("scheduler shutdown")

    def add_date_job(
        self,
        job_id: str,
        run_at: datetime,
        func: JobFunc,
        **kwargs: Any,
    ) -> None:
        when = ensure_aware(run_at, default_tz=self._timezone)
        try:
            self._scheduler.add_job(
                func,
                trigger="date",
                run_date=when,
                id=job_id,
                replace_existing=True,
                misfire_grace_time=300,
                coalesce=True,
                kwargs=kwargs,
            )
        except Exception as exc:  # noqa: BLE001
            raise ScheduleError(f"failed to add date job {job_id}: {exc}") from exc

    def add_interval_job(
        self,
        job_id: str,
        seconds: int,
        func: JobFunc,
        **kwargs: Any,
    ) -> None:
        if seconds < 60:
            raise ScheduleError("interval seconds must be >= 60")
        try:
            self._scheduler.add_job(
                func,
                trigger="interval",
                seconds=seconds,
                id=job_id,
                replace_existing=True,
                coalesce=True,
                max_instances=1,
                kwargs=kwargs,
            )
        except Exception as exc:  # noqa: BLE001
            raise ScheduleError(f"failed to add interval job {job_id}: {exc}") from exc

    def remove_job(self, job_id: str) -> None:
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            logger.debug("remove_job missing id=%s", job_id)

    def pause_job(self, job_id: str) -> None:
        try:
            self._scheduler.pause_job(job_id)
        except Exception:
            logger.debug("pause_job missing id=%s", job_id)

    def resume_job(self, job_id: str) -> None:
        try:
            self._scheduler.resume_job(job_id)
        except Exception:
            logger.debug("resume_job missing id=%s", job_id)

    def get_job_ids(self) -> list[str]:
        return [j.id for j in self._scheduler.get_jobs()]
