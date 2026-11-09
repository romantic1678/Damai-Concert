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
    parser.add_argument(
        "--scheduler-demo",
        action="store_true",
        help="Demo countdown reminders + mock status monitor (local fixtures only)",
    )
    parser.add_argument(
        "--test-notify",
        action="store_true",
        help="Send a test notification through all configured channels",
    )
    parser.add_argument(
        "--browser-demo",
        action="store_true",
        help="Open local mock ticket page with Playwright (no Damai network)",
    )
    parser.add_argument(
        "--open-url",
        type=str,
        default=None,
        help="Open an allowlisted (or localhost) URL via Playwright assist",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser demo headed (default headless for CI/demo stability)",
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


def _scheduler_demo(app: Application) -> int:
    """Local mock demo: countdown snapshots + reminder fire + fixture status diff."""
    from datetime import timedelta
    from pathlib import Path

    from app.models import ConcertTask
    from app.services.monitor import FixtureStatusFetcher
    from app.timeutil import wall_now

    fixtures = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "status"
    now = wall_now(app.settings.monitor.timezone)
    sale = now + timedelta(minutes=15)
    task = app.task_service.create(
        ConcertTask(
            name="Demo Countdown Show",
            artist_name="Demo Artist",
            city="Shanghai",
            official_url="https://detail.damai.cn/item.htm?id=demo",
            open_sale_at=sale,
            status="watching",
            monitor_enabled=True,
            ticket_quantity=2,
            target_price=580,
            target_tier="看台",
        )
    )
    assert task.id is not None
    snap = app.countdown.snapshot(task.id)
    print(f"countdown: remaining={snap.remaining_seconds:.1f}s phase={snap.phase}")

    # Swap in fixture fetcher for demo (still no network)
    fetcher = FixtureStatusFetcher({task.id: fixtures / "pre_sale.html"})
    app.monitor._fetcher = fetcher  # noqa: SLF001
    base = app.monitor.establish_baseline(task.id)
    print(f"baseline status={base.normalized_status}")
    fetcher.set_path(task.id, fixtures / "on_sale.html")
    diff = app.monitor.poll_once(task.id)
    print(
        f"diff notify={diff.should_notify} "
        f"{diff.previous.normalized_status if diff.previous else None} -> {diff.current.normalized_status}"
    )

    # Fire reminder handlers idempotently (simulate T-10 without waiting)
    app.runtime._record_job(task.id, f"remind:{task.id}:600", "countdown_offset", status="scheduled")
    once = app.runtime.fire_reminder(task.id, 600)
    twice = app.runtime.fire_reminder(task.id, 600)
    print(f"reminder T-10 first={once} second={twice} events={len(app.notifier.events)}")
    print("scheduler demo OK (mock only — no Damai network)")
    return 0



def _test_notify(app: Application) -> int:
    """Fire a force test notification (bypasses dedupe) across channels."""
    from app.notify.kinds import REQUIRED_KINDS

    event = app.notifier.notify(
        "测试通知",
        "Damai Ticket Assistant test notify — monitor/reminder only.",
        kind="test_notify",
        urgent=True,
        dedupe_key="test_notify:manual",
        force=True,
    )
    print(f"test notify delivered={event.delivered} channels_registered={len(app.notifier._notifiers)}")  # noqa: SLF001
    print(f"gui queue size={len(app.gui_sink.peek())}")
    print(f"known kinds sample={sorted(REQUIRED_KINDS)[:3]}...")
    print("test-notify OK")
    return 0



def _browser_demo(app: Application, *, headed: bool = False) -> int:
    """Local mock Playwright demo — never contacts Damai."""
    from pathlib import Path

    from app.browser.mock_server import MockBrowserServer
    from app.browser.status import BrowserConnectionStatus

    fixtures = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "browser"
    server = MockBrowserServer(fixtures)
    server.start()
    try:
        # Recreate assist headless flag for demo
        app.browser._headless = not headed  # noqa: SLF001
        url = server.url("ok.html")
        info = app.browser.open_official_page(1, url, headless=not headed)
        print(f"opened {info.official_url} status={info.status.value}")
        # Navigate to verify page → should request human takeover
        verify = server.url("verify.html")
        app.browser.navigate(verify, task_id=1)
        print(f"after verify status={app.browser.connection_status.value}")
        assert app.browser.connection_status in {
            BrowserConnectionStatus.HUMAN_TAKEOVER,
            BrowserConnectionStatus.PAGE_READY,
            BrowserConnectionStatus.PAGE_ERROR,
        }
        app.browser.pause(1)
        print(f"paused status={app.browser.connection_status.value}")
        app.browser.close(1)
        print("browser-demo OK (mock only)")
        return 0
    finally:
        try:
            app.browser.close()
        except Exception:
            pass
        server.stop()


def _open_url(app: Application, url: str, *, headed: bool = False) -> int:
    info = app.browser.open_official_page(0, url, headless=not headed)
    print(f"opened {info.official_url} status={info.status.value}")
    print("Leave the window for manual use, then Ctrl+C / close. (No auto-checkout.)")
    app.browser.close(0)
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
            browser_headless=not args.headed,
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
            if args.scheduler_demo:
                return _scheduler_demo(app)
            if args.test_notify:
                return _test_notify(app)
            if args.browser_demo:
                return _browser_demo(app, headed=args.headed)
            if args.open_url:
                return _open_url(app, args.open_url, headed=args.headed)

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
