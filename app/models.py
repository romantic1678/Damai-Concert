"""Domain models (dataclasses). Monitor / reminder only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
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

TaskStatus = Literal["pending", "watching", "paused", "done", "cancelled"]

TASK_STATUSES: frozenset[str] = frozenset(
    {"pending", "watching", "paused", "done", "cancelled"}
)

# Typical concert ticket purchase bounds (metadata only — no auto-buy).
TICKET_QUANTITY_MIN = 1
TICKET_QUANTITY_MAX = 6

DEFAULT_URL_ALLOWLIST: tuple[str, ...] = (
    "damai.cn",
    "www.damai.cn",
    "m.damai.cn",
    "detail.damai.cn",
)

SortField = Literal["open_sale_at", "created_at", "name", "city", "status", "show_date", "id"]
SortDir = Literal["asc", "desc"]


def parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError(f"invalid datetime: {value!r}") from exc


def parse_date(value: str | date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        if "T" in text:
            return datetime.fromisoformat(text).date()
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError(f"invalid date: {value!r}") from exc


def dt_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def date_to_iso(value: date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def validate_official_url(
    url: str | None,
    allowlist: tuple[str, ...] | list[str] | None = None,
    *,
    required: bool = False,
) -> str | None:
    """Validate HTTPS official URL against host allowlist."""
    if url is None or not str(url).strip():
        if required:
            raise ValidationError("official_url is required")
        return None
    text = str(url).strip()
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


def validate_target_price(value: float | int | str | Decimal | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, Decimal):
            price = float(value)
        else:
            price = float(value)
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValidationError(f"target_price must be a number, got {value!r}") from exc
    if price != price:  # NaN
        raise ValidationError("target_price must be a finite number")
    if price < 0:
        raise ValidationError("target_price must be >= 0")
    return price


def validate_ticket_quantity(value: int | str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        qty = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"ticket_quantity must be an integer, got {value!r}") from exc
    if qty < TICKET_QUANTITY_MIN or qty > TICKET_QUANTITY_MAX:
        raise ValidationError(
            f"ticket_quantity must be between {TICKET_QUANTITY_MIN} and {TICKET_QUANTITY_MAX}"
        )
    return qty


def validate_task_status(value: str | None) -> TaskStatus:
    status = (value or "pending").strip().lower()
    if status not in TASK_STATUSES:
        raise ValidationError(
            f"status must be one of {sorted(TASK_STATUSES)}, got {value!r}"
        )
    return status  # type: ignore[return-value]


@dataclass(slots=True)
class ConcertTask:
    """Concert watch / reminder task (no auto-purchase fields beyond preferences)."""

    name: str
    id: int | None = None
    artist_name: str | None = None
    city: str | None = None
    official_url: str | None = None
    show_date: date | None = None
    session_name: str | None = None
    target_price: float | None = None
    target_tier: str | None = None
    ticket_quantity: int | None = None
    open_sale_at: datetime | None = None
    status: TaskStatus = "pending"
    monitor_enabled: bool = False
    note: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def validate(self, allowlist: tuple[str, ...] | list[str] | None = None) -> None:
        if not self.name or not str(self.name).strip():
            raise ValidationError("task name is required")
        self.name = str(self.name).strip()

        if self.artist_name is not None:
            self.artist_name = str(self.artist_name).strip() or None
        if self.city is not None:
            self.city = str(self.city).strip() or None
        if self.session_name is not None:
            self.session_name = str(self.session_name).strip() or None
        if self.target_tier is not None:
            self.target_tier = str(self.target_tier).strip() or None
        if self.note is not None:
            self.note = str(self.note).strip() or None

        self.official_url = validate_official_url(self.official_url, allowlist)
        # Coerce string inputs (CLI / YAML / loose constructors)
        if isinstance(self.show_date, (str, datetime)):
            self.show_date = parse_date(self.show_date)  # type: ignore[arg-type]
        if isinstance(self.open_sale_at, str):
            self.open_sale_at = parse_datetime(self.open_sale_at)

        self.target_price = validate_target_price(self.target_price)
        self.ticket_quantity = validate_ticket_quantity(self.ticket_quantity)
        self.status = validate_task_status(self.status)


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
