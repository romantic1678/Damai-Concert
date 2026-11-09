"""Phase 8 Playwright browser assist tests — local mock pages only."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.browser.assist import BrowserAssist
from app.browser.heuristics import needs_human_verification
from app.browser.mock_server import MockBrowserServer
from app.browser.status import BrowserConnectionStatus
from app.browser.takeover import TakeoverState
from app.errors import BrowserAssistError
from app.lifecycle import Application
from app.notify.kinds import BROWSER_LAUNCH_FAILED, HUMAN_TAKEOVER_NEEDED

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "browser"


@pytest.fixture()
def mock_server() -> MockBrowserServer:
    server = MockBrowserServer(FIXTURES)
    server.start()
    yield server
    server.stop()


@pytest.fixture()
def assist(app: Application) -> BrowserAssist:
    # Ensure headless for CI
    app.browser._headless = True  # noqa: SLF001
    yield app.browser
    try:
        app.browser.close()
    except Exception:
        pass


def test_heuristic_detects_captcha() -> None:
    reason = needs_human_verification("请完成验证码", "请拖动滑块")
    assert reason is not None


def test_open_mock_page(app: Application, mock_server: MockBrowserServer, assist: BrowserAssist) -> None:
    url = mock_server.url("ok.html")
    info = assist.open_official_page(11, url, headless=True)
    assert info.task_id == 11
    assert "ok.html" in info.official_url
    assert assist.connection_status in {
        BrowserConnectionStatus.PAGE_READY,
        BrowserConnectionStatus.HUMAN_TAKEOVER,
    }
    assert assist.current_url() is not None
    assist.close(11)
    assert assist.connection_status == BrowserConnectionStatus.DISCONNECTED


def test_reject_disallowed_host(assist: BrowserAssist) -> None:
    with pytest.raises(BrowserAssistError):
        assist.open_official_page(1, "https://evil.example/phish", headless=True)


def test_human_takeover_on_verify_page(
    app: Application, mock_server: MockBrowserServer, assist: BrowserAssist
) -> None:
    ok = mock_server.url("ok.html")
    assist.open_official_page(22, ok, headless=True)
    verify = mock_server.url("verify.html")
    assist.navigate(verify, task_id=22)
    assert assist.takeover.state(22) == TakeoverState.HUMAN_ACTIVE
    assert assist.connection_status == BrowserConnectionStatus.HUMAN_TAKEOVER
    # Auto navigation blocked during takeover
    with pytest.raises(BrowserAssistError):
        assist.reload(22)
    kinds = {e.kind for e in app.notifier.events if e.delivered}
    assert HUMAN_TAKEOVER_NEEDED in kinds


def test_pause_and_close(app: Application, mock_server: MockBrowserServer, assist: BrowserAssist) -> None:
    assist.open_official_page(33, mock_server.url("ok.html"), headless=True)
    assist.pause(33)
    assert assist.connection_status == BrowserConnectionStatus.PAUSED
    with pytest.raises(BrowserAssistError):
        assist.reload(33)
    assist.close(33)
    assert assist.connection_status == BrowserConnectionStatus.DISCONNECTED


def test_page_error_anomaly(
    app: Application, mock_server: MockBrowserServer, assist: BrowserAssist
) -> None:
    assist.open_official_page(44, mock_server.url("error.html"), headless=True)
    assert assist.connection_status == BrowserConnectionStatus.PAGE_ERROR
    kinds = {e.kind for e in app.notifier.events if e.delivered}
    assert "browser_page_anomaly" in kinds


def test_launch_failure_emits_notification(app: Application, assist: BrowserAssist) -> None:
    # Invalid scheme / host
    with pytest.raises(BrowserAssistError):
        assist.open_official_page(55, "https://not-allowed.example/", headless=True)
    kinds = {e.kind for e in app.notifier.events if e.delivered}
    assert BROWSER_LAUNCH_FAILED in kinds


def test_status_listener(app: Application, mock_server: MockBrowserServer, assist: BrowserAssist) -> None:
    seen: list[str] = []

    def on_event(ev):  # type: ignore[no-untyped-def]
        seen.append(ev.status.value)

    assist.status.add_listener(on_event)
    assist.open_official_page(66, mock_server.url("login.html"), headless=True)
    assist.close(66)
    assert "launching" in seen or "connected" in seen
    assert "disconnected" in seen


def test_manual_login_page_does_not_scrape_password(
    mock_server: MockBrowserServer, assist: BrowserAssist
) -> None:
    """Ensure we only open the page — no fill/submit of credentials."""
    info = assist.open_official_page(77, mock_server.url("login.html"), headless=True)
    assert "login" in info.official_url
    # Page has password input but we never call fill
    assert assist._page is not None  # noqa: SLF001
    count = assist._page.locator('input[type="password"]').count()  # noqa: SLF001
    assert count >= 1
    # No credential storage API on assist
    assert not hasattr(assist, "credentials")
    assist.close(77)


def test_release_takeover_allows_reload(
    mock_server: MockBrowserServer, assist: BrowserAssist
) -> None:
    assist.open_official_page(88, mock_server.url("ok.html"), headless=True)
    assist.request_human_takeover(88, "manual")
    assist.release_takeover(88)
    assist.reload(88)
    assist.close(88)
