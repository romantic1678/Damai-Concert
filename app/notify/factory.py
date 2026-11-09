"""Build NotifierService from settings."""

from __future__ import annotations

from app.config import NotifySettings, Settings
from app.notify.base import NotifierService
from app.notify.console import ConsoleNotifier
from app.notify.dedupe import NotificationDedupeStore
from app.notify.desktop import DesktopNotifier
from app.notify.gui_sink import QueueGuiSink
from app.notify.logging_channel import LoggingNotifier
from app.notify.sound import SoundNotifier
from app.storage.database import Database


def build_notifier_service(
    settings: Settings,
    database: Database,
    *,
    gui_sink: QueueGuiSink | None = None,
) -> tuple[NotifierService, QueueGuiSink]:
    notify_cfg: NotifySettings = settings.notify
    service = NotifierService(
        database=database,
        dedupe=NotificationDedupeStore(database),
    )
    # Logging always on
    service.register(LoggingNotifier())

    channels = {c.lower() for c in notify_cfg.channels}
    if "console" in channels:
        service.register(ConsoleNotifier())
    if "desktop" in channels or notify_cfg.desktop_enabled:
        service.register(
            DesktopNotifier(
                app_name=settings.app.name,
                enabled=notify_cfg.desktop_enabled,
            )
        )
    if "sound" in channels or notify_cfg.sound_enabled:
        # Sound channel registered but respects sound_enabled flag internally
        service.register(SoundNotifier(enabled=notify_cfg.sound_enabled))

    sink = gui_sink or QueueGuiSink()
    if "gui" in channels or notify_cfg.gui_enabled:
        service.register(sink)  # type: ignore[arg-type]

    return service, sink
