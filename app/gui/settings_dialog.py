"""Notification settings dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.config import Settings
from app.lifecycle import Application


class NotifySettingsDialog(QDialog):
    def __init__(self, app: Application, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("通知设置")
        self._app = app
        cfg = app.settings.notify

        self.offsets = QLineEdit(",".join(str(m) for m in cfg.reminder_offsets_minutes))
        self.sound = QCheckBox("启用声音提醒")
        self.sound.setChecked(cfg.sound_enabled)
        self.desktop = QCheckBox("启用桌面通知")
        self.desktop.setChecked(cfg.desktop_enabled)
        self.gui_en = QCheckBox("启用界面内消息")
        self.gui_en.setChecked(cfg.gui_enabled)

        form = QFormLayout()
        form.addRow(QLabel("提醒时间（分钟，逗号分隔，0=开售时）"))
        form.addRow("偏移", self.offsets)
        form.addRow(self.sound)
        form.addRow(self.desktop)
        form.addRow(self.gui_en)

        self.btn_test = QPushButton("发送测试通知")
        self.btn_test.clicked.connect(self._test)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        tip = QLabel("说明：偏移写入内存设置；完整持久化请编辑 config/settings.yaml 后重启。")
        tip.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.btn_test)
        layout.addWidget(tip)
        layout.addWidget(buttons)

    def apply_to_settings(self) -> None:
        raw = self.offsets.text().replace("，", ",")
        parts = [p.strip() for p in raw.split(",") if p.strip() != ""]
        minutes = [int(p) for p in parts]
        if not minutes or any(m < 0 for m in minutes):
            raise ValueError("提醒偏移无效")
        self._app.settings.notify.reminder_offsets_minutes = minutes
        self._app.settings.notify.sound_enabled = self.sound.isChecked()
        self._app.settings.notify.desktop_enabled = self.desktop.isChecked()
        self._app.settings.notify.gui_enabled = self.gui_en.isChecked()
        # Update runtime offsets
        from app.services.runtime import minutes_to_offset_seconds

        self._app.runtime._offsets = minutes_to_offset_seconds(minutes)  # noqa: SLF001
        # Update sound channel flags if present
        from app.notify.sound import SoundNotifier

        for n in self._app.notifier._notifiers:  # noqa: SLF001
            if isinstance(n, SoundNotifier):
                n.enabled = self.sound.isChecked()

    def _test(self) -> None:
        try:
            self.apply_to_settings()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "设置错误", str(exc))
            return
        self._app.notifier.notify(
            "测试通知",
            "这是一条来自 GUI 的测试通知（不会自动购票）。",
            kind="test_notify",
            urgent=True,
            dedupe_key="gui_test_notify",
            force=True,
        )
        QMessageBox.information(self, "已发送", "测试通知已发送。")

    def accept(self) -> None:  # type: ignore[override]
        try:
            self.apply_to_settings()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "设置错误", str(exc))
            return
        super().accept()
