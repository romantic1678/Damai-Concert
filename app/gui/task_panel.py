"""Left-side concert task table."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.status_labels import display_status
from app.models import ConcertTask


class TaskPanel(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        on_selection: Callable[[int | None], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_selection = on_selection
        self._tasks: list[ConcertTask] = []

        title = QLabel("演唱会任务")
        title.setObjectName("Title")

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "名称", "城市", "开售时间", "状态"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._emit_selection)

        self.btn_add = QPushButton("添加任务")
        self.btn_edit = QPushButton("编辑任务")
        self.btn_edit.setObjectName("Secondary")
        self.btn_delete = QPushButton("删除任务")
        self.btn_delete.setObjectName("Danger")

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_edit)
        btn_row.addWidget(self.btn_delete)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.table, stretch=1)
        layout.addLayout(btn_row)

    def set_tasks(self, tasks: list[ConcertTask]) -> None:
        selected = self.selected_task_id()
        self._tasks = list(tasks)
        self.table.setRowCount(0)
        for task in self._tasks:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                str(task.id or ""),
                task.name,
                task.city or "",
                task.open_sale_at.isoformat() if task.open_sale_at else "",
                display_status(task),
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, task.id)
                self.table.setItem(row, col, item)
        if selected is not None:
            self.select_task_id(selected)

    def selected_task_id(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        return int(data) if data is not None else None

    def select_task_id(self, task_id: int) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == task_id:
                self.table.selectRow(row)
                return

    def _emit_selection(self) -> None:
        if self._on_selection:
            self._on_selection(self.selected_task_id())
