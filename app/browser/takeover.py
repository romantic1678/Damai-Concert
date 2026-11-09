"""Human takeover state machine."""

from __future__ import annotations

from enum import Enum


class TakeoverState(str, Enum):
    IDLE = "idle"
    BROWSER_ASSIST = "browser_assist"
    HUMAN_ACTIVE = "human_active"


class HumanTakeoverService:
    """Tracks per-task takeover; when HUMAN_ACTIVE, BrowserAssist must not auto-navigate."""

    def __init__(self) -> None:
        self._states: dict[int, TakeoverState] = {}

    def state(self, task_id: int) -> TakeoverState:
        return self._states.get(task_id, TakeoverState.IDLE)

    def mark_assist(self, task_id: int) -> TakeoverState:
        self._states[task_id] = TakeoverState.BROWSER_ASSIST
        return self._states[task_id]

    def request_takeover(self, task_id: int) -> TakeoverState:
        self._states[task_id] = TakeoverState.HUMAN_ACTIVE
        return self._states[task_id]

    def release(self, task_id: int) -> TakeoverState:
        self._states[task_id] = TakeoverState.IDLE
        return self._states[task_id]

    def clear(self, task_id: int) -> None:
        self._states.pop(task_id, None)

    def automation_allowed(self, task_id: int) -> bool:
        return self.state(task_id) != TakeoverState.HUMAN_ACTIVE
