"""Always-on logging notification channel."""

from __future__ import annotations

from app.logging_config import get_logger

logger = get_logger("notify.channel")


class LoggingNotifier:
    name = "logging"

    def send(self, title: str, message: str, *, urgent: bool = False) -> bool:
        level = logger.warning if urgent else logger.info
        level("NOTIFY %s | %s", title, message)
        return True
