"""Domain models (dataclasses). Monitor / reminder only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from app.errors import ValidationError

NormalizedStatus = Literal[
    "unknown",
    "pre_sale",
    "on_sale",
    "sold_out",
    "off_sale",
]

TakeoverStateName = Literal["idle", "browser_assist", "human_active"]

DEFAULT_URL_ALLOWLIST: tuple[str, ...] = (
    "damai.cn",
    "www.damai.cn",
    "m.damai.cn",
    "detail.damai.cn",
)


def parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = value.strip()
    if not text:
        return None
    return datetime.fromisoformat(text)


def dt_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def validate_official_url(
    url: str | None,
    allowlist: tuple[str, ...] | list[str] | None = None,
) -> str | None:
    """Validate HTTPS official URL against host allowlist. Empty/None is allowed."""
    if url is None:
        return None
    text = url.strip()
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme != "https":
        raise ValidationError("official_url must use https")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValidationError("official_url host is missing")
    allowed = tuple(allowlist) if allowlist is not None else DEFAULT_URL_ALLOWLIST
    ok = any(host == a or host.endswith("." + a) for a in allowed)
    if not ok:
        raise ValidationError(f"official_url host not in allowlist: {host}")
    return text


@dataclass(slots=True)
class ConcertTask:
    name: str
    id: int | None = None
    city: str | None = None
    official_url: str | None = None
    open_sale_at: datetime | None = None
    monitor_enabled: bool = False
    note: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def validate(self, allowlist: tuple[str, ...] | list[str] | None = None) -> None:
        if not self.name or not self.name.strip():
            raise ValidationError("task name is required")
        self.name = self.name.strip()
        self.official_url = validate_official_url(self.official_url, allowlist)


@dataclass(slots=True)
class SaleSnapshot:
    task_id: int
    fetched_at: datetime
    source_url: str
    raw_excerpt: str
    normalized_status: NormalizedStatus
    content_hash: str
    id: int | None = None
    is_baseline: bool = False


@dataclass(slots=True)
class StatusBaseline:
    task_id: int
    established_at: datetime
    normalized_status: NormalizedStatus
    content_hash: str
    raw_excerpt: str = ""


@dataclass(slots=True)
class ReminderJob:
    task_id: int
    scheduler_job_id: str
    kind: Literal["countdown_offset", "sale_due", "monitor_interval"]
    status: Literal["scheduled", "paused", "done", "cancelled"]
    created_at: datetime
    id: int | None = None
    run_at: datetime | None = None
    interval_seconds: int | None = None


@dataclass(slots=True)
class NotificationLog:
    channel: str
    title: str
    body: str
    success: bool
    created_at: datetime
    id: int | None = None
    task_id: int | None = None
    error_message: str | None = None


@dataclass(slots=True)
class BrowserSession:
    task_id: int
    official_url: str
    launched_at: datetime
    takeover_state: TakeoverStateName
    id: int | None = None
    closed_at: datetime | None = None
    notes: str | None = None
