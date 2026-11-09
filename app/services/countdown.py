"""Open-sale countdown snapshots (wall-clock, timezone-aware)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Literal, Sequence

from app.errors import NotFoundError, ValidationError
from app.models import ConcertTask
from app.services.task_service import TaskService
from app.timeutil import DEFAULT_TZ_NAME, ensure_aware, to_zone, wall_now

CountdownPhase = Literal["upcoming", "due", "past"]

# Reminder offsets before open_sale_at (seconds): T-10min, T-1min, T-0
DEFAULT_REMINDER_OFFSETS: tuple[int, ...] = (600, 60, 0)


@dataclass(frozen=True, slots=True)
class CountdownSnapshot:
    task_id: int
    open_sale_at: datetime
    remaining_seconds: float
    phase: CountdownPhase
    timezone: str


Clock = Callable[[], datetime]


class CountdownService:
    def __init__(
        self,
        task_service: TaskService,
        *,
        timezone: str = DEFAULT_TZ_NAME,
        clock: Clock | None = None,
    ) -> None:
        self._tasks = task_service
        self._tz = timezone
        self._clock: Clock = clock or (lambda: wall_now(self._tz))

    def snapshot(self, task_id: int, now: datetime | None = None) -> CountdownSnapshot:
        task = self._tasks.require(task_id)
        return self.snapshot_task(task, now=now)

    def snapshot_task(self, task: ConcertTask, now: datetime | None = None) -> CountdownSnapshot:
        if task.id is None:
            raise ValidationError("task id is required for countdown")
        if task.open_sale_at is None:
            raise ValidationError(f"task {task.id} has no open_sale_at")
        sale = ensure_aware(task.open_sale_at, default_tz=self._tz)
        current = ensure_aware(now or self._clock(), default_tz=self._tz)
        # Compare in UTC to avoid DST pitfalls
        remaining = sale.timestamp() - current.timestamp()
        if remaining > 0:
            phase: CountdownPhase = "upcoming"
        elif remaining > -1.0:
            phase = "due"
        else:
            phase = "past"
        return CountdownSnapshot(
            task_id=int(task.id),
            open_sale_at=to_zone(sale, self._tz),
            remaining_seconds=remaining,
            phase=phase,
            timezone=self._tz,
        )

    def snapshots_for_tasks(
        self,
        tasks: Sequence[ConcertTask] | None = None,
        now: datetime | None = None,
    ) -> list[CountdownSnapshot]:
        items = tasks if tasks is not None else self._tasks.list_all()
        out: list[CountdownSnapshot] = []
        current = now or self._clock()
        for task in items:
            if task.open_sale_at is None or task.id is None:
                continue
            out.append(self.snapshot_task(task, now=current))
        return out

    def reminder_fire_at(self, open_sale_at: datetime, offset_seconds: int) -> datetime:
        sale = ensure_aware(open_sale_at, default_tz=self._tz)
        from datetime import timedelta

        return sale - timedelta(seconds=offset_seconds)
