"""Logging setup: rotating file + optional console."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import LoggingSettings, Settings

_CONFIGURED = False


def setup_logging(settings: Settings | LoggingSettings, *, force: bool = False) -> logging.Logger:
    """Configure root logger for damai.* modules. Idempotent unless force=True."""
    global _CONFIGURED
    log_settings = settings.logging if isinstance(settings, Settings) else settings
    root = logging.getLogger()
    if _CONFIGURED and not force:
        return logging.getLogger("damai")

    if force:
        for handler in list(root.handlers):
            root.removeHandler(handler)
            handler.close()

    level = getattr(logging, log_settings.level.upper(), logging.INFO)
    root.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log_path = (
        settings.log_file_path
        if isinstance(settings, Settings)
        else Path(log_settings.file)
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=log_settings.max_bytes,
        backupCount=log_settings.backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    root.addHandler(file_handler)

    if log_settings.console:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console.setLevel(level)
        root.addHandler(console)

    _CONFIGURED = True
    logger = logging.getLogger("damai")
    logger.debug("logging configured -> %s", log_path)
    return logger


def get_logger(name: str = "damai") -> logging.Logger:
    if not name.startswith("damai"):
        name = f"damai.{name}"
    return logging.getLogger(name)
