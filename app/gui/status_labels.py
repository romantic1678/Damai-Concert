"""Chinese display status labels for the GUI."""

from __future__ import annotations

from datetime import datetime

from app.browser.status import BrowserConnectionStatus
from app.browser.takeover import TakeoverState
from app.models import ConcertTask
from app.services.countdown import CountdownSnapshot
from app.timeutil import ensure_aware, wall_now

# Required product labels
LABEL_WAIT_SALE = "等待开售"
LABEL_MONITORING = "监控中"
LABEL_SOON = "即将开售"
LABEL_ON_SALE = "已开售"
LABEL_WAIT_USER = "等待用户操作"
LABEL_QUEUE = "排队中"
LABEL_ERROR = "异常"
LABEL_STOPPED = "已停止"


def display_status(
    task: ConcertTask,
    *,
    countdown: CountdownSnapshot | None = None,
    browser_status: BrowserConnectionStatus | None = None,
    takeover: TakeoverState | None = None,
    now: datetime | None = None,
) -> str:
    """Map internal states to a single Chinese status label."""
    if takeover == TakeoverState.HUMAN_ACTIVE:
        return LABEL_WAIT_USER
    if browser_status == BrowserConnectionStatus.HUMAN_TAKEOVER:
        return LABEL_WAIT_USER
    if browser_status == BrowserConnectionStatus.PAGE_ERROR:
        return LABEL_ERROR

    note = (task.note or "")
    if "排队" in note:
        return LABEL_QUEUE

    if task.status in {"paused", "cancelled"}:
        if note.startswith("auto-paused"):
            return LABEL_ERROR
        return LABEL_STOPPED
    if task.status == "done":
        return LABEL_ON_SALE

    current = ensure_aware(now or wall_now())
    if task.open_sale_at is not None:
        sale = ensure_aware(task.open_sale_at)
        remaining = sale.timestamp() - current.timestamp()
        if remaining <= 0:
            return LABEL_ON_SALE
        if remaining <= 600:  # 10 minutes
            return LABEL_SOON

    if task.monitor_enabled and task.status == "watching":
        return LABEL_MONITORING

    if task.status == "watching":
        return LABEL_WAIT_SALE

    return LABEL_WAIT_SALE


def format_countdown(snapshot: CountdownSnapshot | None) -> str:
    if snapshot is None:
        return "—"
    secs = int(snapshot.remaining_seconds)
    if secs <= 0:
        return "已到开售时间"
    hours, rem = divmod(secs, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
