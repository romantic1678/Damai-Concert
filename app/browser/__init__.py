"""Browser assist package (Playwright) — human-first, no purchase automation.

See ``app.browser.assist`` module docstring for hard security limits.
"""

from app.browser.assist import BrowserAssist, BrowserSessionInfo
from app.browser.status import BrowserConnectionStatus, BrowserStatusEvent, StatusHub
from app.browser.takeover import HumanTakeoverService, TakeoverState

__all__ = [
    "BrowserAssist",
    "BrowserSessionInfo",
    "BrowserConnectionStatus",
    "BrowserStatusEvent",
    "StatusHub",
    "HumanTakeoverService",
    "TakeoverState",
]
