"""Phase 10 coverage gaps: logging, shutdown/restart, multi-task schedule."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.lifecycle import Application
from app.logging_config import get_logger, setup_logging
from app.models import ConcertTask
from app.services.runtime import reminder_job_id

SH = ZoneInfo("Asia/Shanghai")


def test_logging_writes_file(example_settings_yaml: Path, tmp_path: Path) -> None:
    from app.config import load_settings

    settings = load_settings(example_settings_yaml, ensure_exists=False)
    setup_logging(settings, force=True)
    log_path = settings.log_file_path
    logger = get_logger("phase10")
    marker = "PHASE10_LOG_MARKER_UNIQUE"
    logger.warning(marker)
    # Ensure handlers flush
    for h in list(__import__("logging").getLogger().handlers):
        try:
            h.flush()
        except Exception:
            pass
    assert log_path.is_file()
    content = log_path.read_text(encoding="utf-8", errors="replace")
    assert marker in content


def test_shutdown_restart_persists_tasks(
    example_settings_yaml: Path, tmp_path: Path
) -> None:
    db = tmp_path / "restart.db"
    app1 = Application.create(
        settings_path=example_settings_yaml,
        database_path=db,
        ensure_settings=False,
        browser_headless=True,
    )
    created = app1.task_service.create(
        ConcertTask(
            name="Restart Persist",
            city="Shanghai",
            official_url="https://detail.damai.cn/item.htm?id=rp1",
            open_sale_at=datetime(2026, 12, 20, 12, 0, tzinfo=SH),
            status="watching",
        )
    )
    tid = created.id
    assert tid is not None
    app1.shutdown()

    app2 = Application.create(
        settings_path=example_settings_yaml,
        database_path=db,
        ensure_settings=False,
        browser_headless=True,
    )
    try:
        loaded = app2.task_service.require(tid)
        assert loaded.name == "Restart Persist"
        assert loaded.city == "Shanghai"
        assert app2.task_service.count() >= 1
    finally:
        app2.shutdown()


def test_multi_task_reminder_schedule_ids(
    example_settings_yaml: Path, tmp_path: Path
) -> None:
    from app.timeutil import wall_now

    app = Application.create(
        settings_path=example_settings_yaml,
        database_path=tmp_path / "sched.db",
        ensure_settings=False,
        browser_headless=True,
    )
    try:
        now = wall_now(SH)
        app.runtime._clock = lambda: now  # noqa: SLF001
        app.countdown._clock = lambda: now  # noqa: SLF001
        ids = []
        for i in range(3):
            t = app.task_service.create(
                ConcertTask(
                    name=f"Multi {i}",
                    open_sale_at=now + timedelta(minutes=40 + i),
                    status="watching",
                )
            )
            assert t.id is not None
            ids.append(t.id)
        app.scheduler.start()
        try:
            totals = 0
            for tid in ids:
                totals += app.runtime.schedule_task_reminders(tid)
            assert totals >= 9  # 3 tasks * 3 offsets
            job_ids = set(app.scheduler.get_job_ids())
            for tid in ids:
                assert reminder_job_id(tid, 600) in job_ids
                assert reminder_job_id(tid, 60) in job_ids
                assert reminder_job_id(tid, 0) in job_ids
        finally:
            for tid in ids:
                app.runtime.unschedule_task(tid)
            app.scheduler.shutdown(wait=False)
    finally:
        app.shutdown()


def test_notify_log_without_existing_task_id(app: Application) -> None:
    """Ephemeral task_id must not crash notification_logs FK."""
    event = app.notifier.notify(
        "orphan",
        "no concert_tasks row",
        kind="test_orphan",
        task_id=999999,
        dedupe_key="orphan:999999",
        force=True,
    )
    assert event.delivered is True
    rows = app.database.fetchall(
        "SELECT task_id, title FROM notification_logs WHERE title = ?",
        ("orphan",),
    )
    assert rows
    assert rows[0]["task_id"] is None
