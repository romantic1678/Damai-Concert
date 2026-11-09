"""Main Chinese desktop window for Damai Ticket Assistant."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.errors import AppError, ValidationError
from app.gui.log_panel import LogPanel
from app.gui.settings_dialog import NotifySettingsDialog
from app.gui.status_labels import display_status, format_countdown
from app.gui.styles import APP_STYLE
from app.gui.task_dialog import TaskDialog
from app.gui.task_panel import TaskPanel
from app.gui.workers import BrowserOpenWorker, MonitorControlWorker, start_worker
from app.lifecycle import Application
from app.logging_config import get_logger
from app.models import ConcertTask

logger = get_logger("gui.main")


class MainWindow(QMainWindow):
    def __init__(self, app: Application) -> None:
        super().__init__()
        self._app = app
        self._selected_id: int | None = None
        self._threads: list = []

        self.setWindowTitle(f"大麦开票助手 — Damai Ticket Assistant v{__version__}")
        self.resize(1180, 760)
        self.setMinimumSize(960, 640)
        self.setStyleSheet(APP_STYLE)

        header = QLabel(f"{app.settings.app.name}")
        header.setObjectName("Title")
        subtitle = QLabel(
            f"版本 {__version__} · 仅开售监控/提醒 · 不会自动购票或绕过风控"
        )
        subtitle.setObjectName("Subtitle")

        self.task_panel = TaskPanel(on_selection=self._on_select_task)
        self.task_panel.btn_add.clicked.connect(self._add_task)
        self.task_panel.btn_edit.clicked.connect(self._edit_task)
        self.task_panel.btn_delete.clicked.connect(self._delete_task)

        # Detail card
        detail = QFrame()
        detail.setObjectName("Card")
        detail_layout = QVBoxLayout(detail)

        self.lbl_name = QLabel("未选择任务")
        self.lbl_name.setObjectName("Title")
        self.lbl_status = QLabel("—")
        self.lbl_status.setObjectName("StatusBadge")
        self.lbl_countdown = QLabel("倒计时：—")
        self.lbl_price = QLabel("目标票价：—")
        self.lbl_browser = QLabel("浏览器状态：未连接")
        self.lbl_meta = QLabel("")
        self.lbl_meta.setWordWrap(True)

        self.btn_start = QPushButton("开始监控")
        self.btn_stop = QPushButton("停止监控")
        self.btn_stop.setObjectName("Danger")
        self.btn_open = QPushButton("打开大麦官方页面")
        self.btn_open.setObjectName("Secondary")
        self.btn_settings = QPushButton("通知设置")
        self.btn_settings.setObjectName("Secondary")

        self.btn_start.clicked.connect(self._start_monitor)
        self.btn_stop.clicked.connect(self._stop_monitor)
        self.btn_open.clicked.connect(self._open_official)
        self.btn_settings.clicked.connect(self._open_settings)

        actions = QHBoxLayout()
        actions.addWidget(self.btn_start)
        actions.addWidget(self.btn_stop)
        actions.addWidget(self.btn_open)
        actions.addWidget(self.btn_settings)
        actions.addStretch(1)

        detail_layout.addWidget(self.lbl_name)
        detail_layout.addWidget(self.lbl_status, alignment=Qt.AlignmentFlag.AlignLeft)
        detail_layout.addWidget(self.lbl_countdown)
        detail_layout.addWidget(self.lbl_price)
        detail_layout.addWidget(self.lbl_browser)
        detail_layout.addWidget(self.lbl_meta)
        detail_layout.addLayout(actions)
        detail_layout.addStretch(1)

        self.log_panel = LogPanel()

        splitter = QSplitter()
        left = QFrame()
        left.setObjectName("Card")
        left_l = QVBoxLayout(left)
        left_l.addWidget(self.task_panel)
        splitter.addWidget(left)

        right_split = QSplitter(Qt.Orientation.Vertical)
        right_split.addWidget(detail)
        log_card = QFrame()
        log_card.setObjectName("Card")
        log_l = QVBoxLayout(log_card)
        log_title = QLabel("系统日志")
        log_title.setObjectName("Title")
        log_l.addWidget(log_title)
        log_l.addWidget(self.log_panel)
        right_split.addWidget(log_card)
        right_split.setStretchFactor(0, 2)
        right_split.setStretchFactor(1, 3)
        splitter.addWidget(right_split)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)

        central = QWidget()
        root = QVBoxLayout(central)
        root.addWidget(header)
        root.addWidget(subtitle)
        root.addWidget(splitter, stretch=1)
        self.setCentralWidget(central)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self.refresh_tasks()
        logger.info("GUI 主窗口已启动")

    def refresh_tasks(self) -> None:
        tasks = list(self._app.task_service.list_all())
        self.task_panel.set_tasks(tasks)
        self._refresh_detail()

    def _on_select_task(self, task_id: int | None) -> None:
        self._selected_id = task_id
        self._refresh_detail()

    def _current_task(self) -> ConcertTask | None:
        if self._selected_id is None:
            return None
        return self._app.task_service.get(self._selected_id)

    def _refresh_detail(self) -> None:
        task = self._current_task()
        if task is None:
            self.lbl_name.setText("未选择任务")
            self.lbl_status.setText("—")
            self.lbl_countdown.setText("倒计时：—")
            self.lbl_price.setText("目标票价：—")
            self.lbl_meta.setText("")
            return
        countdown = None
        try:
            if task.open_sale_at is not None and task.id is not None:
                countdown = self._app.countdown.snapshot(task.id)
        except Exception:  # noqa: BLE001
            countdown = None
        takeover = None
        if task.id is not None:
            takeover = self._app.takeover.state(task.id)
        label = display_status(
            task,
            countdown=countdown,
            browser_status=self._app.browser.connection_status,
            takeover=takeover,
        )
        self.lbl_name.setText(task.name)
        self.lbl_status.setText(label)
        self.lbl_countdown.setText(f"倒计时：{format_countdown(countdown)}")
        price = f"{task.target_price:.2f}" if task.target_price is not None else "—"
        self.lbl_price.setText(f"目标票价：{price}")
        self.lbl_browser.setText(
            f"浏览器状态：{self._app.browser.connection_status.value}"
        )
        self.lbl_meta.setText(
            f"艺人：{task.artist_name or '—'}　城市：{task.city or '—'}　"
            f"场次：{task.session_name or '—'}　票档：{task.target_tier or '—'}　"
            f"数量：{task.ticket_quantity or '—'}　链接：{task.official_url or '—'}"
        )

    def _tick(self) -> None:
        self._refresh_detail()
        # light refresh of status column
        if self._selected_id is not None:
            # refresh table statuses without full reload unless needed
            pass

    def _add_task(self) -> None:
        dlg = TaskDialog(self, title="添加演唱会任务")
        if dlg.exec() != TaskDialog.DialogCode.Accepted:
            return
        try:
            task = dlg.build_task()
            saved = self._app.task_service.create(task)
            self.refresh_tasks()
            if saved.id is not None:
                self.task_panel.select_task_id(saved.id)
                self._selected_id = saved.id
            logger.info("GUI 已添加任务 id=%s", saved.id)
        except (AppError, ValidationError) as exc:
            QMessageBox.warning(self, "无法添加", getattr(exc, "user_message", str(exc)))

    def _edit_task(self) -> None:
        task = self._current_task()
        if task is None or task.id is None:
            QMessageBox.information(self, "提示", "请先选择一个任务。")
            return
        dlg = TaskDialog(self, task=task, title="编辑演唱会任务")
        if dlg.exec() != TaskDialog.DialogCode.Accepted:
            return
        try:
            updated = dlg.build_task()
            fields = {
                "name": updated.name,
                "artist_name": updated.artist_name,
                "city": updated.city,
                "official_url": updated.official_url,
                "show_date": updated.show_date,
                "session_name": updated.session_name,
                "target_price": updated.target_price,
                "target_tier": updated.target_tier,
                "ticket_quantity": updated.ticket_quantity,
                "open_sale_at": updated.open_sale_at,
                "status": updated.status,
                "note": updated.note,
            }
            self._app.task_service.update(task.id, **fields)
            self.refresh_tasks()
            self.task_panel.select_task_id(task.id)
        except (AppError, ValidationError) as exc:
            QMessageBox.warning(self, "无法保存", getattr(exc, "user_message", str(exc)))

    def _delete_task(self) -> None:
        task = self._current_task()
        if task is None or task.id is None:
            QMessageBox.information(self, "提示", "请先选择一个任务。")
            return
        ans = QMessageBox.question(
            self,
            "确认删除",
            f"确定删除任务「{task.name}」吗？",
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            try:
                self._app.runtime.unschedule_task(task.id)
            except Exception:  # noqa: BLE001
                pass
            self._app.task_service.delete(task.id)
            self._selected_id = None
            self.refresh_tasks()
        except AppError as exc:
            QMessageBox.warning(self, "无法删除", exc.user_message)

    def _start_monitor(self) -> None:
        task = self._current_task()
        if task is None or task.id is None:
            QMessageBox.information(self, "提示", "请先选择一个任务。")
            return
        worker = MonitorControlWorker(self._app.runtime)
        worker.configure(task.id, start=True)
        worker.finished_ok.connect(lambda *_: self.refresh_tasks())
        worker.failed.connect(lambda _tid, msg: QMessageBox.warning(self, "监控失败", msg))
        self._threads.append(start_worker(worker))
        logger.info("请求开始监控 task=%s", task.id)

    def _stop_monitor(self) -> None:
        task = self._current_task()
        if task is None or task.id is None:
            QMessageBox.information(self, "提示", "请先选择一个任务。")
            return
        worker = MonitorControlWorker(self._app.runtime)
        worker.configure(task.id, start=False)
        worker.finished_ok.connect(lambda *_: self.refresh_tasks())
        worker.failed.connect(lambda _tid, msg: QMessageBox.warning(self, "停止失败", msg))
        self._threads.append(start_worker(worker))

    def _open_official(self) -> None:
        task = self._current_task()
        if task is None or task.id is None:
            QMessageBox.information(self, "提示", "请先选择一个任务。")
            return
        if not task.official_url:
            QMessageBox.warning(self, "缺少链接", "该任务没有官方页面链接。")
            return
        worker = BrowserOpenWorker(self._app.browser)
        worker.configure(task.id, task.official_url, headed=True)
        worker.finished_ok.connect(self._on_browser_ok)
        worker.failed.connect(self._on_browser_fail)
        self._threads.append(start_worker(worker))
        self.lbl_browser.setText("浏览器状态：launching…")
        logger.info("请求打开官方页 task=%s", task.id)

    def _on_browser_ok(self, task_id: int, status: str) -> None:
        self.lbl_browser.setText(f"浏览器状态：{status}")
        self._refresh_detail()
        QMessageBox.information(
            self,
            "已打开官方页面",
            "浏览器已打开。请手动登录与操作；本程序不会自动下单或绕过验证。",
        )

    def _on_browser_fail(self, task_id: int, message: str) -> None:
        self.lbl_browser.setText("浏览器状态：异常")
        QMessageBox.warning(self, "打开失败", message)
        self._refresh_detail()

    def _open_settings(self) -> None:
        dlg = NotifySettingsDialog(self._app, self)
        dlg.exec()

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._timer.stop()
        self.log_panel.detach()
        try:
            self._app.browser.close()
        except Exception:  # noqa: BLE001
            pass
        super().closeEvent(event)
