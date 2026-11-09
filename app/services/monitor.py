"""Public sale-status monitoring: baseline → fetch → diff → notify.

Never guesses in-stock / sold-out when parsing fails — returns ``unknown``.
Fetchers are injectable; production must not use high-frequency polling or
bypass access controls. Tests use local fixtures only.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Protocol

from app.errors import MonitorFetchError, ValidationError
from app.logging_config import get_logger
from app.models import ConcertTask, NormalizedStatus, dt_to_iso
from app.services.task_service import TaskService
from app.storage.database import Database
from app.timeutil import ensure_aware, wall_now

logger = get_logger("services.monitor")

_EXCERPT_LIMIT = 4096

# Conservative keyword map for *local fixtures / public HTML snippets only*.
_STATUS_PATTERNS: list[tuple[NormalizedStatus, re.Pattern[str]]] = [
    ("on_sale", re.compile(r"立即购买|热卖|on[_-]?sale|在售", re.I)),
    ("sold_out", re.compile(r"售罄|缺货|sold[_-]?out", re.I)),
    ("pre_sale", re.compile(r"即将开售|预售|pre[_-]?sale", re.I)),
    ("off_sale", re.compile(r"已结束|停售|off[_-]?sale", re.I)),
]


@dataclass(frozen=True, slots=True)
class FetchResult:
    source_url: str
    body: str
    content_type: str = "text/html"


@dataclass(frozen=True, slots=True)
class SaleStatusSnapshot:
    task_id: int
    fetched_at: datetime
    source_url: str
    raw_excerpt: str
    normalized_status: NormalizedStatus
    content_hash: str
    id: int | None = None
    is_baseline: bool = False


@dataclass(frozen=True, slots=True)
class StatusDiff:
    task_id: int
    previous: SaleStatusSnapshot | None
    current: SaleStatusSnapshot
    changed_fields: tuple[str, ...]
    should_notify: bool


class PublicStatusFetcher(Protocol):
    def fetch(self, task: ConcertTask) -> FetchResult: ...


class FixtureStatusFetcher:
    """Read local HTML/JSON fixtures — never touches the network."""

    def __init__(self, mapping: dict[int, Path] | None = None, default: Path | None = None) -> None:
        self._mapping = mapping or {}
        self._default = default

    def set_path(self, task_id: int, path: Path) -> None:
        self._mapping[task_id] = path

    def fetch(self, task: ConcertTask) -> FetchResult:
        if task.id is None:
            raise MonitorFetchError("task id required")
        path = self._mapping.get(task.id, self._default)
        if path is None or not path.is_file():
            raise MonitorFetchError(f"no fixture for task {task.id}")
        body = path.read_text(encoding="utf-8")
        ctype = "application/json" if path.suffix.lower() == ".json" else "text/html"
        url = task.official_url or f"fixture://{path.name}"
        return FetchResult(source_url=url, body=body, content_type=ctype)


class RejectNetworkFetcher:
    """Fail closed if anything tries to hit the network in tests."""

    def fetch(self, task: ConcertTask) -> FetchResult:
        raise MonitorFetchError("network fetch disabled (tests / safe mode)")


def parse_public_status(body: str, content_type: str = "text/html") -> tuple[NormalizedStatus, str]:
    """Parse public snippet. Returns unknown when unreliable — never invents stock."""
    excerpt = body.strip()[:_EXCERPT_LIMIT]
    if not excerpt:
        return "unknown", excerpt

    if "json" in content_type.lower():
        try:
            data = json.loads(excerpt)
        except json.JSONDecodeError:
            return "unknown", excerpt
        raw = str(data.get("saleStatus") or data.get("status") or "").strip().lower()
        mapping = {
            "pre_sale": "pre_sale",
            "presale": "pre_sale",
            "on_sale": "on_sale",
            "onsale": "on_sale",
            "sold_out": "sold_out",
            "soldout": "sold_out",
            "off_sale": "off_sale",
            "unknown": "unknown",
        }
        status = mapping.get(raw, "unknown")
        return status, excerpt  # type: ignore[return-value]

    # data-status attribute preferred
    m = re.search(r'data-status=["\']([a-z_]+)["\']', excerpt, re.I)
    if m:
        token = m.group(1).lower()
        if token in {"unknown", "pre_sale", "on_sale", "sold_out", "off_sale"}:
            return token, excerpt  # type: ignore[return-value]

    for status, pattern in _STATUS_PATTERNS:
        if pattern.search(excerpt):
            return status, excerpt
    return "unknown", excerpt


def content_hash(excerpt: str, status: str) -> str:
    payload = f"{status}\n{excerpt}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class MonitorService:
    def __init__(
        self,
        database: Database,
        task_service: TaskService,
        fetcher: PublicStatusFetcher,
        *,
        min_poll_interval_seconds: int = 60,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if min_poll_interval_seconds < 60:
            raise ValidationError("min_poll_interval_seconds must be >= 60")
        self._db = database
        self._tasks = task_service
        self._fetcher = fetcher
        self._min_interval = min_poll_interval_seconds
        self._clock = clock or wall_now

    def min_poll_interval_seconds(self) -> int:
        return self._min_interval

    def _row_to_snapshot(self, row: object, *, is_baseline: bool = False) -> SaleStatusSnapshot:
        r = row  # sqlite3.Row
        return SaleStatusSnapshot(
            id=int(r["id"]) if "id" in r.keys() and r["id"] is not None else None,  # type: ignore[index]
            task_id=int(r["task_id"]),  # type: ignore[index]
            fetched_at=ensure_aware(
                datetime.fromisoformat(str(r["fetched_at"]))  # type: ignore[index]
            ),
            source_url=str(r["source_url"]),  # type: ignore[index]
            raw_excerpt=str(r["raw_excerpt"]),  # type: ignore[index]
            normalized_status=r["normalized_status"],  # type: ignore[index]
            content_hash=str(r["content_hash"]),  # type: ignore[index]
            is_baseline=bool(r["is_baseline"]) if "is_baseline" in r.keys() else is_baseline,  # type: ignore[index]
        )

    def _latest_snapshot(self, task_id: int) -> SaleStatusSnapshot | None:
        row = self._db.fetchone(
            "SELECT * FROM sale_snapshots WHERE task_id = ? ORDER BY fetched_at DESC, id DESC LIMIT 1",
            (task_id,),
        )
        return self._row_to_snapshot(row) if row else None

    def _insert_snapshot(self, snap: SaleStatusSnapshot) -> SaleStatusSnapshot:
        cur = self._db.execute(
            """
            INSERT INTO sale_snapshots (
              task_id, fetched_at, source_url, raw_excerpt,
              normalized_status, content_hash, is_baseline
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snap.task_id,
                dt_to_iso(snap.fetched_at),
                snap.source_url,
                snap.raw_excerpt,
                snap.normalized_status,
                snap.content_hash,
                1 if snap.is_baseline else 0,
            ),
        )
        return SaleStatusSnapshot(
            id=int(cur.lastrowid),
            task_id=snap.task_id,
            fetched_at=snap.fetched_at,
            source_url=snap.source_url,
            raw_excerpt=snap.raw_excerpt,
            normalized_status=snap.normalized_status,
            content_hash=snap.content_hash,
            is_baseline=snap.is_baseline,
        )

    def _upsert_baseline(self, snap: SaleStatusSnapshot) -> None:
        self._db.execute(
            """
            INSERT INTO status_baselines (
              task_id, established_at, normalized_status, content_hash, raw_excerpt
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
              established_at=excluded.established_at,
              normalized_status=excluded.normalized_status,
              content_hash=excluded.content_hash,
              raw_excerpt=excluded.raw_excerpt
            """,
            (
                snap.task_id,
                dt_to_iso(snap.fetched_at),
                snap.normalized_status,
                snap.content_hash,
                snap.raw_excerpt,
            ),
        )

    def _build_snapshot(self, task: ConcertTask, *, is_baseline: bool) -> SaleStatusSnapshot:
        assert task.id is not None
        try:
            result = self._fetcher.fetch(task)
            status, excerpt = parse_public_status(result.body, result.content_type)
            source_url = result.source_url
        except MonitorFetchError as exc:
            logger.warning("fetch failed task=%s: %s → unknown", task.id, exc.user_message)
            status = "unknown"
            excerpt = f"fetch_error: {exc.user_message}"
            source_url = task.official_url or "fetch://error"
        except Exception as exc:  # noqa: BLE001
            logger.exception("unexpected fetch error task=%s", task.id)
            status = "unknown"
            excerpt = f"fetch_error: {exc}"
            source_url = task.official_url or "fetch://error"

        fetched_at = ensure_aware(self._clock())
        return SaleStatusSnapshot(
            task_id=int(task.id),
            fetched_at=fetched_at,
            source_url=source_url,
            raw_excerpt=excerpt[:_EXCERPT_LIMIT],
            normalized_status=status,  # type: ignore[arg-type]
            content_hash=content_hash(excerpt, status),
            is_baseline=is_baseline,
        )

    def establish_baseline(self, task_id: int) -> SaleStatusSnapshot:
        task = self._tasks.require(task_id)
        snap = self._build_snapshot(task, is_baseline=True)
        saved = self._insert_snapshot(snap)
        self._upsert_baseline(saved)
        logger.info("baseline task=%s status=%s", task_id, saved.normalized_status)
        return saved

    def poll_once(self, task_id: int) -> StatusDiff:
        task = self._tasks.require(task_id)
        previous = self._latest_snapshot(task_id)
        if previous is None:
            current = self.establish_baseline(task_id)
            return StatusDiff(
                task_id=task_id,
                previous=None,
                current=current,
                changed_fields=(),
                should_notify=False,
            )

        current = self._insert_snapshot(self._build_snapshot(task, is_baseline=False))
        changed: list[str] = []
        if current.normalized_status != previous.normalized_status:
            changed.append("normalized_status")
        if current.content_hash != previous.content_hash:
            changed.append("content_hash")
        # Baseline round already handled; notify only on real status change
        should_notify = "normalized_status" in changed
        return StatusDiff(
            task_id=task_id,
            previous=previous,
            current=current,
            changed_fields=tuple(changed),
            should_notify=should_notify,
        )

