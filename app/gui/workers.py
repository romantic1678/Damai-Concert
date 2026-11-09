"""QThread workers — keep Playwright / monitor off the GUI thread."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.browser.assist import BrowserAssist
from app.errors import AppError
from app.logging_config import get_logger
from app.services.runtime import TaskRuntime

logger = get_logger("gui.workers")


class BrowserOpenWorker(QObject):
    finished_ok = Signal(int, str)  # task_id, status
    failed = Signal(int, str)  # task_id, message

    def __init__(self, browser: BrowserAssist) -> None:
        super().__init__()
        self._browser = browser
        self._task_id = 0
        self._url = ""
        self._headed = True

    def configure(self, task_id: int, url: str, *, headed: bool = True) -> None:
        self._task_id = task_id
        self._url = url
        self._headed = headed

    @Slot()
    def run(self) -> None:
        try:
            info = self._browser.open_official_page(
                self._task_id,
                self._url,
                headless=not self._headed,
            )
            self.finished_ok.emit(self._task_id, info.status.value)
        except AppError as exc:
            logger.error("browser worker app error: %s", exc.user_message)
            self.failed.emit(self._task_id, exc.user_message)
        except Exception as exc:  # noqa: BLE001
            logger.exception("browser worker crashed")
            self.failed.emit(self._task_id, str(exc))


class MonitorControlWorker(QObject):
    finished_ok = Signal(int, str)
    failed = Signal(int, str)

    def __init__(self, runtime: TaskRuntime) -> None:
        super().__init__()
        self._runtime = runtime
        self._task_id = 0
        self._start = True

    def configure(self, task_id: int, *, start: bool) -> None:
        self._task_id = task_id
        self._start = start

    @Slot()
    def run(self) -> None:
        try:
            if self._start:
                self._runtime.resume_task(self._task_id, enable_monitor=True)
                # Also try baseline poll once without blocking forever
                try:
                    self._runtime.fire_monitor_poll(self._task_id)
                except Exception:  # noqa: BLE001
                    logger.exception("initial monitor poll failed")
                self.finished_ok.emit(self._task_id, "started")
            else:
                self._runtime.stop_task(self._task_id, reason="user_stop_monitor")
                self.finished_ok.emit(self._task_id, "stopped")
        except AppError as exc:
            self.failed.emit(self._task_id, exc.user_message)
        except Exception as exc:  # noqa: BLE001
            logger.exception("monitor worker crashed")
            self.failed.emit(self._task_id, str(exc))


def start_worker(worker: QObject, slot_name: str = "run") -> QThread:
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(getattr(worker, slot_name))
    worker.finished_ok.connect(thread.quit)  # type: ignore[attr-defined]
    worker.failed.connect(thread.quit)  # type: ignore[attr-defined]
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread
