"""Phase 7 notification module tests (local mock events only)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.lifecycle import Application
from app.notify.kinds import (
    BROWSER_LAUNCH_FAILED,
    HUMAN_TAKEOVER_NEEDED,
    MONITOR_EXCEPTION,
    REQUIRED_KINDS,
    SALE_DUE,
    SALE_T_MINUS_1M,
    SALE_T_MINUS_10M,
    STATUS_CHANGE,
    TASK_STOPPED,
    sale_reminder_kind,
)
from app.notify.sound import SoundNotifier
from app.services.runtime import reminder_job_id


def test_required_kinds_constant() -> None:
    assert len(REQUIRED_KINDS) == 8


def test_all_eight_event_kinds(app: Application) -> None:
    rt = app.runtime
    tid = 42
    # sale reminders via notify directly with canonical keys
    assert app.notifier.notify(
        "t10", "m", kind=SALE_T_MINUS_10M, task_id=tid, dedupe_key=f"remind:{tid}:600"
    ).delivered
    assert app.notifier.notify(
        "t1", "m", kind=SALE_T_MINUS_1M, task_id=tid, dedupe_key=f"remind:{tid}:60"
    ).delivered
    assert app.notifier.notify(
        "due", "m", kind=SALE_DUE, task_id=tid, dedupe_key=f"remind:{tid}:0"
    ).delivered
    assert app.notifier.notify(
        "status", "m", kind=STATUS_CHANGE, task_id=tid, dedupe_key=f"status_change:{tid}:a"
    ).delivered
    assert rt.emit_browser_launch_failed(tid, "mock launch fail", session_key="s1")
    assert rt.emit_human_takeover_needed(tid, "captcha shown — user must continue manually")
    assert rt.emit_monitor_exception(tid, "mock monitor boom")
    assert rt.emit_task_stopped(tid, reason="user_stop")

    delivered_kinds = {e.kind for e in app.notifier.events if e.delivered}
    assert REQUIRED_KINDS <= delivered_kinds
    assert len(app.gui_sink.peek()) >= 8


def test_dedupe_same_event(app: Application) -> None:
    key = "remind:7:600"
    e1 = app.notifier.notify("a", "b", kind=SALE_T_MINUS_10M, task_id=7, dedupe_key=key)
    e2 = app.notifier.notify("a", "b", kind=SALE_T_MINUS_10M, task_id=7, dedupe_key=key)
    assert e1.delivered is True
    assert e2.delivered is False
    assert len(app.notifier.delivered_of_kind(SALE_T_MINUS_10M)) == 1


def test_sound_disabled(app: Application) -> None:
    sound = SoundNotifier(enabled=False)
    assert sound.send("t", "m") is False
    # settings default sound_enabled False in conftest — factory may still register
    # but SoundNotifier.enabled follows settings
    enabled_flags = [
        n.enabled  # type: ignore[attr-defined]
        for n in app.notifier._notifiers  # noqa: SLF001
        if isinstance(n, SoundNotifier)
    ]
    # either not registered or disabled
    assert not enabled_flags or enabled_flags == [False]


def test_notify_failure_isolation(app: Application) -> None:
    class Boom:
        name = "boom"

        def send(self, title: str, message: str, *, urgent: bool = False) -> bool:
            raise RuntimeError("channel exploded")

    app.notifier.register(Boom())  # type: ignore[arg-type]
    event = app.notifier.notify(
        "still ok",
        "main must survive",
        kind="test_boom",
        dedupe_key="test_boom:1",
        force=True,
    )
    # delivered True because we still create event after attempting channels
    assert event.title == "still ok"


def test_custom_reminder_offsets(tmp_path: Path, example_settings_yaml: Path) -> None:
    data = yaml.safe_load(example_settings_yaml.read_text(encoding="utf-8"))
    data["notify"]["reminder_offsets_minutes"] = [5, 0]
    data["notify"]["sound_enabled"] = False
    path = tmp_path / "custom.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    app = Application.create(
        settings_path=path,
        database_path=tmp_path / "c.db",
        ensure_settings=False,
    )
    try:
        assert app.settings.notify.reminder_offsets_minutes == [5, 0]
        assert app.runtime._offsets == (300, 0)  # noqa: SLF001
        assert sale_reminder_kind(300) == "sale_t_minus_5m"
        assert sale_reminder_kind(0) == SALE_DUE
    finally:
        app.shutdown()


def test_runtime_reminder_dedupe_with_job(app: Application) -> None:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from app.models import ConcertTask

    SH = ZoneInfo("Asia/Shanghai")
    now = datetime(2026, 10, 1, 12, 0, tzinfo=SH)
    app.runtime._clock = lambda: now  # noqa: SLF001
    app.countdown._clock = lambda: now  # noqa: SLF001
    task = app.task_service.create(
        ConcertTask(
            name="N",
            open_sale_at=now + timedelta(minutes=30),
            status="watching",
        )
    )
    assert task.id is not None
    jid = reminder_job_id(task.id, 600)
    app.runtime._record_job(task.id, jid, "countdown_offset", status="scheduled")
    assert app.runtime.fire_reminder(task.id, 600) is True
    assert app.runtime.fire_reminder(task.id, 600) is False


def test_emit_browser_and_takeover_dedupe(app: Application) -> None:
    assert app.runtime.emit_browser_launch_failed(1, "x", session_key="abc")
    assert app.runtime.emit_browser_launch_failed(1, "x", session_key="abc") is False
    assert app.runtime.emit_human_takeover_needed(1, "please take over")
    assert app.runtime.emit_human_takeover_needed(1, "please take over again") is False


def test_schema_v3_dedupe_table(app: Application) -> None:
    tables = app.database.tables()
    assert "notification_dedupe" in tables
