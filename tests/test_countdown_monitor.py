"""Phase 6: countdown, reminders, monitor, pause/resume (mock only)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.errors import MonitorFetchError
from app.lifecycle import Application
from app.models import ConcertTask
from app.notify.recording import RecordingNotifier
from app.services.countdown import CountdownService
from app.services.monitor import (
    FixtureStatusFetcher,
    MonitorService,
    RejectNetworkFetcher,
    parse_public_status,
)
from app.services.runtime import TaskRuntime, reminder_job_id
from app.timeutil import ensure_aware

SH = ZoneInfo("Asia/Shanghai")
NY = ZoneInfo("America/New_York")
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "status"


@pytest.fixture()
def recording_app(app: Application) -> Application:
    rec = RecordingNotifier()
    app.notifier.register(rec)
    app._recording = rec  # type: ignore[attr-defined]
    return app


def test_countdown_remaining_across_timezones(app: Application) -> None:
    sale_sh = datetime(2026, 12, 1, 12, 0, tzinfo=SH)
    task = app.task_service.create(
        ConcertTask(name="TZ Show", open_sale_at=sale_sh, status="watching")
    )
    # Same instant expressed in New York
    now_ny = datetime(2026, 12, 1, 10, 0, tzinfo=NY)  # 23:00 previous day SH? 
    # 2026-12-01 10:00 America/New_York = 2026-12-01 23:00 Asia/Shanghai
    # Wait: SH is UTC+8, NY EST is UTC-5 → 10:00 NY = 15:00 UTC = 23:00 SH same day.
    # sale is 12:00 SH = 04:00 UTC. now 23:00 SH means remaining negative (past).
    # Use now = 2026-12-01 11:00 SH via NY equivalent:
    now = datetime(2026, 11, 30, 22, 0, tzinfo=NY)  # = 2026-12-01 11:00 SH
    assert to_sh(now) == datetime(2026, 12, 1, 11, 0, tzinfo=SH)
    snap = app.countdown.snapshot(task.id, now=now)  # type: ignore[arg-type]
    assert snap.phase == "upcoming"
    assert 3500 < snap.remaining_seconds < 3700  # ~1 hour


def to_sh(dt: datetime) -> datetime:
    return dt.astimezone(SH)


def test_multi_task_independent_countdowns(app: Application) -> None:
    now = datetime(2026, 6, 1, 12, 0, tzinfo=SH)
    t1 = app.task_service.create(
        ConcertTask(
            name="Soon",
            open_sale_at=now + timedelta(minutes=5),
            status="watching",
        )
    )
    t2 = app.task_service.create(
        ConcertTask(
            name="Later",
            open_sale_at=now + timedelta(hours=2),
            status="watching",
        )
    )
    snaps = {s.task_id: s for s in app.countdown.snapshots_for_tasks(now=now)}
    assert snaps[t1.id].remaining_seconds < snaps[t2.id].remaining_seconds  # type: ignore[index]
    assert snaps[t1.id].phase == "upcoming"
    assert snaps[t2.id].phase == "upcoming"


def test_reminder_offsets_fire_once(recording_app: Application) -> None:
    app = recording_app
    now = datetime(2026, 7, 1, 12, 0, tzinfo=SH)
    # Freeze clock via countdown/runtime clock injection
    app.countdown._clock = lambda: now  # noqa: SLF001
    app.runtime._clock = lambda: now  # noqa: SLF001
    sale = now + timedelta(minutes=30)
    task = app.task_service.create(
        ConcertTask(name="Remind Me", open_sale_at=sale, status="watching")
    )
    assert task.id is not None
    for offset in (600, 60, 0):
        jid = reminder_job_id(task.id, offset)
        app.runtime._record_job(task.id, jid, "countdown_offset", status="scheduled")
        assert app.runtime.fire_reminder(task.id, offset) is True
        assert app.runtime.fire_reminder(task.id, offset) is False  # idempotent
    kinds = [e.kind for e in app.notifier.events]
    assert "sale_t_minus_10m" in kinds
    assert "sale_t_minus_1m" in kinds
    assert "sale_due" in kinds
    assert kinds.count("sale_t_minus_10m") == 1


def test_pause_and_resume(app: Application) -> None:
    now = datetime(2026, 8, 1, 10, 0, tzinfo=SH)
    app.runtime._clock = lambda: now  # noqa: SLF001
    app.countdown._clock = lambda: now  # noqa: SLF001
    task = app.task_service.create(
        ConcertTask(
            name="Pauseable",
            open_sale_at=now + timedelta(hours=1),
            status="watching",
            monitor_enabled=False,
        )
    )
    assert task.id is not None
    n = app.runtime.schedule_task_reminders(task.id)
    assert n >= 1
    app.runtime.pause_task(task.id)
    paused = app.task_service.require(task.id)
    assert paused.status == "paused"
    # Reminder while paused is skipped
    jid = reminder_job_id(task.id, 600)
    app.runtime._record_job(task.id, jid, "countdown_offset", status="scheduled")
    assert app.runtime.fire_reminder(task.id, 600) is False
    resumed = app.runtime.resume_task(task.id, enable_monitor=False)
    assert resumed.status == "watching"


def test_status_unknown_on_fetch_fail(app: Application) -> None:
    task = app.task_service.create(
        ConcertTask(
            name="No Fixture",
            official_url="https://detail.damai.cn/item.htm?id=1",
            status="watching",
            monitor_enabled=True,
        )
    )
    assert task.id is not None
    # default RejectNetworkFetcher
    snap = app.monitor.establish_baseline(task.id)
    assert snap.normalized_status == "unknown"


def test_diff_detects_change_with_fixtures(app: Application) -> None:
    task = app.task_service.create(
        ConcertTask(
            name="Fixture Diff",
            official_url="https://detail.damai.cn/item.htm?id=2",
            status="watching",
            monitor_enabled=True,
        )
    )
    assert task.id is not None
    fetcher = FixtureStatusFetcher({task.id: FIXTURES / "pre_sale.html"})
    app.monitor._fetcher = fetcher  # noqa: SLF001
    base = app.monitor.establish_baseline(task.id)
    assert base.normalized_status == "pre_sale"
    assert base.is_baseline is True
    # first poll after baseline with same content — may notify false if status same
    same = app.monitor.poll_once(task.id)
    assert same.should_notify is False
    fetcher.set_path(task.id, FIXTURES / "on_sale.html")
    changed = app.monitor.poll_once(task.id)
    assert changed.should_notify is True
    assert changed.current.normalized_status == "on_sale"
    assert "normalized_status" in changed.changed_fields
    # history recorded
    rows = app.database.fetchall(
        "SELECT normalized_status FROM sale_snapshots WHERE task_id = ? ORDER BY id",
        (task.id,),
    )
    assert len(rows) >= 3


def test_safe_stop_on_fetcher_exception(recording_app: Application) -> None:
    app = recording_app

    class BoomFetcher:
        def fetch(self, task: ConcertTask):
            raise RuntimeError("boom")

    task = app.task_service.create(
        ConcertTask(
            name="Boom",
            official_url="https://detail.damai.cn/item.htm?id=3",
            status="watching",
            monitor_enabled=True,
        )
    )
    assert task.id is not None
    app.monitor._fetcher = BoomFetcher()  # noqa: SLF001
    # poll_once should not raise — maps to unknown
    diff = app.monitor.poll_once(task.id)
    assert diff.current.normalized_status == "unknown"

    # fire_monitor_poll should not crash process
    app.runtime.fire_monitor_poll(task.id)


def test_parse_unknown_when_ambiguous() -> None:
    status, _ = parse_public_status("<html>hello</html>")
    assert status == "unknown"


def test_reject_network_fetcher() -> None:
    f = RejectNetworkFetcher()
    with pytest.raises(MonitorFetchError):
        f.fetch(ConcertTask(name="x", id=1))


def test_no_real_damai_network_in_monitor(monkeypatch: pytest.MonkeyPatch, app: Application) -> None:
    """Ensure stdlib urlopen cannot be used accidentally during poll."""

    def blocked(*_a, **_k):  # type: ignore[no-untyped-def]
        raise AssertionError("network to Damai is forbidden in tests")

    monkeypatch.setattr("urllib.request.urlopen", blocked)
    task = app.task_service.create(
        ConcertTask(
            name="Net Block",
            official_url="https://detail.damai.cn/item.htm?id=9",
            monitor_enabled=True,
            status="watching",
        )
    )
    assert task.id is not None
    # Still works: reject fetcher → unknown, no urlopen
    snap = app.monitor.establish_baseline(task.id)
    assert snap.normalized_status == "unknown"


def test_schedule_reminders_registers_future_only(app: Application) -> None:
    """Use real wall-clock future so APScheduler does not misfire immediately."""
    from app.timeutil import wall_now

    now = wall_now(SH)
    app.runtime._clock = lambda: now  # noqa: SLF001
    app.countdown._clock = lambda: now  # noqa: SLF001
    task = app.task_service.create(
        ConcertTask(
            name="Sched",
            open_sale_at=now + timedelta(minutes=30),
            status="watching",
        )
    )
    assert task.id is not None
    app.scheduler.start()
    try:
        n = app.runtime.schedule_task_reminders(task.id)
        assert n == 3  # T-10m, T-1m, T-0 all in the real future
        ids = app.scheduler.get_job_ids()
        assert reminder_job_id(task.id, 600) in ids
        assert reminder_job_id(task.id, 60) in ids
        assert reminder_job_id(task.id, 0) in ids
        # Also persisted
        rows = app.database.fetchall(
            "SELECT scheduler_job_id, status FROM reminder_jobs WHERE task_id = ?",
            (task.id,),
        )
        assert len(rows) >= 3
    finally:
        app.runtime.unschedule_task(task.id)
        app.scheduler.shutdown(wait=False)


def test_past_offsets_cancelled_not_scheduled(app: Application) -> None:
    now = datetime(2026, 9, 1, 12, 0, tzinfo=SH)
    app.runtime._clock = lambda: now  # noqa: SLF001
    app.countdown._clock = lambda: now  # noqa: SLF001
    # Sale already 1 minute ago relative to fake clock — all offsets in the past
    task = app.task_service.create(
        ConcertTask(
            name="Past Sale",
            open_sale_at=now - timedelta(minutes=1),
            status="watching",
        )
    )
    assert task.id is not None
    n = app.runtime.schedule_task_reminders(task.id)
    assert n == 0
    rows = app.database.fetchall(
        "SELECT status FROM reminder_jobs WHERE task_id = ?",
        (task.id,),
    )
    assert rows and all(r["status"] == "cancelled" for r in rows)
