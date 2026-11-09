"""Task service CRUD tests."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from app.errors import NotFoundError, ValidationError
from app.lifecycle import Application
from app.models import ConcertTask

CST = timezone(timedelta(hours=8))


def test_crud_flow(app: Application) -> None:
    created = app.task_service.create(
        ConcertTask(
            name="Demo Tour",
            city="Shanghai",
            official_url="https://detail.damai.cn/item.htm?id=99",
            open_sale_at=datetime(2026, 12, 1, 12, 0, tzinfo=CST),
            note="phase4",
        )
    )
    assert created.id is not None
    assert created.monitor_enabled is False

    got = app.task_service.require(created.id)
    assert got.name == "Demo Tour"

    updated = app.task_service.update(created.id, city="Hangzhou")
    assert updated.city == "Hangzhou"

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
