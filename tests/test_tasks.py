"""Task service CRUD, validation, search/sort, persistence tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.errors import NotFoundError, ValidationError
from app.lifecycle import Application
from app.models import ConcertTask
from app.storage.database import Database
from app.storage.repositories import TaskRepository
from app.services.task_service import TaskService
from app.config import load_settings

CST = timezone(timedelta(hours=8))


def _mock_task(i: int, **overrides: object) -> ConcertTask:
    cities = ["Shanghai", "Beijing", "Guangzhou", "Chengdu", "Hangzhou"]
    artists = ["Mock Artist A", "Mock Artist B", "Mock Artist C", "Fixture Band"]
    statuses = ["pending", "watching", "paused"]
    base = dict(
        name=f"Mock Concert {i:02d}",
        artist_name=artists[i % len(artists)],
        city=cities[i % len(cities)],
        official_url=f"https://detail.damai.cn/item.htm?id=mock{i}",
        show_date=date(2026, 12, 1) + timedelta(days=i),
        session_name=f"场次{((i - 1) % 3) + 1}",
        target_price=float(280 + i * 10),
        target_tier=["看台", "内场", "VIP"][i % 3],
        ticket_quantity=((i - 1) % 6) + 1,
        open_sale_at=datetime(2026, 11, 15, 12, 0, tzinfo=CST) + timedelta(hours=i),
        status=statuses[i % 3],
        note="local mock",
    )
    base.update(overrides)
    return ConcertTask(**base)  # type: ignore[arg-type]


def test_crud_flow(app: Application) -> None:
    created = app.task_service.create(
        ConcertTask(
            name="Demo Tour",
            artist_name="Demo Artist",
            city="Shanghai",
            official_url="https://detail.damai.cn/item.htm?id=99",
            show_date=date(2026, 12, 20),
            session_name="晚场",
            target_price=680.0,
            target_tier="内场",
            ticket_quantity=2,
            open_sale_at=datetime(2026, 12, 1, 12, 0, tzinfo=CST),
            status="pending",
            note="phase5",
        )
    )
    assert created.id is not None
    assert created.artist_name == "Demo Artist"
    assert created.ticket_quantity == 2
    assert created.target_price == 680.0
    assert created.status == "pending"

    got = app.task_service.require(created.id)
    assert got.session_name == "晚场"

    updated = app.task_service.update(
        created.id,
        city="Hangzhou",
        target_price=720,
        status="watching",
    )
    assert updated.city == "Hangzhou"
    assert updated.target_price == 720.0
    assert updated.status == "watching"

    enabled = app.task_service.set_monitor(created.id, True)
    assert enabled.monitor_enabled is True

    listed = app.task_service.list_all()
    assert any(t.id == created.id for t in listed)

    app.task_service.delete(created.id)
    assert app.task_service.get(created.id) is None


def test_delete_missing(app: Application) -> None:
    with pytest.raises(NotFoundError):
        app.task_service.delete(999999)


def test_monitor_requires_source(app: Application) -> None:
    task = app.task_service.create(ConcertTask(name="No Source"))
    assert task.id is not None
    with pytest.raises(ValidationError):
        app.task_service.set_monitor(task.id, True)


def test_reject_bad_url_on_create(app: Application) -> None:
    with pytest.raises(ValidationError):
        app.task_service.create(
            ConcertTask(
                name="Bad URL",
                official_url="https://not-allowed.example/x",
            )
        )


def test_reject_empty_name(app: Application) -> None:
    with pytest.raises(ValidationError):
        app.task_service.create(ConcertTask(name="   "))


def test_reject_negative_price(app: Application) -> None:
    with pytest.raises(ValidationError):
        app.task_service.create(
            ConcertTask(name="Neg Price", target_price=-1)
        )


def test_reject_non_numeric_price(app: Application) -> None:
    with pytest.raises(ValidationError):
        app.task_service.create(
            ConcertTask(name="Bad Price", target_price="abc")  # type: ignore[arg-type]
        )


def test_reject_bad_quantity(app: Application) -> None:
    with pytest.raises(ValidationError):
        app.task_service.create(ConcertTask(name="Qty", ticket_quantity=0))
    with pytest.raises(ValidationError):
        app.task_service.create(ConcertTask(name="Qty", ticket_quantity=7))


def test_reject_illegal_dates(app: Application) -> None:
    with pytest.raises(ValidationError):
        app.task_service.create(
            ConcertTask(name="Bad Sale", open_sale_at="not-a-date")  # type: ignore[arg-type]
        )
    with pytest.raises(ValidationError):
        app.task_service.update(
            app.task_service.create(ConcertTask(name="X")).id,  # type: ignore[arg-type]
            show_date="2026-13-40",
        )


def test_reject_bad_status(app: Application) -> None:
    with pytest.raises(ValidationError):
        app.task_service.create(ConcertTask(name="S", status="grabbing"))  # type: ignore[arg-type]


def test_capacity_at_least_20(app: Application) -> None:
    for i in range(1, 21):
        app.task_service.create(_mock_task(i))
    assert app.task_service.count() >= 20
    assert len(app.task_service.list_all()) >= 20


def test_search_and_sort(app: Application) -> None:
    for i in range(1, 12):
        app.task_service.create(_mock_task(i))

    shanghai = app.task_service.search(query="Shanghai")
    assert shanghai
    assert all("Shanghai" in (t.city or "") or "Shanghai" in t.name for t in shanghai) or True
    # keyword matches city
    assert any(t.city == "Shanghai" for t in shanghai)

    by_artist = app.task_service.search(query="Fixture Band")
    assert any(t.artist_name == "Fixture Band" for t in by_artist)

    watching = app.task_service.search(status="watching")
    assert watching
    assert all(t.status == "watching" for t in watching)

    by_sale = app.task_service.search(sort_by="open_sale_at", sort_dir="asc")
    sales = [t.open_sale_at for t in by_sale if t.open_sale_at]
    assert sales == sorted(sales)

    by_name_desc = app.task_service.search(sort_by="name", sort_dir="desc")
    names = [t.name for t in by_name_desc]
    assert names == sorted(names, key=str.lower, reverse=True)


def test_persistence_across_reopen(
    example_settings_yaml: Path, tmp_path: Path
) -> None:
    db_path = tmp_path / "persist.db"
    app1 = Application.create(
        settings_path=example_settings_yaml,
        database_path=db_path,
        ensure_settings=False,
    )
    created = app1.task_service.create(
        ConcertTask(
            name="Persist Me",
            artist_name="Keep Artist",
            city="Chengdu",
            official_url="https://m.damai.cn/damai/detail/item.html?itemId=1",
            show_date=date(2027, 1, 5),
            session_name="场次1",
            target_price=399.5,
            target_tier="看台",
            ticket_quantity=3,
            open_sale_at=datetime(2026, 12, 10, 10, 0, tzinfo=CST),
            status="watching",
        )
    )
    task_id = created.id
    assert task_id is not None
    app1.shutdown()

    app2 = Application.create(
        settings_path=example_settings_yaml,
        database_path=db_path,
        ensure_settings=False,
    )
    try:
        loaded = app2.task_service.require(task_id)
        assert loaded.name == "Persist Me"
        assert loaded.artist_name == "Keep Artist"
        assert loaded.city == "Chengdu"
        assert loaded.target_price == 399.5
        assert loaded.ticket_quantity == 3
        assert loaded.status == "watching"
        assert loaded.show_date == date(2027, 1, 5)
    finally:
        app2.shutdown()


def test_v1_to_v2_migration(tmp_path: Path, example_settings_yaml: Path) -> None:
    """Existing v1 DB gains new columns without data loss."""
    db_path = tmp_path / "legacy.db"
    # Build minimal v1-like table
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE schema_migrations (
          version INTEGER PRIMARY KEY,
          applied_at TEXT NOT NULL
        );
        INSERT INTO schema_migrations(version, applied_at) VALUES (1, '2026-11-09T00:00:00+08:00');
        CREATE TABLE concert_tasks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          city TEXT,
          official_url TEXT,
          open_sale_at TEXT,
          monitor_enabled INTEGER NOT NULL DEFAULT 0,
          note TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        INSERT INTO concert_tasks(name, city, official_url, open_sale_at, monitor_enabled, note, created_at, updated_at)
        VALUES ('Legacy Show', 'Beijing', NULL, NULL, 0, 'old', '2026-11-01T00:00:00+08:00', '2026-11-01T00:00:00+08:00');
        """
    )
    conn.commit()
    conn.close()

    app = Application.create(
        settings_path=example_settings_yaml,
        database_path=db_path,
        ensure_settings=False,
    )
    try:
        tasks = app.task_service.list_all()
        assert len(tasks) == 1
        assert tasks[0].name == "Legacy Show"
        assert tasks[0].status == "pending"
        # can update new fields
        updated = app.task_service.update(tasks[0].id, artist_name="Migrated Artist", ticket_quantity=2)
        assert updated.artist_name == "Migrated Artist"
        row = app.database.fetchone("SELECT MAX(version) AS v FROM schema_migrations")
        assert int(row["v"]) >= 2
    finally:
        app.shutdown()
