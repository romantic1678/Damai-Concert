"""Minimal CLI entrypoint for Damai Ticket Assistant (monitor / reminder mode)."""

from __future__ import annotations

import sys
from pathlib import Path


def _load_example_event_name() -> str | None:
    """Optionally read one key from the example YAML if PyYAML is available."""
    try:
        import yaml
    except ImportError:
        return None

    config_path = Path(__file__).resolve().parent.parent / "config" / "settings.example.yaml"
    if not config_path.is_file():
        return None
    with config_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    events = data.get("events") or []
    if not events:
        return None
    return events[0].get("name")


def main() -> int:
    print("=" * 56)
    print("  Damai Ticket Assistant")
    print("  mode: monitor / reminder (NO auto-purchase)")
    print(f"  Python: {sys.version.split()[0]}")
    print("=" * 56)
    event_name = _load_example_event_name()
    if event_name:
        print(f"  example event: {event_name}")
    else:
        print("  example event: (config not loaded)")
    print("  startup OK — scaffold phase only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
