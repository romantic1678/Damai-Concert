"""Playwright browser assist — open official pages and yield control to humans.

Hard limits (must never be violated)
------------------------------------
* NO captcha solve / bypass
* NO queue jump
* NO stealth / fingerprint spoofing
* NO anti-bot evasion
* NO unauthorized internal APIs
* NO auto payment / checkout submit
* NEVER collect or store user credentials (password fields are user-typed only)

Priority: browser stability + human takeover. After launch + goto official URL,
the user operates the browser manually.
"""

from __future__ import annotations

import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse

from app.browser.heuristics import (
    looks_blank,
    looks_http_error_page,
    needs_human_verification,
)
from app.browser.status import BrowserConnectionStatus, StatusHub
from app.browser.takeover import HumanTakeoverService, TakeoverState
from app.errors import BrowserAssistError, ValidationError
from app.logging_config import get_logger
from app.models import validate_official_url
from app.notify.base import NotifierService
from app.services.runtime import TaskRuntime
from app.timeutil import wall_now

logger = get_logger("browser.assist")


@dataclass(frozen=True, slots=True)
class BrowserSessionInfo:
    task_id: int
    official_url: str
    launched_at: datetime
    headless: bool
    status: BrowserConnectionStatus


class BrowserAssist:
    """Launch Chromium, open allowlisted official URL, then leave control to the user."""

    def __init__(
        self,
        *,
        url_allowlist: Sequence[str],
        notifier: NotifierService | None = None,
        runtime: TaskRuntime | None = None,
        takeover: HumanTakeoverService | None = None,
        status_hub: StatusHub | None = None,
        user_data_dir: Path | None = None,
        headless: bool = False,
        navigation_timeout_ms: int = 30_000,
    ) -> None:
        self._allowlist = tuple(url_allowlist)
        self._notifier = notifier
        self._runtime = runtime
        self._takeover = takeover or HumanTakeoverService()
        self.status = status_hub or StatusHub()
        self._user_data_dir = user_data_dir
        self._headless = headless
        self._timeout = navigation_timeout_ms

        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._task_id: int | None = None
        self._url: str | None = None
        self._paused = False

    @property
    def takeover(self) -> HumanTakeoverService:
        return self._takeover

    @property
    def connection_status(self) -> BrowserConnectionStatus:
        return self.status.status

    def _validate_url(self, url: str) -> str:
        # Allow localhost for mock demos/tests in addition to configured allowlist
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if host in {"127.0.0.1", "localhost"} and parsed.scheme in {"http", "https"}:
            return url
        validated = validate_official_url(url, self._allowlist, required=True)
        assert validated is not None
        return validated

    def _host_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if host in {"127.0.0.1", "localhost"}:
            return True
        try:
            validate_official_url(url, self._allowlist, required=True)
            return True
        except ValidationError:
            return False

    def open_official_page(
        self,
        task_id: int,
        url: str,
        *,
        headless: bool | None = None,
    ) -> BrowserSessionInfo:
        """Start browser (if needed) and navigate to the official URL."""
        use_headless = self._headless if headless is None else headless
        launched_at = wall_now()
        try:
            safe_url = self._validate_url(url)
        except ValidationError as exc:
            self._on_launch_failed(task_id, str(exc.user_message))
            raise BrowserAssistError(exc.user_message) from exc

        self.status.set(
            BrowserConnectionStatus.LAUNCHING,
            task_id=task_id,
            detail="launching chromium",
            url=safe_url,
        )
        try:
            self._ensure_browser(headless=use_headless)
            assert self._page is not None
            self._task_id = task_id
            self._url = safe_url
            self._takeover.mark_assist(task_id)
            self._paused = False
            self.status.set(
                BrowserConnectionStatus.NAVIGATING,
                task_id=task_id,
                detail="goto official url",
                url=safe_url,
            )
            response = self._page.goto(
                safe_url,
                wait_until="domcontentloaded",
                timeout=self._timeout,
            )
            if response is not None and response.status >= 400:
                self._handle_page_anomaly(
                    task_id,
                    f"HTTP {response.status} loading {safe_url}",
                    url=safe_url,
                )
            else:
                self._inspect_page(task_id, safe_url)
            return BrowserSessionInfo(
                task_id=task_id,
                official_url=safe_url,
                launched_at=launched_at,
                headless=use_headless,
                status=self.status.status,
            )
        except BrowserAssistError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("open_official_page failed task=%s", task_id)
            self._on_launch_failed(task_id, str(exc))
            # Best-effort system browser fallback (still no automation)
            try:
                webbrowser.open(url)
            except Exception:  # noqa: BLE001
                pass
            raise BrowserAssistError(f"browser launch/navigation failed: {exc}") from exc

    def _ensure_browser(self, *, headless: bool) -> None:
        if self._page is not None and not self._page.is_closed():
            return
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        launch_args: dict = {
            "headless": headless,
            # No stealth flags — intentionally stock Chromium.
        }
        browser_type = self._playwright.chromium
        if self._user_data_dir is not None:
            self._user_data_dir.mkdir(parents=True, exist_ok=True)
            self._context = browser_type.launch_persistent_context(
                str(self._user_data_dir),
                headless=headless,
            )
            self._browser = None
            self._page = (
                self._context.pages[0]
                if self._context.pages
                else self._context.new_page()
            )
        else:
            self._browser = browser_type.launch(**launch_args)
            self._context = self._browser.new_context()
            self._page = self._context.new_page()
        self.status.set(BrowserConnectionStatus.CONNECTED, detail="chromium ready")

    def reload(self, task_id: int | None = None) -> None:
        tid = task_id if task_id is not None else self._task_id
        if tid is None or self._page is None:
            raise BrowserAssistError("no active browser session")
        if not self._takeover.automation_allowed(tid):
            raise BrowserAssistError("human takeover active — auto navigation blocked")
        if self._paused:
            raise BrowserAssistError("browser session paused")
        try:
            self.status.set(BrowserConnectionStatus.NAVIGATING, task_id=tid, detail="reload")
            self._page.reload(wait_until="domcontentloaded", timeout=self._timeout)
            self._inspect_page(tid, self._page.url)
        except BrowserAssistError:
            raise
        except Exception as exc:  # noqa: BLE001
            self._handle_page_anomaly(tid, f"reload failed: {exc}")
            raise BrowserAssistError(str(exc)) from exc

    def go_back(self, task_id: int | None = None) -> None:
        tid = task_id if task_id is not None else self._task_id
        if tid is None or self._page is None:
            raise BrowserAssistError("no active browser session")
        if not self._takeover.automation_allowed(tid):
            raise BrowserAssistError("human takeover active — auto navigation blocked")
        if self._paused:
            raise BrowserAssistError("browser session paused")
        try:
            self.status.set(BrowserConnectionStatus.NAVIGATING, task_id=tid, detail="back")
            response = self._page.go_back(wait_until="domcontentloaded", timeout=self._timeout)
            url = self._page.url
            if not self._host_allowed(url):
                raise BrowserAssistError(f"navigated outside allowlist: {url}")
            if response is not None and response.status >= 400:
                self._handle_page_anomaly(tid, f"HTTP {response.status} on back", url=url)
            else:
                self._inspect_page(tid, url)
        except BrowserAssistError:
            raise
        except Exception as exc:  # noqa: BLE001
            self._handle_page_anomaly(tid, f"go_back failed: {exc}")
            raise BrowserAssistError(str(exc)) from exc

    def navigate(self, url: str, task_id: int | None = None) -> None:
        """Navigate only if URL host is allowlisted (or localhost mock)."""
        tid = task_id if task_id is not None else self._task_id
        if tid is None or self._page is None:
            raise BrowserAssistError("no active browser session")
        if not self._takeover.automation_allowed(tid):
            raise BrowserAssistError("human takeover active — auto navigation blocked")
        if self._paused:
            raise BrowserAssistError("browser session paused")
        safe = self._validate_url(url)
        try:
            self.status.set(
                BrowserConnectionStatus.NAVIGATING,
                task_id=tid,
                detail="navigate",
                url=safe,
            )
            response = self._page.goto(
                safe, wait_until="domcontentloaded", timeout=self._timeout
            )
            if response is not None and response.status >= 400:
                self._handle_page_anomaly(tid, f"HTTP {response.status}", url=safe)
            else:
                self._inspect_page(tid, safe)
        except BrowserAssistError:
            raise
        except Exception as exc:  # noqa: BLE001
            self._handle_page_anomaly(tid, f"navigate failed: {exc}", url=safe)
            raise BrowserAssistError(str(exc)) from exc

    def pause(self, task_id: int | None = None) -> None:
        """Pause assist automation; user keeps the browser window."""
        tid = task_id if task_id is not None else self._task_id
        self._paused = True
        if tid is not None:
            self._takeover.request_takeover(tid)
            if self._runtime is not None:
                try:
                    self._runtime.emit_human_takeover_needed(tid, "browser paused by user")
                except Exception:  # noqa: BLE001
                    logger.exception("emit takeover on pause failed")
        self.status.set(
            BrowserConnectionStatus.PAUSED,
            task_id=tid,
            detail="assist paused — human control",
        )

    def request_human_takeover(self, task_id: int | None = None, reason: str = "") -> TakeoverState:
        tid = task_id if task_id is not None else self._task_id
        if tid is None:
            raise BrowserAssistError("no task id for takeover")
        state = self._takeover.request_takeover(tid)
        self.status.set(
            BrowserConnectionStatus.HUMAN_TAKEOVER,
            task_id=tid,
            detail=reason or "human takeover",
        )
        if self._runtime is not None:
            try:
                self._runtime.emit_human_takeover_needed(tid, reason or "manual takeover")
            except Exception:  # noqa: BLE001
                logger.exception("emit_human_takeover_needed failed")
        elif self._notifier is not None:
            try:
                self._notifier.notify(
                    "需要人工接管",
                    reason or f"task {tid}",
                    kind="human_takeover_needed",
                    task_id=tid,
                    urgent=True,
                    dedupe_key=f"human_takeover_needed:{tid}",
                )
            except Exception:  # noqa: BLE001
                logger.exception("notifier takeover failed")
        return state

    def release_takeover(self, task_id: int | None = None) -> TakeoverState:
        tid = task_id if task_id is not None else self._task_id
        if tid is None:
            return TakeoverState.IDLE
        state = self._takeover.release(tid)
        self._paused = False
        self.status.set(
            BrowserConnectionStatus.CONNECTED,
            task_id=tid,
            detail="takeover released",
        )
        return state

    def close(self, task_id: int | None = None) -> None:
        tid = task_id if task_id is not None else self._task_id
        self.status.set(BrowserConnectionStatus.CLOSING, task_id=tid, detail="closing")
        try:
            if self._context is not None:
                self._context.close()
        except Exception:  # noqa: BLE001
            logger.exception("context close error")
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:  # noqa: BLE001
            logger.exception("browser close error")
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:  # noqa: BLE001
            logger.exception("playwright stop error")
        if tid is not None:
            self._takeover.clear(tid)
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._task_id = None
        self._url = None
        self._paused = False
        self.status.set(BrowserConnectionStatus.DISCONNECTED, detail="closed")

    def current_url(self) -> str | None:
        if self._page is None or self._page.is_closed():
            return None
        try:
            return self._page.url
        except Exception:  # noqa: BLE001
            return None

    def _inspect_page(self, task_id: int, url: str) -> None:
        assert self._page is not None
        try:
            title = self._page.title()
            body = ""
            try:
                body = self._page.inner_text("body", timeout=3_000)
            except Exception:  # noqa: BLE001
                body = ""
        except Exception as exc:  # noqa: BLE001
            self._handle_page_anomaly(task_id, f"page inspect failed: {exc}", url=url)
            return

        if looks_blank(title, body):
            self._handle_page_anomaly(task_id, "blank or empty page", url=url)
            return
        if looks_http_error_page(title, body):
            self._handle_page_anomaly(task_id, "error page content detected", url=url)
            return

        reason = needs_human_verification(title, body)
        if reason:
            self.request_human_takeover(task_id, reason=reason)
            return

        self.status.set(
            BrowserConnectionStatus.PAGE_READY,
            task_id=task_id,
            detail=f"title={title[:80]}",
            url=url,
        )

    def _handle_page_anomaly(self, task_id: int, detail: str, *, url: str | None = None) -> None:
        logger.warning("page anomaly task=%s detail=%s", task_id, detail)
        self.status.set(
            BrowserConnectionStatus.PAGE_ERROR,
            task_id=task_id,
            detail=detail,
            url=url,
        )
        if self._notifier is not None:
            try:
                self._notifier.notify(
                    "页面异常",
                    f"task {task_id}: {detail}",
                    kind="browser_page_anomaly",
                    task_id=task_id,
                    urgent=True,
                    dedupe_key=f"browser_page_anomaly:{task_id}:{detail[:64]}",
                )
            except Exception:  # noqa: BLE001
                logger.exception("anomaly notify failed")

    def _on_launch_failed(self, task_id: int, reason: str) -> None:
        self.status.set(
            BrowserConnectionStatus.PAGE_ERROR,
            task_id=task_id,
            detail=reason,
        )
        if self._runtime is not None:
            try:
                self._runtime.emit_browser_launch_failed(task_id, reason)
            except Exception:  # noqa: BLE001
                logger.exception("emit_browser_launch_failed failed")
        elif self._notifier is not None:
            try:
                self._notifier.notify(
                    "浏览器启动失败",
                    reason,
                    kind="browser_launch_failed",
                    task_id=task_id,
                    urgent=True,
                    dedupe_key=f"browser_launch_failed:{task_id}:{reason[:40]}",
                )
            except Exception:  # noqa: BLE001
                logger.exception("launch fail notify failed")
