"""SQLite connection, migrations, and helpers."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterator

from app.errors import StorageError
from app.logging_config import get_logger

logger = get_logger("storage")

SCHEMA_VERSION = 1
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# Asia/Shanghai for migration timestamps
_CST = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(_CST).isoformat()


class Database:
    """Thread-aware SQLite wrapper with light migrations."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise StorageError("database is not connected")
        return self._conn

    def connect(self) -> None:
        with self._lock:
            if self._conn is not None:
                return
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(
                    self.path,
                    check_same_thread=False,
                    detect_types=sqlite3.PARSE_DECLTYPES,
                )
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA journal_mode = WAL")
                self._conn = conn
                logger.info("connected to sqlite at %s", self.path)
            except sqlite3.Error as exc:
                raise StorageError(f"failed to open database: {exc}") from exc

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
                logger.info("database closed")

    def migrate(self) -> None:
        """Apply schema version 1 if not yet applied."""
        with self._lock:
            conn = self.connection
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                      version INTEGER PRIMARY KEY,
                      applied_at TEXT NOT NULL
                    )
                    """
                )
                row = conn.execute(
                    "SELECT MAX(version) AS v FROM schema_migrations"
                ).fetchone()
                current = int(row["v"] or 0) if row else 0
                if current >= SCHEMA_VERSION:
                    logger.debug("schema already at version %s", current)
                    return
                if not SCHEMA_PATH.is_file():
                    raise StorageError(f"schema file missing: {SCHEMA_PATH}")
                sql = SCHEMA_PATH.read_text(encoding="utf-8")
                conn.executescript(sql)
                conn.execute(
                    "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, _now_iso()),
                )
                # Ensure version row even if schema.sql created empty migrations
                exists = conn.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = ?",
                    (SCHEMA_VERSION,),
                ).fetchone()
                if not exists:
                    conn.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                        (SCHEMA_VERSION, _now_iso()),
                    )
                conn.commit()
                logger.info("applied schema migration to v%s", SCHEMA_VERSION)
            except sqlite3.Error as exc:
                conn.rollback()
                raise StorageError(f"migration failed: {exc}") from exc

    def execute(self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            try:
                cur = self.connection.execute(sql, params)
                self.connection.commit()
                return cur
            except sqlite3.Error as exc:
                self.connection.rollback()
                raise StorageError(f"sql error: {exc}") from exc

    def executemany(self, sql: str, seq: list[tuple[Any, ...]]) -> None:
        with self._lock:
            try:
                self.connection.executemany(sql, seq)
                self.connection.commit()
            except sqlite3.Error as exc:
                self.connection.rollback()
                raise StorageError(f"sql error: {exc}") from exc

    def fetchone(self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            try:
                return self.connection.execute(sql, params).fetchone()
            except sqlite3.Error as exc:
                raise StorageError(f"sql error: {exc}") from exc

    def fetchall(self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            try:
                return list(self.connection.execute(sql, params).fetchall())
            except sqlite3.Error as exc:
                raise StorageError(f"sql error: {exc}") from exc

    def tables(self) -> list[str]:
        rows = self.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [str(r["name"]) for r in rows]
