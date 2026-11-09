"""Model validation tests."""

from __future__ import annotations

import pytest

from app.errors import ValidationError
from app.models import (
    ConcertTask,
    parse_date,
    parse_datetime,
    validate_official_url,
    validate_target_price,
    validate_ticket_quantity,
)


def test_validate_official_url_ok() -> None:
    url = validate_official_url("https://detail.damai.cn/item.htm?id=1")
    assert url is not None
    assert "damai.cn" in url


def test_reject_http() -> None:
    with pytest.raises(ValidationError):
        validate_official_url("http://detail.damai.cn/item.htm?id=1")


def test_reject_unknown_host() -> None:
    with pytest.raises(ValidationError):
        validate_official_url("https://evil.example/phish")


def test_concert_task_requires_name() -> None:
    task = ConcertTask(name="  ")
    with pytest.raises(ValidationError):
        task.validate()


def test_parse_illegal_datetime() -> None:
    with pytest.raises(ValidationError):
        parse_datetime("yesterday")


def test_parse_illegal_date() -> None:
    with pytest.raises(ValidationError):
        parse_date("2026-99-01")


def test_price_and_qty_helpers() -> None:
    assert validate_target_price("128.5") == 128.5
    with pytest.raises(ValidationError):
        validate_target_price(-3)
    assert validate_ticket_quantity(2) == 2
    with pytest.raises(ValidationError):
        validate_ticket_quantity(99)
