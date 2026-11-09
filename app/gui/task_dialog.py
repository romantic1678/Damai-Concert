"""Add / edit concert task dialog (Chinese)."""

from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import QDate, QDateTime
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from app.errors import ValidationError
from app.models import ConcertTask, TASK_STATUSES
from app.timeutil import DEFAULT_TZ, ensure_aware


class TaskDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        task: ConcertTask | None = None,
        title: str = "任务",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(480)
        self._task = task

        self.name = QLineEdit(task.name if task else "")
        self.artist = QLineEdit(task.artist_name or "" if task else "")
        self.city = QLineEdit(task.city or "" if task else "")
        self.url = QLineEdit(task.official_url or "" if task else "")
        self.session = QLineEdit(task.session_name or "" if task else "")
        self.tier = QLineEdit(task.target_tier or "" if task else "")
        self.price = QDoubleSpinBox()
        self.price.setRange(0, 100000)
        self.price.setDecimals(2)
        if task and task.target_price is not None:
            self.price.setValue(float(task.target_price))
        self.qty = QSpinBox()
        self.qty.setRange(0, 6)
        self.qty.setSpecialValueText("未设置")
        if task and task.ticket_quantity is not None:
            self.qty.setValue(int(task.ticket_quantity))
        else:
            self.qty.setValue(0)
        self.show_date = QDateEdit()
        self.show_date.setCalendarPopup(True)
        self.show_date.setDisplayFormat("yyyy-MM-dd")
        if task and task.show_date:
            self.show_date.setDate(QDate(task.show_date.year, task.show_date.month, task.show_date.day))
        else:
            self.show_date.setDate(QDate.currentDate())
        self.open_sale = QDateTimeEdit()
        self.open_sale.setCalendarPopup(True)
        self.open_sale.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        if task and task.open_sale_at:
            dt = ensure_aware(task.open_sale_at)
            self.open_sale.setDateTime(
                QDateTime(
                    dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second
                )
            )
        else:
            self.open_sale.setDateTime(QDateTime.currentDateTime())
        self.status = QComboBox()
        for s in sorted(TASK_STATUSES):
            self.status.addItem(s)
        if task:
            idx = self.status.findText(task.status)
            if idx >= 0:
                self.status.setCurrentIndex(idx)
        self.note = QTextEdit(task.note or "" if task else "")
        self.note.setFixedHeight(70)

        form = QFormLayout()
        form.addRow("演唱会名称 *", self.name)
        form.addRow("艺人", self.artist)
        form.addRow("城市", self.city)
        form.addRow("官方链接", self.url)
        form.addRow("演出日期", self.show_date)
        form.addRow("场次", self.session)
        form.addRow("目标票价", self.price)
        form.addRow("票档", self.tier)
        form.addRow("购票数量", self.qty)
        form.addRow("开售时间", self.open_sale)
        form.addRow("任务状态", self.status)
        form.addRow("备注", self.note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def build_task(self) -> ConcertTask:
        name = self.name.text().strip()
        if not name:
            raise ValidationError("演唱会名称不能为空")
        q = self.qty.value()
        show_q = self.show_date.date()
        sale_q = self.open_sale.dateTime()
        open_sale_at = datetime(
            sale_q.date().year(),
            sale_q.date().month(),
            sale_q.date().day(),
            sale_q.time().hour(),
            sale_q.time().minute(),
            sale_q.time().second(),
            tzinfo=DEFAULT_TZ,
        )
        show_date = date(show_q.year(), show_q.month(), show_q.day())
        return ConcertTask(
            id=self._task.id if self._task else None,
            name=name,
            artist_name=self.artist.text().strip() or None,
            city=self.city.text().strip() or None,
            official_url=self.url.text().strip() or None,
            show_date=show_date,
            session_name=self.session.text().strip() or None,
            target_price=float(self.price.value()),
            target_tier=self.tier.text().strip() or None,
            ticket_quantity=q if q > 0 else None,
            open_sale_at=open_sale_at,
            status=self.status.currentText(),  # type: ignore[arg-type]
            note=self.note.toPlainText().strip() or None,
            monitor_enabled=self._task.monitor_enabled if self._task else False,
        )
