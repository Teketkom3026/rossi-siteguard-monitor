"""
SiteGuard Monitor Pro — Main Window v2.0.0
Мониторинг сайтов с обнаружением угроз, email-уведомлениями и историей.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QInputDialog, QMessageBox, QApplication,
    QDialog, QDialogButtonBox, QLineEdit, QFormLayout,
    QGroupBox, QTextEdit, QTabWidget, QFrame, QSizePolicy,
    QSystemTrayIcon, QMenu,
)
from PyQt6.QtCore import (
    Qt, QTimer, QSize,
)
from PyQt6.QtGui import (
    QAction, QColor, QFont, QPixmap, QPainter, QIcon, QBrush,
)
from PyQt6.QtNetwork import QLocalServer

from core.license_manager import LicenseManager
from core.license_validator import validate_key
from core.monitor_engine import MonitorEngine
from core.notifier import EmailNotifier

logger = logging.getLogger("SiteGuard.MainWindow")

SERVER_NAME = "RossiSiteGuardMonitor_v2"

# ---------------------------------------------------------------------------
# AppData paths
# ---------------------------------------------------------------------------
def _app_data_dir() -> Path:
    base = Path(os.getenv("APPDATA", str(Path.home())))
    d = base / "SiteGuard Monitor"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _sites_file() -> Path:
    return _app_data_dir() / "sites.json"

def _history_file() -> Path:
    return _app_data_dir() / "history.json"

def _load_sites() -> List[str]:
    f = _sites_file()
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return []

def _save_sites(domains: List[str]):
    _sites_file().write_text(json.dumps(domains, ensure_ascii=False, indent=2), encoding="utf-8")

def _load_history() -> dict:
    f = _history_file()
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}

# ---------------------------------------------------------------------------
# App icon
# ---------------------------------------------------------------------------
def _make_icon() -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(QColor("#1565C0"))
    p = QPainter(pix)
    p.setPen(QColor("#FFFFFF"))
    f = QFont("Segoe UI", 20, QFont.Weight.Bold)
    p.setFont(f)
    p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "SG")
    p.end()
    return QIcon(pix)

# ---------------------------------------------------------------------------
# License Dialog (inline, for first-run or re-activation)
# ---------------------------------------------------------------------------
class LicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Активация лицензии")
        self.setMinimumWidth(480)
        self.setStyleSheet("background:#1a1a2e; color:#e0e0e0; font-size:13px;")

        layout = QVBoxLayout(self)

        info = QLabel(
            "Введите лицензионный ключ в формате:\n"
            "SG-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX"
        )
        info.setStyleSheet("color:#aaa; padding:8px;")
        layout.addWidget(info)

        form = QFormLayout()
        self._key_edit = QLineEdit()
        self._key_edit.setPlaceholderText("SG-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX")
        self._key_edit.setStyleSheet(
            "background:#0f0f23; color:#e0e0e0; border:1px solid #333; "
            "padding:8px; font-size:14px; border-radius:4px;"
        )
        form.addRow("Ключ:", self._key_edit)
        layout.addLayout(form)

        self._status = QLabel("")
        self._status.setStyleSheet("padding:6px;")
        layout.addWidget(self._status)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.setStyleSheet("QPushButton{background:#1565C0;color:#fff;padding:6px 18px;border-radius:4px;}"
                           "QPushButton:hover{background:#1976D2;}")
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _validate(self):
        key = self._key_edit.text().strip().upper()
        if not key:
            self._status.setStyleSheet("color:#f44;")
            self._status.setText("Введите ключ.")
            return
        try:
            valid, plan, info = validate_key(key)
        except Exception as e:
            valid, plan, info = False, None, str(e)
        if valid:
            self._activated_key = key
            self._activated_plan = plan
            self._status.setStyleSheet("color:#4CAF50;")
            self._status.setText(f"✓ Ключ принят. План: {plan}")
            QTimer.singleShot(800, self.accept)
        else:
            self._status.setStyleSheet("color:#f44;")
            self._status.setText(f"✗ Неверный ключ: {info}")

    def get_key(self) -> str:
        return getattr(self, "_activated_key", "")

    def get_plan(self) -> str:
        return getattr(self, "_activated_plan", "")

# ---------------------------------------------------------------------------
# Add Sites Dialog (bulk import)
# ---------------------------------------------------------------------------
class AddSitesDialog(QDialog):
    def __init__(self, existing: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить сайты")
        self.setMinimumSize(520, 380)
        self.setStyleSheet("background:#1a1a2e; color:#e0e0e0; font-size:13px;")

        layout = QVBoxLayout(self)

        info = QLabel(
            "Введите домены — по одному на строке.\n"
            "Протокол https:// указывать не нужно."
        )
        info.setStyleSheet("color:#aaa; padding:4px;")
        layout.addWidget(info)

        self._edit = QTextEdit()
        self._edit.setPlaceholderText("example.com\nsite.ru\nrossi.ru")
        self._edit.setStyleSheet(
            "background:#0f0f23; color:#e0e0e0; border:1px solid #333; "
            "font-size:13px; border-radius:4px; padding:6px;"
        )
        layout.addWidget(self._edit)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.setStyleSheet("QPushButton{background:#1565C0;color:#fff;padding:6px 18px;border-radius:4px;}"
                           "QPushButton:hover{background:#1976D2;}")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._existing = existing

    def get_domains(self) -> List[str]:
        lines = self._edit.toPlainText().strip().splitlines()
        result = []
        for line in lines:
            d = line.strip().lower()
            for pfx in ("https://", "http://", "www."):
                if d.startswith(pfx):
                    d = d[len(pfx):]
            d = d.rstrip("/")
            if d and d not in self._existing and d not in result:
                result.append(d)
        return result

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------
DARK_BG     = "#0f0f23"
DARK_PANEL  = "#1a1a2e"
DARK_BORDER = "#2d2d4e"
ACCENT      = "#1565C0"
TEXT_MAIN   = "#e0e0e0"
TEXT_DIM    = "#888888"
GREEN       = "#4CAF50"
RED         = "#f44336"
YELLOW      = "#FFC107"

STYLE = f"""
QMainWindow, QWidget {{
    background: {DARK_BG};
    color: {TEXT_MAIN};
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}}
QMenuBar {{
    background: {DARK_PANEL};
    color: {TEXT_MAIN};
    border-bottom: 1px solid {DARK_BORDER};
}}
QMenuBar::item:selected {{ background: {ACCENT}; }}
QMenu {{
    background: {DARK_PANEL};
    color: {TEXT_MAIN};
    border: 1px solid {DARK_BORDER};
}}
QMenu::item:selected {{ background: {ACCENT}; }}
QStatusBar {{
    background: {DARK_PANEL};
    color: {TEXT_DIM};
    border-top: 1px solid {DARK_BORDER};
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
QTableWidget::item {{ padding: 4px 8px; }}
QPushButton {{
    background: {ACCENT};
    color: #fff;
    border: none;
    border-radius: 4px;
    padding: 7px 18px;
    font-size: 13px;
}}
QPushButton:hover {{ background: #1976D2; }}
QPushButton:pressed {{ background: #0D47A1; }}
QPushButton#danger {{ background: #c62828; }}
QPushButton#danger:hover {{ background: #d32f2f; }}
QLabel#stat_box {{
    background: {DARK_PANEL};
    border: 1px solid {DARK_BORDER};
    border-radius: 6px;
    padding: 10px 20px;
}}
QToolBar {{
    background: {DARK_PANEL};
    border-bottom: 1px solid {DARK_BORDER};
    spacing: 6px;
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
"""


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """Главное окно SiteGuard Monitor Pro v2.0.0."""

    def __init__(self, setup_data: dict | None = None):
        super().__init__()
        self.setup_data = setup_data or {}
        self._lm = LicenseManager()
        self._notifier = EmailNotifier()
        self._site_status: Dict[str, dict] = {}
        self._history: dict = _load_history()
        self._monitor_thread: Optional[MonitorEngine] = None
        self._icon = _make_icon()
        self._tray: Optional[QSystemTrayIcon] = None

        self.setWindowTitle("SiteGuard Monitor Pro v2.0.0")
        self.setWindowIcon(self._icon)
        self.setMinimumSize(900, 620)
        self.resize(1200, 780)
        self.setStyleSheet(STYLE)

        # Local server for single-instance show
        QLocalServer.removeServer(SERVER_NAME)
        self._local_server = QLocalServer(self)
        self._local_server.listen(SERVER_NAME)
        self._local_server.newConnection.connect(self._on_show_request)

        self._build_ui()
        self._setup_tray()

        # Auto-refresh timer — interval from settings
        settings = self._notifier.get_settings()
        interval_ms = settings.get("monitor_interval", 60) * 1000
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._run_monitor)
        self._timer.start(interval_ms)

        # Initial data load after window is shown
        QTimer.singleShot(500, self._initial_load)

    # ------------------------------------------------------------------
    # UI Build
    # ------------------------------------------------------------------
    def _build_ui(self):
        # Menu bar
        mb = self.menuBar()

        file_menu = mb.addMenu("Файл")
        act_add = QAction("Добавить сайты…", self)
        act_add.setShortcut("Ctrl+N")
        act_add.triggered.connect(self._add_sites_dialog)
        file_menu.addAction(act_add)
        file_menu.addSeparator()
        act_quit = QAction("Выход", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self._quit)
        file_menu.addAction(act_quit)

        license_menu = mb.addMenu("Лицензия")
        act_activate = QAction("Активировать / сменить ключ…", self)
        act_activate.triggered.connect(self._activate_license)
        license_menu.addAction(act_activate)
        act_license_info = QAction("Информация о лицензии", self)
        act_license_info.triggered.connect(self._show_license_info)
        license_menu.addAction(act_license_info)

        monitor_menu = mb.addMenu("Мониторинг")
        act_check = QAction("Проверить сейчас", self)
        act_check.setShortcut("F5")
        act_check.triggered.connect(self._run_monitor_forced)
        monitor_menu.addAction(act_check)
        act_remove = QAction("Удалить сайт…", self)
        act_remove.triggered.connect(self._remove_site_dialog)
        monitor_menu.addAction(act_remove)

        settings_menu = mb.addMenu("Настройки")
        act_settings = QAction("Параметры…", self)
        act_settings.triggered.connect(self._open_settings)
        settings_menu.addAction(act_settings)

        help_menu = mb.addMenu("Помощь")
        act_about = QAction("О программе", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

        # Toolbar
        tb = self.addToolBar("Главная")
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))

        btn_add = QPushButton("  + Добавить сайты")
        btn_add.clicked.connect(self._add_sites_dialog)
        tb.addWidget(btn_add)

        tb.addSeparator()

        btn_check = QPushButton("  ↻ Проверить")
        btn_check.clicked.connect(self._run_monitor_forced)
        tb.addWidget(btn_check)

        tb.addSeparator()

        btn_settings = QPushButton("  ⚙ Настройки")
        btn_settings.clicked.connect(self._open_settings)
        tb.addWidget(btn_settings)

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self._license_label = QLabel("Лицензия: загрузка…")
        self._license_label.setStyleSheet(f"color:{TEXT_DIM}; padding:0 12px;")
        tb.addWidget(self._license_label)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(12, 12, 12, 8)
        vbox.setSpacing(10)

        # Stats bar
        self._stats_bar = self._build_stats_bar()
        vbox.addWidget(self._stats_bar)

        # Tab widget: Мониторинг | Угрозы | История
        self._tabs = QTabWidget()
        vbox.addWidget(self._tabs, stretch=1)

        # Monitoring tab — sites table
        self._table = self._build_sites_table()
        self._table.doubleClicked.connect(self._on_table_double_click)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_table_context_menu)
        self._tabs.addTab(self._table, "Мониторинг")

        # Threats tab
        self._threats_table = self._build_threats_table()
        self._tabs.addTab(self._threats_table, "Угрозы")

        # History tab
        self._history_table = self._build_history_table()
        self._tabs.addTab(self._history_table, "История")

        # Bottom status
        self._last_check_label = QLabel("Последняя проверка: —")
        self._last_check_label.setStyleSheet(f"color:{TEXT_DIM}; font-size:11px;")
        vbox.addWidget(self._last_check_label)

        # Status bar
        self.statusBar().showMessage("Готово")

    def _build_stats_bar(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(80)
        h = QHBoxLayout(w)
        h.setSpacing(12)
        h.setContentsMargins(0, 0, 0, 0)

        self._stat_total   = self._stat_box("Всего",    "0", "#1565C0")
        self._stat_online  = self._stat_box("Онлайн",   "0", GREEN)
        self._stat_offline = self._stat_box("Офлайн",   "0", RED)
        self._stat_threats = self._stat_box("Угрозы",   "0", YELLOW)
        self._stat_avg     = self._stat_box("Ср.время", "—", "#9C27B0")

        h.addWidget(self._stat_total)
        h.addWidget(self._stat_online)
        h.addWidget(self._stat_offline)
        h.addWidget(self._stat_threats)
        h.addWidget(self._stat_avg)
        h.addStretch()
        return w

    def _stat_box(self, title: str, value: str, color: str) -> QLabel:
        lbl = QLabel(f"<b style='font-size:22px;color:{color}'>{value}</b><br>"
                     f"<span style='color:{TEXT_DIM};font-size:11px'>{title}</span>")
        lbl.setObjectName("stat_box")
        lbl.setFixedSize(130, 70)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        return lbl

    def _build_sites_table(self) -> QTableWidget:
        t = QTableWidget(0, 7)
        t.setHorizontalHeaderLabels([
            "Домен", "Статус", "Код", "Время (мс)", "SSL (дней)", "Угрозы", "Последняя проверка"
        ])
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 7):
            t.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setAlternatingRowColors(True)
        t.setStyleSheet(t.styleSheet() + "QTableWidget{alternate-background-color:#151528;}")
        t.verticalHeader().setVisible(False)
        return t

    def _build_threats_table(self) -> QTableWidget:
        t = QTableWidget(0, 5)
        t.setHorizontalHeaderLabels([
            "Домен", "Тип угрозы", "Описание", "Время обнаружения", "Статус"
        ])
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        t.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setAlternatingRowColors(True)
        t.setStyleSheet(t.styleSheet() + "QTableWidget{alternate-background-color:#151528;}")
        t.verticalHeader().setVisible(False)
        return t

    def _build_history_table(self) -> QTableWidget:
        t = QTableWidget(0, 5)
        t.setHorizontalHeaderLabels(["Домен", "Дата", "Время ответа", "Код", "Статус"])
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 5):
            t.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setAlternatingRowColors(True)
        t.setStyleSheet(t.styleSheet() + "QTableWidget{alternate-background-color:#151528;}")
        t.verticalHeader().setVisible(False)
        return t

    # ------------------------------------------------------------------
    # Context menu & double-click
    # ------------------------------------------------------------------
    def _on_table_double_click(self, index):
        row = index.row()
        domains = _load_sites()
        if 0 <= row < len(domains):
            self._open_site_detail(domains[row])

    def _on_table_context_menu(self, pos):
        row = self._table.rowAt(pos.y())
        domains = _load_sites()
        if row < 0 or row >= len(domains):
            return
        domain = domains[row]

        menu = QMenu(self)
        menu.setStyleSheet(f"background:{DARK_PANEL}; color:{TEXT_MAIN}; border:1px solid {DARK_BORDER};")

        act_check = menu.addAction("Проверить сейчас")
        act_detail = menu.addAction("Подробности")
        menu.addSeparator()
        act_delete = menu.addAction("Удалить")

        action = menu.exec(self._table.viewport().mapToGlobal(pos))
        if action == act_check:
            self._check_single_site(domain)
        elif action == act_detail:
            self._open_site_detail(domain)
        elif action == act_delete:
            self._delete_site(domain)

    def _open_site_detail(self, domain: str):
        from ui.site_detail_dialog import SiteDetailDialog
        status = self._site_status.get(domain, {})
        history = self._history.get(domain, [])
        dlg = SiteDetailDialog(domain, status, history, parent=self)
        dlg.check_requested.connect(self._check_single_site)
        dlg.delete_requested.connect(self._delete_site)
        dlg.exec()

    def _check_single_site(self, domain: str):
        settings = self._notifier.get_settings()
        thread = MonitorEngine(
            [domain],
            timeout=settings.get("monitor_timeout", 15),
            threat_scan=settings.get("threat_scan_enabled", True),
            scan_every_n=1,  # force scan on manual check
            parent=self,
        )
        thread.results_ready.connect(self._on_results)
        thread.start()
        self.statusBar().showMessage(f"Проверяем {domain}…")

    def _delete_site(self, domain: str):
        sites = _load_sites()
        if domain in sites:
            sites.remove(domain)
            _save_sites(sites)
            self._site_status.pop(domain, None)
            self._refresh_table()
            self._refresh_threats_tab()
            self._refresh_history_tab()
            self.statusBar().showMessage(f"Удалён: {domain}")

    # ------------------------------------------------------------------
    # Tray
    # ------------------------------------------------------------------
    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(self._icon, self)
        self._tray.setToolTip("SiteGuard Monitor Pro")

        menu = QMenu()
        menu.setStyleSheet(f"background:{DARK_PANEL}; color:{TEXT_MAIN}; border:1px solid {DARK_BORDER};")
        act_show = menu.addAction("Показать окно")
        act_show.triggered.connect(self._bring_to_front)
        menu.addSeparator()
        act_check = menu.addAction("Проверить сейчас")
        act_check.triggered.connect(self._run_monitor_forced)
        menu.addSeparator()
        act_quit = menu.addAction("Выход")
        act_quit.triggered.connect(self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _bring_to_front(self):
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._bring_to_front()

    # ------------------------------------------------------------------
    # Single instance
    # ------------------------------------------------------------------
    def _on_show_request(self):
        conn = self._local_server.nextPendingConnection()
        if conn:
            conn.waitForReadyRead(200)
            conn.disconnectFromServer()
        self._bring_to_front()

    # ------------------------------------------------------------------
    # Close / Quit
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        if self._tray and self._tray.isVisible():
            reply = QMessageBox.question(
                self,
                "SiteGuard Monitor",
                "Свернуть в трей (мониторинг продолжится) или выйти?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                event.ignore()
                self.hide()
                self._tray.showMessage(
                    "SiteGuard Monitor",
                    "Свёрнут в трей. Двойной клик для открытия.",
                    QSystemTrayIcon.MessageIcon.Information, 2500,
                )
                return
            elif reply == QMessageBox.StandardButton.No:
                self._quit()
            else:
                event.ignore()
        else:
            reply = QMessageBox.question(
                self, "Выход",
                "Закрыть SiteGuard Monitor?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._quit()
            else:
                event.ignore()

    def _quit(self):
        if self._monitor_thread and self._monitor_thread.isRunning():
            self._monitor_thread.stop_gracefully()
            self._monitor_thread.wait(2000)
        if self._tray:
            self._tray.hide()
        QApplication.quit()

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def _initial_load(self):
        self._update_license_bar()
        self._refresh_table()
        self._refresh_threats_tab()
        self._refresh_history_tab()
        domains = _load_sites()
        if domains:
            self.statusBar().showMessage(f"Запускаем проверку {len(domains)} сайтов…")
            self._run_monitor()
        else:
            self.statusBar().showMessage("Добавьте сайты для мониторинга через меню «Файл → Добавить сайты»")

    def _run_monitor(self):
        domains = _load_sites()
        if not domains:
            return
        if self._monitor_thread and self._monitor_thread.isRunning():
            return
        settings = self._notifier.get_settings()
        self._monitor_thread = MonitorEngine(
            domains,
            timeout=settings.get("monitor_timeout", 15),
            threat_scan=settings.get("threat_scan_enabled", True),
            scan_every_n=settings.get("threat_scan_every_n", 10),
            parent=self,
        )
        self._monitor_thread.results_ready.connect(self._on_results)
        self._monitor_thread.start()
        self.statusBar().showMessage(f"Проверяем {len(domains)} сайтов…")

    def _run_monitor_forced(self):
        if self._monitor_thread and self._monitor_thread.isRunning():
            self._monitor_thread.stop_gracefully()
            self._monitor_thread.wait(1000)
        self._run_monitor()

    def _on_results(self, results: dict):
        old_status = dict(self._site_status)
        self._site_status.update(results)
        self._save_history(results)
        self._refresh_table()
        self._refresh_threats_tab()
        self._refresh_history_tab()

        # Send notifications
        try:
            self._notifier.check_and_notify(old_status, results)
        except Exception:
            pass

        now = datetime.now().strftime("%H:%M:%S")
        self._last_check_label.setText(f"Последняя проверка: {now}")
        up = sum(1 for v in results.values() if v.get("up"))
        threats = sum(len(v.get("threats", [])) for v in self._site_status.values())
        self.statusBar().showMessage(
            f"Проверено {len(results)} сайтов: {up} онлайн, {len(results)-up} офлайн, {threats} угроз"
        )

    # ------------------------------------------------------------------
    # History persistence
    # ------------------------------------------------------------------
    def _save_history(self, results: dict):
        now = datetime.now().isoformat()
        for domain, info in results.items():
            if domain not in self._history:
                self._history[domain] = []
            self._history[domain].append({
                "time": now,
                "up": info["up"],
                "status_code": info["status_code"],
                "response_ms": info["response_ms"],
            })
            self._history[domain] = self._history[domain][-100:]
        try:
            _history_file().write_text(
                json.dumps(self._history, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Refresh tables
    # ------------------------------------------------------------------
    def _refresh_table(self):
        domains = _load_sites()
        self._table.setRowCount(len(domains))
        for row, domain in enumerate(domains):
            info = self._site_status.get(domain, {})
            up = info.get("up")
            code = info.get("status_code", 0)
            ms = info.get("response_ms", 0)
            ssl_d = info.get("ssl_days")
            last = info.get("last_check", "—")
            threats = info.get("threats", [])
            error = info.get("error")

            if up is None:
                status_text, status_color = "⏳ Ожидание", TEXT_DIM
            elif up:
                status_text, status_color = "✓ Онлайн", GREEN
            elif code >= 500:
                status_text, status_color = "⚠ Ошибка", YELLOW
            else:
                status_text, status_color = "✗ Офлайн", RED

            ms_text = f"{ms}" if ms else "—"
            ssl_text = f"{ssl_d}" if ssl_d is not None else "—"
            code_text = str(code) if code else "—"
            threats_text = str(len(threats)) if threats else "0"
            threats_color = YELLOW if threats else TEXT_DIM

            items = [
                (domain, TEXT_MAIN),
                (status_text, status_color),
                (code_text, TEXT_DIM),
                (ms_text, TEXT_DIM),
                (ssl_text, YELLOW if ssl_d is not None and ssl_d < 30 else TEXT_DIM),
                (threats_text, threats_color),
                (last, TEXT_DIM),
            ]
            for col, (text, color) in enumerate(items):
                item = QTableWidgetItem(text)
                item.setForeground(QBrush(QColor(color)))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row, col, item)

        # Update stats
        total = len(domains)
        up_count = sum(1 for d in domains if self._site_status.get(d, {}).get("up") is True)
        off_count = sum(1 for d in domains if self._site_status.get(d, {}).get("up") is False)
        threat_count = sum(len(self._site_status.get(d, {}).get("threats", [])) for d in domains)
        times = [self._site_status[d]["response_ms"]
                 for d in domains
                 if d in self._site_status and self._site_status[d].get("response_ms")]
        avg = f"{int(sum(times)/len(times))} мс" if times else "—"

        def _set_stat(lbl: QLabel, val: str, title: str, color: str):
            lbl.setText(f"<b style='font-size:22px;color:{color}'>{val}</b><br>"
                        f"<span style='color:{TEXT_DIM};font-size:11px'>{title}</span>")

        _set_stat(self._stat_total,   str(total),        "Всего",    "#1565C0")
        _set_stat(self._stat_online,  str(up_count),     "Онлайн",   GREEN)
        _set_stat(self._stat_offline, str(off_count),    "Офлайн",   RED)
        _set_stat(self._stat_threats, str(threat_count), "Угрозы",   YELLOW)
        _set_stat(self._stat_avg,     avg,               "Ср.время", "#9C27B0")

    def _refresh_threats_tab(self):
        all_threats = []
        for domain, info in self._site_status.items():
            for t in info.get("threats", []):
                all_threats.append((domain, t))

        if not all_threats:
            self._threats_table.setRowCount(1)
            item = QTableWidgetItem("Угроз не обнаружено")
            item.setForeground(QBrush(QColor(GREEN)))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._threats_table.setItem(0, 0, item)
            for col in range(1, 5):
                empty = QTableWidgetItem("")
                empty.setFlags(empty.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._threats_table.setItem(0, col, empty)
            return

        self._threats_table.setRowCount(len(all_threats))
        for row, (domain, t) in enumerate(all_threats):
            items = [
                (domain, TEXT_MAIN),
                (t.get("type", ""), YELLOW),
                (t.get("desc", ""), TEXT_MAIN),
                (t.get("time", ""), TEXT_DIM),
                ("Обнаружена", RED),
            ]
            for col, (text, color) in enumerate(items):
                item = QTableWidgetItem(text)
                item.setForeground(QBrush(QColor(color)))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._threats_table.setItem(row, col, item)

    def _refresh_history_tab(self):
        # Flatten history — show most recent entries across all domains
        entries = []
        for domain, checks in self._history.items():
            for check in checks[-20:]:  # last 20 per domain for display
                entries.append((domain, check))
        # Sort by time descending
        entries.sort(key=lambda x: x[1].get("time", ""), reverse=True)
        entries = entries[:200]  # limit total display

        self._history_table.setRowCount(len(entries))
        for row, (domain, check) in enumerate(entries):
            up = check.get("up")
            status_text = "✓ Онлайн" if up else "✗ Офлайн"
            status_color = GREEN if up else RED

            items = [
                (domain, TEXT_MAIN),
                (check.get("time", "—"), TEXT_DIM),
                (f"{check.get('response_ms', 0)} мс", TEXT_DIM),
                (str(check.get("status_code", 0)), TEXT_DIM),
                (status_text, status_color),
            ]
            for col, (text, color) in enumerate(items):
                item = QTableWidgetItem(text)
                item.setForeground(QBrush(QColor(color)))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._history_table.setItem(row, col, item)

    # ------------------------------------------------------------------
    # License
    # ------------------------------------------------------------------
    def _update_license_bar(self):
        info = self._lm.get_license_info()
        if not info:
            self._license_label.setText("⚠ Лицензия не активирована")
            self._license_label.setStyleSheet(f"color:{YELLOW}; padding:0 12px;")
            return
        plan = info.get("plan", "—")
        days = info.get("days_remaining", 0)
        color = GREEN if days > 30 else YELLOW if days > 10 else RED
        self._license_label.setText(f"✓ {plan}  —  {days}д")
        self._license_label.setStyleSheet(f"color:{color}; padding:0 12px;")

    def _activate_license(self):
        dlg = LicenseDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            key = dlg.get_key()
            if key:
                self._lm.store_license_key(key)
                self._update_license_bar()
                QMessageBox.information(self, "Лицензия", f"Лицензия активирована!\nПлан: {dlg.get_plan()}")

    def _show_license_info(self):
        info = self._lm.get_license_info()
        if not info:
            QMessageBox.information(self, "Лицензия", "Ключ не активирован.\nИспользуйте меню Лицензия → Активировать.")
            return
        key = info.get("license_key", "—")
        plan = info.get("plan", "—")
        days = info.get("days_remaining", 0)
        max_sites = info.get("max_sites", 0)
        QMessageBox.information(
            self, "Информация о лицензии",
            f"Ключ: {key}\nПлан: {plan}\nДней осталось: {days}\nМакс. сайтов: {max_sites}"
        )

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    def _open_settings(self):
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self._notifier, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Reload timer interval from settings
            settings = self._notifier.get_settings()
            interval_ms = settings.get("monitor_interval", 60) * 1000
            self._timer.setInterval(interval_ms)
            self.statusBar().showMessage("Настройки сохранены")

    def _show_about(self):
        QMessageBox.about(
            self, "О программе",
            "SiteGuard Monitor Pro v2.0.0\n\n"
            "Мониторинг сайтов с обнаружением угроз,\n"
            "email-уведомлениями и историей проверок.\n\n"
            "© SiteGuard 2024"
        )

    # ------------------------------------------------------------------
    # Site management
    # ------------------------------------------------------------------
    def _add_sites_dialog(self):
        existing = _load_sites()
        dlg = AddSitesDialog(existing, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_domains = dlg.get_domains()
            if new_domains:
                sites = _load_sites()
                sites.extend(new_domains)
                _save_sites(sites)
                self._refresh_table()
                self.statusBar().showMessage(f"Добавлено {len(new_domains)} сайтов")
                QTimer.singleShot(300, self._run_monitor)
            else:
                self.statusBar().showMessage("Нет новых сайтов для добавления")

    def _remove_site_dialog(self):
        sites = _load_sites()
        if not sites:
            QMessageBox.information(self, "Удалить", "Нет сайтов.")
            return
        domain, ok = QInputDialog.getItem(
            self, "Удалить сайт", "Выберите сайт:", sites, editable=False
        )
        if ok and domain:
            self._delete_site(domain)
