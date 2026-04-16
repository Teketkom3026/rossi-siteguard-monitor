"""
SiteGuard Monitor Pro — Main Window v1.2.0
Офлайн-мониторинг сайтов. Простой и надёжный.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import ssl
import time
import urllib.request
import urllib.error
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
    Qt, QTimer, QThread, QObject, pyqtSignal, QSize,
)
from PyQt6.QtGui import (
    QAction, QColor, QFont, QPixmap, QPainter, QIcon, QBrush,
)
from PyQt6.QtNetwork import QLocalServer

from core.license_manager import LicenseManager
from core.license_validator import validate_key

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
# Background monitor thread (QThread subclass — simpler, no deleteLater race)
# ---------------------------------------------------------------------------
class MonitorThread(QThread):
    results_ready = pyqtSignal(dict)

    def __init__(self, domains: List[str], parent=None):
        super().__init__(parent)
        self._domains = list(domains)
        self._stop = False

    def stop_gracefully(self):
        self._stop = True

    def run(self):
        results: Dict[str, dict] = {}
        for domain in self._domains:
            if self._stop:
                break
            results[domain] = self._check(domain)
        self.results_ready.emit(results)

    def _check(self, domain: str) -> dict:
        status_code = 0
        response_ms = 0.0
        is_up = False
        ssl_days = None

        for scheme in ("https", "http"):
            url = f"{scheme}://{domain}"
            try:
                t0 = time.time()
                req = urllib.request.Request(url, method="HEAD")
                req.add_header("User-Agent", "SiteGuard-Monitor/1.2.0")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    status_code = resp.status
                    response_ms = round((time.time() - t0) * 1000)
                    is_up = status_code < 400
                break
            except urllib.error.HTTPError as exc:
                status_code = exc.code
                response_ms = round((time.time() - t0) * 1000)
                is_up = status_code < 400
                break
            except Exception:
                continue

        try:
            ctx = ssl.create_default_context()
            with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
                s.settimeout(8)
                s.connect((domain, 443))
                cert = s.getpeercert()
                if cert:
                    not_after = cert.get("notAfter", "")
                    expires_dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                    ssl_days = (expires_dt - datetime.utcnow()).days
        except Exception:
            ssl_days = None

        return {
            "up": is_up,
            "status_code": status_code,
            "response_ms": response_ms,
            "ssl_days": ssl_days,
            "last_check": datetime.now().strftime("%H:%M:%S"),
        }

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
# Main Window
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


class MainWindow(QMainWindow):
    """Главное окно SiteGuard Monitor Pro."""

    def __init__(self, setup_data: dict | None = None):
        super().__init__()
        self.setup_data = setup_data or {}
        self._lm = LicenseManager()
        self._site_status: Dict[str, dict] = {}
        self._monitor_thread: Optional[MonitorThread] = None
        self._icon = _make_icon()
        self._tray: Optional[QSystemTrayIcon] = None

        self.setWindowTitle("SiteGuard Monitor Pro v1.2.0")
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

        # Auto-refresh every 60 sec
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._run_monitor)
        self._timer.start(60_000)

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

        btn_license = QPushButton("  🔑 Лицензия")
        btn_license.clicked.connect(self._activate_license)
        tb.addWidget(btn_license)

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

        # Sites table
        self._table = self._build_table()
        vbox.addWidget(self._table, stretch=1)

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

        self._stat_total  = self._stat_box("Сайтов", "0", "#1565C0")
        self._stat_online = self._stat_box("Онлайн", "0", GREEN)
        self._stat_offline= self._stat_box("Офлайн", "0", RED)
        self._stat_avg    = self._stat_box("Ср. время", "—", "#9C27B0")

        h.addWidget(self._stat_total)
        h.addWidget(self._stat_online)
        h.addWidget(self._stat_offline)
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

    def _build_table(self) -> QTableWidget:
        t = QTableWidget(0, 6)
        t.setHorizontalHeaderLabels(["Домен", "Статус", "Код", "Время (мс)", "SSL (дней)", "Проверка"])
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 6):
            t.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setAlternatingRowColors(True)
        t.setStyleSheet(t.styleSheet() + "QTableWidget{alternate-background-color:#151528;}")
        t.verticalHeader().setVisible(False)
        return t

    # ------------------------------------------------------------------
    # Tray
    # ------------------------------------------------------------------
    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(self._icon, self)
        self._tray.setToolTip("SiteGuard Monitor Pro")

        menu = QMenu()
        menu.setStyleSheet("background:#1a1a2e; color:#e0e0e0; border:1px solid #333;")
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
        """X button — спрашиваем: свернуть или выйти."""
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
        domains = _load_sites()
        if domains:
            self.statusBar().showMessage(f"Запускаем проверку {len(domains)} сайтов…")
            self._run_monitor()
        else:
            self.statusBar().showMessage("Добавьте сайты для мониторинга через меню «Файл → Добавить сайты»")

    def _run_monitor(self):
        """Start background check. Only one thread at a time."""
        domains = _load_sites()
        if not domains:
            return
        if self._monitor_thread and self._monitor_thread.isRunning():
            return
        self._monitor_thread = MonitorThread(domains, parent=self)
        self._monitor_thread.results_ready.connect(self._on_results)
        self._monitor_thread.start()
        self.statusBar().showMessage(f"Проверяем {len(domains)} сайтов…")

    def _run_monitor_forced(self):
        """Force check even if thread running."""
        if self._monitor_thread and self._monitor_thread.isRunning():
            self._monitor_thread.stop_gracefully()
            self._monitor_thread.wait(1000)
        self._run_monitor()

    def _on_results(self, results: dict):
        self._site_status.update(results)
        self._refresh_table()
        now = datetime.now().strftime("%H:%M:%S")
        self._last_check_label.setText(f"Последняя проверка: {now}")
        up = sum(1 for v in results.values() if v.get("up"))
        total = len(results)
        self.statusBar().showMessage(f"Проверено: {total} сайтов. Онлайн: {up}, Офлайн: {total - up}")

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

            if up is None:
                status_text, status_color = "⏳ Ожидание", TEXT_DIM
            elif up:
                status_text, status_color = "✓ Онлайн", GREEN
            else:
                status_text, status_color = "✗ Офлайн", RED

            ms_text = f"{ms} мс" if ms else "—"
            ssl_text = f"{ssl_d}д" if ssl_d is not None else "—"
            code_text = str(code) if code else "—"

            items = [
                (domain, TEXT_MAIN),
                (status_text, status_color),
                (code_text, TEXT_DIM),
                (ms_text, TEXT_DIM),
                (ssl_text, YELLOW if ssl_d is not None and ssl_d < 30 else TEXT_DIM),
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
        times = [self._site_status[d]["response_ms"] for d in domains if d in self._site_status and self._site_status[d].get("response_ms")]
        avg = f"{int(sum(times)/len(times))} мс" if times else "—"

        def _set_stat(lbl: QLabel, val: str, title: str, color: str):
            lbl.setText(f"<b style='font-size:22px;color:{color}'>{val}</b><br>"
                        f"<span style='color:{TEXT_DIM};font-size:11px'>{title}</span>")

        _set_stat(self._stat_total,   str(total),    "Сайтов",   "#1565C0")
        _set_stat(self._stat_online,  str(up_count),  "Онлайн",   GREEN)
        _set_stat(self._stat_offline, str(off_count), "Офлайн",   RED)
        _set_stat(self._stat_avg,     avg,            "Ср. время", "#9C27B0")

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
                # Check new sites
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
            sites.remove(domain)
            _save_sites(sites)
            self._site_status.pop(domain, None)
            self._refresh_table()
            self.statusBar().showMessage(f"Удалён: {domain}")
