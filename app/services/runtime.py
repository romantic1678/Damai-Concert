"""Runtime coordinator: reminders, monitor polls, pause/resume, safe errors."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Callable, Sequence

from app.errors import AppError, MonitorFetchError, ValidationError
from app.logging_config import get_logger
from app.models import ConcertTask, dt_to_iso
from app.notify.base import NotifierService
from app.notify.kinds import (
    BROWSER_LAUNCH_FAILED,
    HUMAN_TAKEOVER_NEEDED,
    MONITOR_EXCEPTION,
    STATUS_CHANGE,
    TASK_STOPPED,
    sale_reminder_kind,
    sale_reminder_title,
)
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


def minutes_to_offset_seconds(minutes: Sequence[int]) -> tuple[int, ...]:
    return tuple(sorted({int(m) * 60 for m in minutes}, reverse=True))


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
        self._offsets = tuple(sorted(set(int(x) for x in reminder_offsets), reverse=True))
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

            kind = sale_reminder_kind(offset_seconds)
            title = sale_reminder_title(offset_seconds)
            if offset_seconds <= 0:
                msg = (
                    f"「{task.name}」已到开售时间，请自行打开官方页面购票"
                    f"（本程序不会自动下单）。"
                )
            else:
                msg = f"「{task.name}」开售提醒（T-{offset_seconds}s）。"
            if snap is not None:
                msg += f" remaining={snap.remaining_seconds:.1f}s"

            dedupe_key = job_id  # remind:{task}:{offset} — stable across channels
            event = self._notifier.notify(
                title,
                msg,
                kind=kind,
                task_id=task_id,
                urgent=(offset_seconds <= 60),
                dedupe_key=dedupe_key,
            )
            self._mark_job(job_id, "done")
            return bool(event.delivered)
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
                key = (
                    f"status_change:{task_id}:"
                    f"{prev}->{diff.current.normalized_status}:"
                    f"{diff.current.content_hash}"
                )
                self._notifier.notify(
                    "公开销售状态变化",
                    f"「{task.name}」{prev} → {diff.current.normalized_status}",
                    kind=STATUS_CHANGE,
                    task_id=task_id,
                    urgent=True,
                    dedupe_key=key,
                )
        except AppError as exc:
            logger.error("monitor poll failed task=%s: %s", task_id, exc.user_message)
            self.emit_monitor_exception(task_id, exc.user_message)
            if not isinstance(exc, MonitorFetchError):
                self._safe_pause_on_error(task_id, exc.user_message)
        except Exception as exc:  # noqa: BLE001
            logger.exception("monitor poll crashed task=%s", task_id)
            self.emit_monitor_exception(task_id, str(exc))
            self._safe_pause_on_error(task_id, "monitor crashed")

    # --- explicit event emitters (stubs for browser / takeover / stop) ---

    def emit_browser_launch_failed(
        self,
        task_id: int,
        reason: str,
        *,
        session_key: str | None = None,
    ) -> bool:
        key = f"browser_launch_failed:{task_id}:{session_key or hashlib.sha1(reason.encode()).hexdigest()[:12]}"
        event = self._notifier.notify(
            "浏览器启动失败",
            f"task {task_id}: {reason}",
            kind=BROWSER_LAUNCH_FAILED,
            task_id=task_id,
            urgent=True,
            dedupe_key=key,
        )
        return bool(event.delivered)

    def emit_human_takeover_needed(self, task_id: int, reason: str = "") -> bool:
        key = f"human_takeover_needed:{task_id}"
        msg = f"task {task_id} 需要人工接管"
        if reason:
            msg += f"：{reason}"
        event = self._notifier.notify(
            "需要人工接管",
            msg,
            kind=HUMAN_TAKEOVER_NEEDED,
            task_id=task_id,
            urgent=True,
            dedupe_key=key,
        )
        return bool(event.delivered)

    def emit_monitor_exception(self, task_id: int, reason: str) -> bool:
        digest = hashlib.sha1(reason.encode("utf-8", errors="replace")).hexdigest()[:12]
        key = f"monitor_exception:{task_id}:{digest}"
        event = self._notifier.notify(
            "监控任务异常",
            f"task {task_id}: {reason}",
            kind=MONITOR_EXCEPTION,
            task_id=task_id,
            urgent=True,
            dedupe_key=key,
        )
        return bool(event.delivered)

    def emit_task_stopped(self, task_id: int, reason: str = "stopped") -> bool:
        key = f"task_stopped:{task_id}:{reason}"
        event = self._notifier.notify(
            "任务已停止",
            f"task {task_id}: {reason}",
            kind=TASK_STOPPED,
            task_id=task_id,
            urgent=False,
            dedupe_key=key,
        )
        return bool(event.delivered)

    def _safe_pause_on_error(self, task_id: int, reason: str) -> None:
        try:
            self.pause_task(task_id, note=f"auto-paused: {reason}", emit_stopped=True)
        except Exception:  # noqa: BLE001
            logger.exception("failed to safe-pause task=%s", task_id)

    def schedule_task_reminders(self, task_id: int) -> int:
        """Schedule future reminders for configured offsets. Returns number scheduled."""
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

    def pause_task(
        self,
        task_id: int,
        *,
        note: str | None = None,
        emit_stopped: bool = False,
    ) -> ConcertTask:
        fields: dict = {"status": "paused", "monitor_enabled": False}
        if note:
            fields["note"] = note
        task = self._tasks.update(task_id, **fields)
        self.unschedule_task(task_id)
        logger.info("paused task %s", task_id)
        if emit_stopped:
            self.emit_task_stopped(task_id, reason=note or "paused")
        return task

    def stop_task(self, task_id: int, *, reason: str = "user_stop") -> ConcertTask:
        """Stop monitoring/reminders and emit task_stopped."""
        task = self.pause_task(task_id, note=reason, emit_stopped=True)
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
