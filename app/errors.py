"""Application exception hierarchy."""

from __future__ import annotations


class AppError(Exception):
    """Base class for expected application errors."""

    def __init__(self, user_message: str, *, code: str = "app_error") -> None:
        self.user_message = user_message
        self.code = code
        super().__init__(user_message)


class ConfigError(AppError):
    def __init__(self, user_message: str, *, code: str = "config_error") -> None:
        super().__init__(user_message, code=code)


class ValidationError(AppError):
    def __init__(self, user_message: str, *, code: str = "validation_error") -> None:
        super().__init__(user_message, code=code)


class StorageError(AppError):
    def __init__(self, user_message: str, *, code: str = "storage_error") -> None:
        super().__init__(user_message, code=code)


class NotFoundError(AppError):
    def __init__(self, user_message: str, *, code: str = "not_found") -> None:
        super().__init__(user_message, code=code)


class MonitorFetchError(AppError):
    def __init__(self, user_message: str, *, code: str = "monitor_fetch_error") -> None:
        super().__init__(user_message, code=code)


class BrowserAssistError(AppError):
    def __init__(self, user_message: str, *, code: str = "browser_assist_error") -> None:
        super().__init__(user_message, code=code)


class ScheduleError(AppError):
    def __init__(self, user_message: str, *, code: str = "schedule_error") -> None:
        super().__init__(user_message, code=code)


class NotifyError(AppError):
    def __init__(self, user_message: str, *, code: str = "notify_error") -> None:
        super().__init__(user_message, code=code)
