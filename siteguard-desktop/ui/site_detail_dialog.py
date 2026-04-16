"""
SiteDetailDialog — per-site detail view with Overview, Threats, History, Actions tabs.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont

# Style constants
DARK_BG = "#0f0f23"
DARK_PANEL = "#1a1a2e"
DARK_BORDER = "#2d2d4e"
ACCENT = "#1565C0"
TEXT_MAIN = "#e0e0e0"
TEXT_DIM = "#888888"
GREEN = "#4CAF50"
RED = "#f44336"
YELLOW = "#FFC107"

DIALOG_STYLE = f"""
QDialog, QWidget {{
    background: {DARK_BG};
    color: {TEXT_MAIN};
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}}
QTabWidget::pane {{
    border: 1px solid {DARK_BORDER};
    background: {DARK_BG};
}}
QTabBar::tab {{
    background: {DARK_PANEL};
    color: {TEXT_DIM};
    padding: 8px 20px;
    border: none;
    border-right: 1px solid {DARK_BORDER};
}}
QTabBar::tab:selected {{
    color: {TEXT_MAIN};
    background: {DARK_BG};
    border-bottom: 2px solid {ACCENT};
}}
QTableWidget {{
    background: {DARK_PANEL};
    color: {TEXT_MAIN};
    border: 1px solid {DARK_BORDER};
    gridline-color: {DARK_BORDER};
    selection-background-color: {ACCENT};
}}
QHeaderView::section {{
    background: {DARK_BG};
    color: {TEXT_MAIN};
    border: none;
    border-bottom: 1px solid {DARK_BORDER};
    padding: 6px;
    font-weight: bold;
}}
QPushButton {{
    background: {ACCENT};
    color: #fff;
    border: none;
    border-radius: 4px;
    padding: 7px 18px;
    font-size: 13px;
}}
QPushButton:hover {{ background: #1976D2; }}
QPushButton#danger {{ background: #c62828; }}
QPushButton#danger:hover {{ background: #d32f2f; }}
QLabel#header {{
    font-size: 18px;
    font-weight: bold;
    padding: 8px;
}}
QLabel#metric {{
    background: {DARK_PANEL};
    border: 1px solid {DARK_BORDER};
    border-radius: 6px;
    padding: 12px;
}}
"""


class SiteDetailDialog(QDialog):
    """Detail dialog for a single monitored site."""

    check_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, domain: str, status: dict, history: List[dict],
                 parent=None):
        super().__init__(parent)
        self._domain = domain
        self._status = status
        self._history = history

        self.setWindowTitle(f"Подробности — {domain}")
        self.setMinimumSize(600, 500)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)

        # Header
        is_up = status.get("up")
        if is_up is None:
            status_text, color = "⏳ Ожидание", TEXT_DIM
        elif is_up:
            status_text, color = "✓ Онлайн", GREEN
        else:
            status_text, color = "✗ Офлайн", RED

        header = QLabel(f"<span style='color:{color}'>{status_text}</span>  {domain}")
        header.setObjectName("header")
        layout.addWidget(header)

        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self._build_overview_tab(), "Обзор")
        tabs.addTab(self._build_threats_tab(), "Угрозы")
        tabs.addTab(self._build_history_tab(), "История")
        tabs.addTab(self._build_actions_tab(), "Действия")
        layout.addWidget(tabs)

    def _build_overview_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        info = self._status
        code = info.get("status_code", 0)
        ms = info.get("response_ms", 0)
        ssl_d = info.get("ssl_days")
        last = info.get("last_check", "—")
        error = info.get("error")

        # Metrics grid
        metrics = QHBoxLayout()
        metrics.addWidget(self._metric_box("HTTP код", str(code) if code else "—", ACCENT))
        metrics.addWidget(self._metric_box("Время ответа", f"{ms} мс" if ms else "—", "#9C27B0"))
        metrics.addWidget(self._metric_box("SSL дней",
                                           str(ssl_d) if ssl_d is not None else "—",
                                           YELLOW if ssl_d is not None and ssl_d < 30 else GREEN))
        layout.addLayout(metrics)

        # Additional info
        layout.addWidget(QLabel(f"Последняя проверка: {last}"))
        if error:
            err_lbl = QLabel(f"Ошибка: {error}")
            err_lbl.setStyleSheet(f"color: {RED};")
            layout.addWidget(err_lbl)

        # Uptime from history
        if self._history:
            up_count = sum(1 for h in self._history if h.get("up"))
            pct = round(up_count / len(self._history) * 100, 1)
            layout.addWidget(QLabel(f"Аптайм (за {len(self._history)} проверок): {pct}%"))

        threats = info.get("threats", [])
        layout.addWidget(QLabel(f"Угрозы: {len(threats)}"))

        layout.addStretch()
        return w

    def _metric_box(self, title: str, value: str, color: str) -> QLabel:
        lbl = QLabel(f"<b style='font-size:20px;color:{color}'>{value}</b><br>"
                     f"<span style='color:{TEXT_DIM};font-size:11px'>{title}</span>")
        lbl.setObjectName("metric")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setFixedHeight(70)
        return lbl

    def _build_threats_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        threats = self._status.get("threats", [])
        if not threats:
            lbl = QLabel("Угроз не обнаружено")
            lbl.setStyleSheet(f"color: {GREEN}; font-size: 14px; padding: 20px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)
            return w

        table = QTableWidget(len(threats), 3)
        table.setHorizontalHeaderLabels(["Тип угрозы", "Описание", "Время обнаружения"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)

        for row, t in enumerate(threats):
            for col, val in enumerate([t.get("type", ""), t.get("desc", ""), t.get("time", "")]):
                item = QTableWidgetItem(val)
                item.setForeground(QBrush(QColor(YELLOW if col == 0 else TEXT_MAIN)))
                table.setItem(row, col, item)

        layout.addWidget(table)
        return w

    def _build_history_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        entries = self._history[-50:]  # last 50
        if not entries:
            lbl = QLabel("История проверок пуста")
            lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 14px; padding: 20px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)
            return w

        table = QTableWidget(len(entries), 4)
        table.setHorizontalHeaderLabels(["Дата", "Статус", "Код", "Время (мс)"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 4):
            table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)

        for row, entry in enumerate(reversed(entries)):
            up = entry.get("up")
            status_text = "✓ Онлайн" if up else "✗ Офлайн"
            status_color = GREEN if up else RED

            items = [
                (entry.get("time", "—"), TEXT_MAIN),
                (status_text, status_color),
                (str(entry.get("status_code", 0)), TEXT_DIM),
                (f"{entry.get('response_ms', 0)} мс", TEXT_DIM),
            ]
            for col, (text, color) in enumerate(items):
                item = QTableWidgetItem(text)
                item.setForeground(QBrush(QColor(color)))
                table.setItem(row, col, item)

        layout.addWidget(table)
        return w

    def _build_actions_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addStretch()

        btn_check = QPushButton("Проверить сейчас")
        btn_check.clicked.connect(lambda: self.check_requested.emit(self._domain))
        layout.addWidget(btn_check, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(20)

        btn_delete = QPushButton("Удалить из мониторинга")
        btn_delete.setObjectName("danger")
        btn_delete.clicked.connect(self._confirm_delete)
        layout.addWidget(btn_delete, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()
        return w

    def _confirm_delete(self):
        reply = QMessageBox.question(
            self, "Удалить сайт",
            f"Удалить {self._domain} из мониторинга?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit(self._domain)
            self.accept()
