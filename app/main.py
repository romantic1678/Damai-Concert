"""Unified program entry: startup / shutdown lifecycle (monitor / reminder)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app import __version__
from app.errors import AppError
from app.lifecycle import Application
from app.logging_config import get_logger
from app.models import ConcertTask, parse_datetime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="damai-ticket-assistant",
        description=(
            "Damai Ticket Assistant — open-sale monitor / reminder only. "
            "Does NOT purchase tickets or bypass anti-bot controls."
        ),
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=None,
        help="Path to settings.yaml (default: config/settings.yaml)",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help="Override SQLite database path",
    )
    parser.add_argument(
        "--list-tasks",
        action="store_true",
        help="List concert tasks and exit",
    )
    parser.add_argument(
        "--seed-example",
        action="store_true",
        help="Insert placeholder events from settings into the database",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version and exit",
    )
    return parser


def _seed_examples(app: Application) -> int:
    logger = get_logger("main")
    created = 0
    for event in app.settings.events:
        if not event.name:
            continue
        task = ConcertTask(
            name=event.name,
            city=event.city,
            open_sale_at=parse_datetime(event.open_sale_at),
            note=event.note,
            monitor_enabled=False,
        )
        saved = app.task_service.create(task)
        logger.info("seeded task id=%s name=%s", saved.id, saved.name)
        created += 1
    print(f"seeded {created} example task(s)")
    return 0


def _list_tasks(app: Application) -> int:
    tasks = app.task_service.list_all()
    if not tasks:
        print("(no tasks)")
        return 0
    for task in tasks:
        print(
            f"#{task.id} {task.name} | city={task.city or '-'} | "
            f"sale={task.open_sale_at.isoformat() if task.open_sale_at else '-'} | "
            f"monitor={task.monitor_enabled}"
        )
    return 0


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    try:
        with Application.create(
            settings_path=args.settings,
            database_path=args.database,
        ) as app:
            logger = get_logger("main")
            print("=" * 56)
            print(f"  {app.settings.app.name}")
            print("  mode: monitor / reminder (NO auto-purchase)")
            print(f"  version: {__version__}")
            print(f"  Python: {sys.version.split()[0]}")
            print(f"  database: {app.database.path}")
            print("=" * 56)

            if args.seed_example:
                return _seed_examples(app)
            if args.list_tasks:
                return _list_tasks(app)

            # Default: smoke start/stop after init
            count = len(app.task_service.list_all())
            print(f"  tasks in database: {count}")
            print("  startup OK — foundation ready (phase 4)")
            logger.info("startup smoke OK task_count=%s", count)
            return 0
    except AppError as exc:
        print(f"error [{exc.code}]: {exc.user_message}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — top-level guard
        print(f"unexpected error: {exc}", file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
