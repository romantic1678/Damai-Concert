"""Desktop notification channel (Windows-oriented; graceful no-op elsewhere)."""

from __future__ import annotations

from app.logging_config import get_logger

logger = get_logger("notify.desktop")


class DesktopNotifier:
    """Best-effort OS notification via plyer; never raises to callers."""

    name = "desktop"

    def __init__(self, *, app_name: str = "Damai Ticket Assistant", enabled: bool = True) -> None:
        self._app_name = app_name
        self._enabled = enabled

    def send(self, title: str, message: str, *, urgent: bool = False) -> bool:
        if not self._enabled:
            return False
        try:
            from plyer import notification

            notification.notify(
                title=title,
                message=message,
                app_name=self._app_name,
                timeout=8 if not urgent else 15,
            )
            return True
        except Exception as exc:  # noqa: BLE001 — headless / missing backend
            logger.debug("desktop notify unavailable: %s", exc)
            return False
