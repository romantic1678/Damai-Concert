"""Console notifier."""

from __future__ import annotations


class ConsoleNotifier:
    name = "console"

    def send(self, title: str, message: str, *, urgent: bool = False) -> bool:
        prefix = "!" if urgent else "-"
        print(f"[notify{prefix}] {title}: {message}")
        return True
