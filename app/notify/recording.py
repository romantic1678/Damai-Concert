"""In-memory notifier for unit tests."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RecordingNotifier:
    name: str = "recording"
    messages: list[tuple[str, str, bool]] = field(default_factory=list)

    def send(self, title: str, message: str, *, urgent: bool = False) -> bool:
        self.messages.append((title, message, urgent))
        return True
