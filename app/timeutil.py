"""Timezone-aware time helpers.

Approach
--------
* **Absolute open-sale times** use the wall clock with aware ``datetime`` values
  (``zoneinfo``). Default display/compare zone is ``Asia/Shanghai``.
* **Remaining seconds** = ``(open_sale_at - now).total_seconds()`` after both
  sides are converted to UTC. This correctly handles DST where the zone observes it
  (Asia/Shanghai currently has no DST, but we never use naive local math).
* **Interval waits** (if any sleep is done outside APScheduler) should use
  ``time.monotonic()`` so system clock steps do not shorten/lengthen the wait.
  APScheduler date triggers still fire by wall clock against ``open_sale_at``.
* **Clock skew**: we cannot know true NTP offset without an external source; we
  document that countdowns follow the local OS clock. Reminders are idempotent
  in DB so a clock jump that double-wakes a job will not double-notify.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DEFAULT_TZ_NAME = "Asia/Shanghai"
DEFAULT_TZ = ZoneInfo(DEFAULT_TZ_NAME)
UTC = timezone.utc


def get_zone(name: str | None = None) -> ZoneInfo:
    return ZoneInfo(name or DEFAULT_TZ_NAME)


def ensure_aware(dt: datetime, *, default_tz: str | ZoneInfo | None = None) -> datetime:
    """Attach default timezone if naive; leave aware values unchanged."""
    if dt.tzinfo is not None:
        return dt
    tz = default_tz if isinstance(default_tz, ZoneInfo) else get_zone(
        default_tz if isinstance(default_tz, str) else None
    )
    return dt.replace(tzinfo=tz)


def to_zone(dt: datetime, tz: str | ZoneInfo | None = None) -> datetime:
    aware = ensure_aware(dt, default_tz=tz)
    zone = tz if isinstance(tz, ZoneInfo) else get_zone(tz if isinstance(tz, str) else None)
    return aware.astimezone(zone)


def utc_now() -> datetime:
    return datetime.now(UTC)


def wall_now(tz: str | ZoneInfo | None = None) -> datetime:
    zone = tz if isinstance(tz, ZoneInfo) else get_zone(tz if isinstance(tz, str) else None)
    return datetime.now(zone)
