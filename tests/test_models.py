"""Model validation tests."""

from __future__ import annotations

import pytest

from app.errors import ValidationError
from app.models import ConcertTask, validate_official_url


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
