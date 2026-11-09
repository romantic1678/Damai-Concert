"""Modern light stylesheet for Damai Ticket Assistant GUI."""

APP_STYLE = """
QWidget {
  font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
  font-size: 13px;
  color: #1f2937;
}
QMainWindow, QDialog {
  background: #f3f4f6;
}
QFrame#Card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
}
QLabel#Title {
  font-size: 18px;
  font-weight: 700;
  color: #111827;
}
QLabel#Subtitle {
  color: #6b7280;
}
QLabel#StatusBadge {
  padding: 4px 10px;
  border-radius: 999px;
  background: #e0e7ff;
  color: #3730a3;
  font-weight: 600;
}
QPushButton {
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 8px;
  padding: 8px 14px;
  font-weight: 600;
}
QPushButton:hover { background: #1d4ed8; }
QPushButton:disabled { background: #93c5fd; }
QPushButton#Secondary {
  background: #ffffff;
  color: #1f2937;
  border: 1px solid #d1d5db;
}
QPushButton#Secondary:hover { background: #f9fafb; }
QPushButton#Danger {
  background: #dc2626;
}
QPushButton#Danger:hover { background: #b91c1c; }
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QDateTimeEdit, QComboBox {
  background: #ffffff;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 6px 8px;
  selection-background-color: #93c5fd;
}
QTableWidget {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  gridline-color: #f3f4f6;
}
QHeaderView::section {
  background: #f9fafb;
  padding: 6px;
  border: none;
  border-bottom: 1px solid #e5e7eb;
  font-weight: 600;
}
QPlainTextEdit#LogView {
  background: #0b1020;
  color: #d1d5db;
  font-family: "Consolas", "Sarasa Mono SC", monospace;
  border-radius: 8px;
}
"""
