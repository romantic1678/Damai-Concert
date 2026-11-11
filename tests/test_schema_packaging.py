"""schema.sql must be resolvable in source checkouts and frozen builds."""

from __future__ import annotations

import sys
from pathlib import Path

from app import __version__
from app.storage.database import schema_sql_path


def test_version_is_0_11_1() -> None:
    assert __version__ == "0.11.1"


def test_schema_sql_path_source_checkout() -> None:
    path = schema_sql_path()
    assert path.name == "schema.sql"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "CREATE TABLE" in text
    assert "concert_tasks" in text


def test_schema_sql_path_resolves_via_meipass(tmp_path: Path, monkeypatch) -> None:
    bundled = tmp_path / "app" / "storage" / "schema.sql"
    bundled.parent.mkdir(parents=True)
    bundled.write_text("-- frozen bundle\nCREATE TABLE concert_tasks (id INTEGER);\n", encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    resolved = schema_sql_path()
    assert resolved == bundled
    assert resolved.is_file()


def test_pyinstaller_spec_bundles_schema_sql() -> None:
    root = Path(__file__).resolve().parents[1]
    spec = (root / "DamaiTicketAssistant.spec").read_text(encoding="utf-8")
    assert '("app/storage/schema.sql", "app/storage")' in spec
