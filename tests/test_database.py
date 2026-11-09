"""SQLite schema and cascade tests."""

from __future__ import annotations

from pathlib import Path

from app.lifecycle import Application
from app.models import ConcertTask
from app.storage.database import SCHEMA_VERSION, Database


def test_migrate_creates_tables(tmp_path: Path) -> None:
    db = Database(tmp_path / "x.db")
    db.connect()
    db.migrate()
    tables = set(db.tables())
    assert "concert_tasks" in tables
    assert "sale_snapshots" in tables
    assert "status_baselines" in tables
    assert "reminder_jobs" in tables
    assert "notification_logs" in tables
    assert "browser_sessions" in tables
    row = db.fetchone(
        "SELECT version FROM schema_migrations WHERE version = ?",
        (SCHEMA_VERSION,),
    )
    assert row is not None
    db.migrate()  # idempotent
    db.close()


def test_foreign_key_cascade(app: Application) -> None:
    task = app.task_service.create(
        ConcertTask(name="Cascade Show", city="Beijing")
    )
    assert task.id is not None
    app.database.execute(
        """
        INSERT INTO sale_snapshots (
          task_id, fetched_at, source_url, raw_excerpt,
          normalized_status, content_hash, is_baseline
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task.id,
            "2026-11-09T12:00:00+08:00",
            "https://detail.damai.cn/item.htm?id=1",
            "excerpt",
            "pre_sale",
            "abc",
            1,
        ),
    )
    snaps = app.database.fetchall(
        "SELECT id FROM sale_snapshots WHERE task_id = ?",
        (task.id,),
    )
    assert len(snaps) == 1
    app.task_service.delete(task.id)
    snaps_after = app.database.fetchall(
        "SELECT id FROM sale_snapshots WHERE task_id = ?",
        (task.id,),
    )
    assert snaps_after == []
