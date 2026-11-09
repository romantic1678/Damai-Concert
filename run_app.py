#!/usr/bin/env python3
"""PyInstaller / desktop entrypoint.

Frozen builds default to ``--gui`` when no CLI args are provided.
Monitor / reminder only — never auto-purchase.
"""

from __future__ import annotations

import sys

from app.paths import ensure_playwright_env, is_frozen


def main() -> int:
    ensure_playwright_env()
    argv = list(sys.argv[1:])
    if is_frozen() and not argv:
        argv = ["--gui"]
    from app.main import main as app_main

    return int(app_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
