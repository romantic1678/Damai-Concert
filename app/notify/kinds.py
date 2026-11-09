"""Canonical notification event kinds (phase 7)."""

from __future__ import annotations

from typing import Final

# Eight required product events (+ dynamic sale_t_minus_*m for custom offsets)
SALE_T_MINUS_10M: Final = "sale_t_minus_10m"
SALE_T_MINUS_1M: Final = "sale_t_minus_1m"
SALE_DUE: Final = "sale_due"
STATUS_CHANGE: Final = "status_change"
BROWSER_LAUNCH_FAILED: Final = "browser_launch_failed"
HUMAN_TAKEOVER_NEEDED: Final = "human_takeover_needed"
MONITOR_EXCEPTION: Final = "monitor_exception"
TASK_STOPPED: Final = "task_stopped"

REQUIRED_KINDS: frozenset[str] = frozenset(
    {
        SALE_T_MINUS_10M,
        SALE_T_MINUS_1M,
        SALE_DUE,
        STATUS_CHANGE,
        BROWSER_LAUNCH_FAILED,
        HUMAN_TAKEOVER_NEEDED,
        MONITOR_EXCEPTION,
        TASK_STOPPED,
    }
)


def sale_reminder_kind(offset_seconds: int) -> str:
    """Map offset seconds to a stable kind string."""
    if offset_seconds <= 0:
        return SALE_DUE
    if offset_seconds == 600:
        return SALE_T_MINUS_10M
    if offset_seconds == 60:
        return SALE_T_MINUS_1M
    if offset_seconds % 60 == 0:
        return f"sale_t_minus_{offset_seconds // 60}m"
    return f"sale_t_minus_{offset_seconds}s"


def sale_reminder_title(offset_seconds: int) -> str:
    if offset_seconds <= 0:
        return "开售时间到"
    if offset_seconds == 600:
        return "开售前 10 分钟"
    if offset_seconds == 60:
        return "开售前 1 分钟"
    if offset_seconds % 60 == 0:
        return f"开售前 {offset_seconds // 60} 分钟"
    return f"开售前提醒 (-{offset_seconds}s)"
