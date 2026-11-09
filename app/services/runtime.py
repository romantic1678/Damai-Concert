"""Runtime coordinator: reminders, monitor polls, pause/resume, safe errors."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Sequence

from app.errors import AppError, MonitorFetchError, ValidationError
from app.logging_config import get_logger
from app.models import ConcertTask, dt_to_iso
from app.notify.base import NotifierService
from app.scheduler.jobs import SchedulerService
from app.services.countdown import DEFAULT_REMINDER_OFFSETS, CountdownService
from app.services.monitor import MonitorService
from app.services.task_service import TaskService
from app.storage.database import Database
from app.timeutil import ensure_aware, wall_now

logger = get_logger("services.runtime")

Clock = Callable[[], datetime]


def reminder_job_id(task_id: int, offset_seconds: int) -> str:
    return f"remind:{task_id}:{offset_seconds}"


def monitor_job_id(task_id: int) -> str:
    return f"monitor:{task_id}"


class TaskRuntime:
    """Wires countdown reminders + polite status monitoring for concert tasks."""

    def __init__(
        self,
        *,
        database: Database,
        task_service: TaskService,
        countdown: CountdownService,
        monitor: MonitorService,
        scheduler: SchedulerService,
        notifier: NotifierService,
        reminder_offsets: Sequence[int] = DEFAULT_REMINDER_OFFSETS,
        clock: Clock | None = None,
    ) -> None:
        self._db = database
        self._tasks = task_service
        self._countdown = countdown
        self._monitor = monitor
        self._scheduler = scheduler
        self._notifier = notifier
        self._offsets = tuple(sorted(set(reminder_offsets), reverse=True))
        self._clock = clock or wall_now

    # --- reminder persistence ---
    def _record_job(
        self,
        task_id: int,
        job_id: str,
        kind: str,
        *,
        run_at: datetime | None = None,
        interval_seconds: int | None = None,
        status: str = "scheduled",
    ) -> None:
        now = ensure_aware(self._clock())
        existing = self._db.fetchone(
            "SELECT id, status FROM reminder_jobs WHERE scheduler_job_id = ?",
            (job_id,),
        )
        if existing:
            self._db.execute(
                """
                UPDATE reminder_jobs
                SET status = ?, run_at = ?, interval_seconds = ?
                WHERE scheduler_job_id = ?
                """,
                (status, dt_to_iso(run_at), interval_seconds, job_id),
            )
            return
        self._db.execute(
            """
            INSERT INTO reminder_jobs (
              task_id, scheduler_job_id, kind, run_at, interval_seconds, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                job_id,
                kind,
                dt_to_iso(run_at),
                interval_seconds,
                status,
                dt_to_iso(now),
            ),
        )

    def _mark_job(self, job_id: str, status: str) -> None:
        self._db.execute(
            "UPDATE reminder_jobs SET status = ? WHERE scheduler_job_id = ?",
            (status, job_id),
        )

    def _job_status(self, job_id: str) -> str | None:
        row = self._db.fetchone(
            "SELECT status FROM reminder_jobs WHERE scheduler_job_id = ?",
            (job_id,),
        )
        return str(row["status"]) if row else None

    def fire_reminder(self, task_id: int, offset_seconds: int) -> bool:
        """Idempotent reminder handler. Returns True if a new notification was sent."""
        job_id = reminder_job_id(task_id, offset_seconds)
        try:
            status = self._job_status(job_id)
            if status == "done":
                logger.info("skip duplicate reminder %s", job_id)
                return False
            if status == "cancelled":
                return False

            task = self._tasks.require(task_id)
            if task.status == "paused":
                logger.info("task %s paused — skip reminder %s", task_id, job_id)
                return False

            snap = None
            if task.open_sale_at is not None:
                snap = self._countdown.snapshot_task(task)

            if offset_seconds == 0:
                kind = "sale_due"
                title = "开售时间到"
                msg = f"「{task.name}」已到开售时间，请自行打开官方页面购票（本程序不会自动下单）。"
            elif offset_seconds == 60:
                kind = "sale_t_minus_1m"
                title = "开售前 1 分钟"
                msg = f"「{task.name}」将在约 1 分钟后开售。"
            elif offset_seconds == 600:
                kind = "sale_t_minus_10m"
                title = "开售前 10 分钟"
                msg = f"「{task.name}」将在约 10 分钟后开售。"
            else:
                kind = f"sale_t_minus_{offset_seconds}s"
                title = f"开售前提醒 (-{offset_seconds}s)"
                msg = f"「{task.name}」开售提醒。"

            if snap is not None:
                msg += f" remaining={snap.remaining_seconds:.1f}s"

            self._notifier.notify(
                title,
                msg,
                kind=kind,
                task_id=task_id,
                urgent=(offset_seconds <= 60),
            )
            self._mark_job(job_id, "done")
            return True
        except AppError as exc:
            logger.error("reminder failed task=%s: %s", task_id, exc.user_message)
            self._safe_pause_on_error(task_id, exc.user_message)
            return False
        except Exception:  # noqa: BLE001
            logger.exception("reminder crashed task=%s", task_id)
            self._safe_pause_on_error(task_id, "reminder crashed")
            return False

    def fire_monitor_poll(self, task_id: int) -> None:
        try:
            task = self._tasks.require(task_id)
            if task.status == "paused" or not task.monitor_enabled:
                return
            diff = self._monitor.poll_once(task_id)
            if diff.should_notify:
                prev = diff.previous.normalized_status if diff.previous else "?"
                self._notifier.notify(
                    "公开销售状态变化",
                    f"「{task.name}」{prev} → {diff.current.normalized_status}",
                    kind="status_change",
                    task_id=task_id,
                    urgent=True,
                )
        except AppError as exc:
            logger.error("monitor poll failed task=%s: %s", task_id, exc.user_message)
            # Fetch failures already map to unknown inside MonitorService;
            # persistent app errors pause scheduling for safety.
            if not isinstance(exc, MonitorFetchError):
                self._safe_pause_on_error(task_id, exc.user_message)
        except Exception:  # noqa: BLE001
            logger.exception("monitor poll crashed task=%s", task_id)
            self._safe_pause_on_error(task_id, "monitor crashed")

    def _safe_pause_on_error(self, task_id: int, reason: str) -> None:
        try:
            self.pause_task(task_id, note=f"auto-paused: {reason}")
            self._notifier.notify(
                "任务已安全暂停",
                f"task {task_id}: {reason}",
                kind="task_paused_error",
                task_id=task_id,
                urgent=True,
            )
        except Exception:  # noqa: BLE001
            logger.exception("failed to safe-pause task=%s", task_id)

    def schedule_task_reminders(self, task_id: int) -> int:
        """Schedule future T-10 / T-1 / T-0 reminders. Returns number scheduled."""
        task = self._tasks.require(task_id)
        if task.open_sale_at is None:
            raise ValidationError("open_sale_at required to schedule reminders")
        now = ensure_aware(self._clock())
        scheduled = 0
        for offset in self._offsets:
            job_id = reminder_job_id(task_id, offset)
            fire_at = self._countdown.reminder_fire_at(task.open_sale_at, offset)
            fire_at = ensure_aware(fire_at)
            if fire_at <= now:
                # Past fire time: skip scheduling (do not retro-spam)
                self._record_job(
                    task_id,
                    job_id,
                    "countdown_offset" if offset else "sale_due",
                    run_at=fire_at,
                    status="cancelled",
                )
                continue
            if self._job_status(job_id) == "done":
                continue
            self._record_job(
                task_id,
                job_id,
                "countdown_offset" if offset else "sale_due",
                run_at=fire_at,
                status="scheduled",
            )
            self._scheduler.add_date_job(
                job_id,
                fire_at,
                self.fire_reminder,
                task_id=task_id,
                offset_seconds=offset,
            )
            scheduled += 1
        return scheduled

    def schedule_task_monitor(self, task_id: int) -> None:
        task = self._tasks.require(task_id)
        if not task.monitor_enabled:
            return
        interval = self._monitor.min_poll_interval_seconds()
        job_id = monitor_job_id(task_id)
        self._record_job(
            task_id,
            job_id,
            "monitor_interval",
            interval_seconds=interval,
            status="scheduled",
        )
        # Establish baseline immediately without notify
        try:
            if self._monitor._latest_snapshot(task_id) is None:  # noqa: SLF001
                self._monitor.establish_baseline(task_id)
        except Exception:  # noqa: BLE001
            logger.exception("baseline failed task=%s", task_id)
        self._scheduler.add_interval_job(
            job_id,
            interval,
            self.fire_monitor_poll,
            task_id=task_id,
        )

    def unschedule_task(self, task_id: int) -> None:
        for offset in self._offsets:
            jid = reminder_job_id(task_id, offset)
            self._scheduler.remove_job(jid)
            if self._job_status(jid) == "scheduled":
                self._mark_job(jid, "cancelled")
        mid = monitor_job_id(task_id)
        self._scheduler.remove_job(mid)
        if self._job_status(mid) == "scheduled":
            self._mark_job(mid, "cancelled")

    def pause_task(self, task_id: int, *, note: str | None = None) -> ConcertTask:
        fields: dict = {"status": "paused", "monitor_enabled": False}
        if note:
            fields["note"] = note
        task = self._tasks.update(task_id, **fields)
        self.unschedule_task(task_id)
        logger.info("paused task %s", task_id)
        return task

    def resume_task(self, task_id: int, *, enable_monitor: bool = False) -> ConcertTask:
        task = self._tasks.update(
            task_id,
            status="watching",
            monitor_enabled=enable_monitor,
        )
        if task.open_sale_at is not None:
            self.schedule_task_reminders(task_id)
        if enable_monitor:
            self.schedule_task_monitor(task_id)
        logger.info("resumed task %s monitor=%s", task_id, enable_monitor)
        return task

    def arm_all_watching(self) -> None:
        for task in self._tasks.list_all():
            if task.id is None or task.status in {"paused", "cancelled", "done"}:
                continue
            if task.open_sale_at is not None:
                try:
                    self.schedule_task_reminders(task.id)
                except AppError as exc:
                    logger.warning("arm reminders task=%s: %s", task.id, exc.user_message)
            if task.monitor_enabled:
                try:
                    self.schedule_task_monitor(task.id)
                except AppError as exc:
                    logger.warning("arm monitor task=%s: %s", task.id, exc.user_message)
