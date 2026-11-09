"""Unified program entry: startup / shutdown lifecycle (monitor / reminder)."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

from app import __version__
from app.errors import AppError
from app.lifecycle import Application
from app.logging_config import get_logger
from app.models import ConcertTask, SortDir, SortField, parse_datetime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="damai-ticket-assistant",
        description=(
            "Damai Ticket Assistant — open-sale monitor / reminder only. "
            "Does NOT purchase tickets or bypass anti-bot controls."
        ),
    )
    parser.add_argument("--settings", type=Path, default=None)
    parser.add_argument("--database", type=Path, default=None)
    parser.add_argument("--list-tasks", action="store_true")
    parser.add_argument(
        "--search",
        type=str,
        default=None,
        help="Search by name/artist/city/status keyword",
    )
    parser.add_argument(
        "--status",
        type=str,
        default=None,
        help="Filter status: pending/watching/paused/done/cancelled",
    )
    parser.add_argument(
        "--sort-by",
        type=str,
        default="id",
        choices=["open_sale_at", "created_at", "name", "city", "status", "show_date", "id"],
    )
    parser.add_argument(
        "--sort-dir",
        type=str,
        default="asc",
        choices=["asc", "desc"],
    )
    parser.add_argument("--seed-example", action="store_true")
    parser.add_argument(
        "--seed-mock",
        type=int,
        metavar="N",
        default=None,
        help="Insert N local mock tasks (no network)",
    )
    parser.add_argument("--version", action="store_true")
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
            status="pending",
        )
        saved = app.task_service.create(task)
        logger.info("seeded task id=%s name=%s", saved.id, saved.name)
        created += 1
    print(f"seeded {created} example task(s)")
    return 0


def _seed_mock(app: Application, count: int) -> int:
    if count < 1:
        print("seed-mock N must be >= 1", file=sys.stderr)
        return 1
    logger = get_logger("main")
    cst = timezone(timedelta(hours=8))
    cities = ["Shanghai", "Beijing", "Guangzhou", "Chengdu", "Hangzhou"]
    artists = ["Mock Artist A", "Mock Artist B", "Mock Artist C", "Fixture Band"]
    statuses = ["pending", "watching", "paused"]
    created = 0
    for i in range(1, count + 1):
        show = date(2026, 12, 1) + timedelta(days=i)
        sale = datetime(2026, 11, 15, 12, 0, tzinfo=cst) + timedelta(hours=i)
        task = ConcertTask(
            name=f"Mock Concert {i:02d}",
            artist_name=artists[i % len(artists)],
            city=cities[i % len(cities)],
            official_url=f"https://detail.damai.cn/item.htm?id=mock{i}",
            show_date=show,
            session_name=f"场次{((i - 1) % 3) + 1}",
            target_price=float(280 + (i * 10)),
            target_tier=["看台", "内场", "VIP"][i % 3],
            ticket_quantity=((i - 1) % 6) + 1,
            open_sale_at=sale,
            status=statuses[i % 3],  # type: ignore[arg-type]
            note="local mock — no network",
        )
        saved = app.task_service.create(task)
        created += 1
        logger.info("mock task id=%s", saved.id)
    print(f"seeded {created} mock task(s)")
    return 0


def _print_tasks(tasks: Sequence[ConcertTask]) -> None:
    if not tasks:
        print("(no tasks)")
        return
    for task in tasks:
        print(
            f"#{task.id} [{task.status}] {task.name} | artist={task.artist_name or '-'} | "
            f"city={task.city or '-'} | show={task.show_date or '-'} | "
            f"session={task.session_name or '-'} | "
            f"price={task.target_price if task.target_price is not None else '-'} | "
            f"tier={task.target_tier or '-'} | qty={task.ticket_quantity or '-'} | "
            f"sale={task.open_sale_at.isoformat() if task.open_sale_at else '-'} | "
            f"url={task.official_url or '-'}"
        )


def _list_or_search(app: Application, args: argparse.Namespace) -> int:
    sort_by: SortField = args.sort_by
    sort_dir: SortDir = args.sort_dir
    tasks = app.task_service.search(
        query=args.search,
        status=args.status,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    _print_tasks(tasks)
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
            if args.seed_mock is not None:
                return _seed_mock(app, args.seed_mock)
            if args.list_tasks or args.search is not None or args.status is not None:
                return _list_or_search(app, args)

            count = app.task_service.count()
            print(f"  tasks in database: {count}")
            print("  startup OK — task CRUD ready (phase 5)")
            logger.info("startup smoke OK task_count=%s", count)
            return 0
    except AppError as exc:
        print(f"error [{exc.code}]: {exc.user_message}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"unexpected error: {exc}", file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
