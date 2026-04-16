"""
SiteGuard Monitor Pro - Main Application Window  (v1.1.1 — Offline-First)

QMainWindow with menu bar, toolbar, tab widget (Dashboard + Site Details),
status bar, system tray icon.  Background QThread monitors sites every 60 s
using only stdlib urllib / ssl — no external HTTP libraries.
Local sites.json for site list, local license.json for licensing.
Dark theme (#0f0f23).
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
from typing import Dict, List

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QLabel,
    QToolBar,
    QMenu,
    QSystemTrayIcon,
    QPushButton,
    QMessageBox,
    QFrame,
    QGridLayout,
    QApplication,
    QFileDialog,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QInputDialog,
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QAction, QColor, QFont

from core.license_manager import LicenseManager

logger = logging.getLogger("SiteGuard.MainWindow")


# ---------------------------------------------------------------------------
# Background monitoring worker
# ---------------------------------------------------------------------------
class MonitorWorker(QObject):
    """Runs site checks in a background QThread."""

    results_ready = pyqtSignal(dict)  # {domain: {...status info...}}
    finished = pyqtSignal()

    def __init__(self, domains: List[str]):
        super().__init__()
        self._domains = list(domains)
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        results: Dict[str, dict] = {}
        for domain in self._domains:
            if not self._running:
                break
            results[domain] = self._check_single(domain)
        self.results_ready.emit(results)
        self.finished.emit()

    # -- per-site check --
    def _check_single(self, domain: str) -> dict:
        status_code = 0
        response_ms = 0.0
        is_up = False
        ssl_days = None

        # HTTP(S) reachability
        for scheme in ("https", "http"):
            url = f"{scheme}://{domain}"
            try:
                t0 = time.time()
                req = urllib.request.Request(url, method="HEAD")
                req.add_header("User-Agent", "SiteGuard-Monitor/1.1.1")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    status_code = resp.status
                    response_ms = round((time.time() - t0) * 1000)
                    is_up = status_code < 400
                break  # success — no need to try fallback
            except urllib.error.HTTPError as exc:
                status_code = exc.code
                response_ms = round((time.time() - t0) * 1000)
                is_up = status_code < 400
                break
            except Exception:
                continue

        # SSL certificate expiry check
        try:
            ctx = ssl.create_default_context()
            with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
                s.settimeout(10)
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
# Dashboard Widget
# ---------------------------------------------------------------------------
class DashboardWidget(QWidget):
    """Dashboard tab showing overview of all monitored sites."""

    site_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # -- Summary cards --
        cards_layout = QHBoxLayout()
        self.card_total = self._make_card("Total Sites", "0", "#4a90d9")
        self.card_up = self._make_card("Online", "0", "#00e676")
        self.card_down = self._make_card("Offline", "0", "#ff6b6b")
        self.card_avg = self._make_card("Avg Response", "—", "#ff9100")
        cards_layout.addWidget(self.card_total)
        cards_layout.addWidget(self.card_up)
        cards_layout.addWidget(self.card_down)
        cards_layout.addWidget(self.card_avg)
        layout.addLayout(cards_layout)

        # -- Sites table --
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Domain", "Status", "Response Time", "SSL Days", "Last Check"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            """
            QTableWidget {
                background-color: #16213e;
                alternate-background-color: #1a2745;
                border: 1px solid #2a2a5e;
                border-radius: 8px;
                gridline-color: #2a2a5e;
                color: #e0e0e0;
                font-size: 13px;
            }
            QTableWidget::item:selected {
                background-color: #4a90d9;
            }
            QHeaderView::section {
                background-color: #0a0a1a;
                color: #a0a0b0;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #4a90d9;
                font-weight: bold;
            }
            """
        )
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table)

    @staticmethod
    def _make_card(title: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setFixedHeight(100)
        card.setStyleSheet(
            f"""
            QFrame {{
                background-color: #16213e;
                border: 1px solid #2a2a5e;
                border-radius: 10px;
                border-left: 4px solid {color};
            }}
            """
        )
        card_layout = QVBoxLayout(card)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #a0a0b0; font-size: 12px;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_value = QLabel(value)
        lbl_value.setObjectName("card_value")
        lbl_value.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold;")
        lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(lbl_title)
        card_layout.addWidget(lbl_value)
        return card

    def _on_row_double_clicked(self, row: int, _col: int):
        domain_item = self.table.item(row, 0)
        if domain_item:
            self.site_selected.emit(domain_item.text())

    def update_from_status(self, domains: List[str], site_status: Dict[str, dict]):
        """Refresh the dashboard table and cards from local monitoring data."""
        total = len(domains)
        up = sum(1 for d in domains if site_status.get(d, {}).get("up", False))
        down = total - up
        resp_times = [
            site_status[d]["response_ms"]
            for d in domains
            if d in site_status and site_status[d].get("up")
        ]
        avg_resp = f"{round(sum(resp_times) / len(resp_times))} ms" if resp_times else "\u2014"

        self.card_total.findChild(QLabel, "card_value").setText(str(total))
        self.card_up.findChild(QLabel, "card_value").setText(str(up))
        self.card_down.findChild(QLabel, "card_value").setText(str(down))
        self.card_avg.findChild(QLabel, "card_value").setText(avg_resp)

        self.table.setRowCount(total)
        for i, domain in enumerate(domains):
            info = site_status.get(domain, {})
            is_up = info.get("up", False)

            # Domain
            self.table.setItem(i, 0, QTableWidgetItem(domain))

            # Status
            status_item = QTableWidgetItem("\u2713 Online" if is_up else "\u2717 Offline")
            status_item.setForeground(QColor("#00e676") if is_up else QColor("#ff6b6b"))
            self.table.setItem(i, 1, status_item)

            # Response time
            resp = f"{info['response_ms']} ms" if info.get("response_ms") else "\u2014"
            self.table.setItem(i, 2, QTableWidgetItem(resp))

            # SSL days
            ssl_d = info.get("ssl_days")
            if ssl_d is not None:
                ssl_text = "Expired" if ssl_d < 0 else f"{ssl_d}d"
            else:
                ssl_text = "\u2014"
            self.table.setItem(i, 3, QTableWidgetItem(ssl_text))

            # Last check
            self.table.setItem(i, 4, QTableWidgetItem(info.get("last_check", "\u2014")))


# ---------------------------------------------------------------------------
# Site Detail Widget
# ---------------------------------------------------------------------------
class SiteDetailWidget(QWidget):
    """Detail tab for a selected site."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.header_label = QLabel("Select a site from the Dashboard to view details")
        self.header_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.header_label.setStyleSheet("color: #4a90d9;")
        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.header_label)

        self.info_frame = QFrame()
        self.info_frame.setStyleSheet(
            """
            QFrame {
                background-color: #16213e;
                border: 1px solid #2a2a5e;
                border-radius: 10px;
            }
            """
        )
        info_layout = QGridLayout(self.info_frame)
        info_layout.setSpacing(12)

        labels = [
            ("Status:", "status_val"),
            ("Domain:", "domain_val"),
            ("Response Time:", "response_val"),
            ("SSL Certificate:", "ssl_val"),
            ("SSL Days Left:", "ssl_days_val"),
            ("Last Check:", "last_check_val"),
        ]
        self._info_labels = {}
        for row, (title, name) in enumerate(labels):
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet("color: #a0a0b0; font-size: 13px; padding: 4px;")
            value_lbl = QLabel("-")
            value_lbl.setStyleSheet("color: #e0e0e0; font-size: 13px; font-weight: bold; padding: 4px;")
            info_layout.addWidget(title_lbl, row, 0)
            info_layout.addWidget(value_lbl, row, 1)
            self._info_labels[name] = value_lbl

        layout.addWidget(self.info_frame)
        layout.addStretch()

    def update_from_status(self, domain: str, info: dict):
        """Populate detail view from local monitoring result."""
        self.header_label.setText(f"Site Details: {domain}")
        is_up = info.get("up", False)
        status_text = "Online" if is_up else "OFFLINE"
        status_color = "#00e676" if is_up else "#ff6b6b"

        self._info_labels["status_val"].setText(status_text)
        self._info_labels["status_val"].setStyleSheet(
            f"color: {status_color}; font-size: 13px; font-weight: bold; padding: 4px;"
        )
        self._info_labels["domain_val"].setText(domain)
        resp = f'{info.get("response_ms", "-")} ms'
        self._info_labels["response_val"].setText(resp)

        ssl_d = info.get("ssl_days")
        if ssl_d is not None:
            self._info_labels["ssl_val"].setText("Valid" if ssl_d >= 0 else "Expired")
            self._info_labels["ssl_days_val"].setText(f"{ssl_d} days")
        else:
            self._info_labels["ssl_val"].setText("\u2014")
            self._info_labels["ssl_days_val"].setText("\u2014")

        self._info_labels["last_check_val"].setText(info.get("last_check", "\u2014"))


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """Main application window — offline-first, dark theme."""

    def __init__(self, setup_data: dict | None = None):
        super().__init__()
        self.setup_data = setup_data or {}
        self.license_manager = LicenseManager()

        # Local monitoring state
        self._site_status: Dict[str, dict] = {}
        self._monitor_thread: QThread | None = None
        self._monitor_worker: MonitorWorker | None = None

        # Window properties
        self.setWindowTitle("SiteGuard Monitor Pro")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        # Build UI
        self._apply_dark_theme()
        self._create_menu_bar()
        self._create_toolbar()
        self._create_central_widget()
        self._create_status_bar()
        self._create_tray_icon()

        # Monitoring timer (60 seconds)
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._start_monitoring_thread)
        self.monitor_timer.start(60_000)

        # License check timer (24 hours)
        self.license_timer = QTimer(self)
        self.license_timer.timeout.connect(self._check_license)
        self.license_timer.start(86_400_000)

        # Initial load after 1 second
        QTimer.singleShot(1000, self._initial_load)

    # ==================================================================
    # Local site storage  (%APPDATA%/SiteGuard Monitor/sites.json)
    # ==================================================================
    def _get_sites_file(self) -> Path:
        base = os.getenv("APPDATA", str(Path.home()))
        return Path(base) / "SiteGuard Monitor" / "sites.json"

    def _load_sites(self) -> List[str]:
        f = self._get_sites_file()
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return [str(d) for d in data]
            except Exception:
                logger.warning("Could not read sites.json")
        return []

    def _save_sites(self, domains: List[str]):
        f = self._get_sites_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(domains, indent=2), encoding="utf-8")

    # ==================================================================
    # Theme
    # ==================================================================
    def _apply_dark_theme(self):
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #0f0f23;
            }
            QWidget {
                background-color: #0f0f23;
                color: #e0e0e0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QTabWidget::pane {
                background-color: #1a1a2e;
                border: 1px solid #2a2a5e;
                border-radius: 8px;
            }
            QTabBar::tab {
                background-color: #16213e;
                color: #a0a0b0;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background-color: #1a1a2e;
                color: #ffffff;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #1a2745;
            }
            QMenuBar {
                background-color: #0a0a1a;
                color: #e0e0e0;
                border-bottom: 1px solid #2a2a5e;
                padding: 4px;
            }
            QMenuBar::item:selected {
                background-color: #4a90d9;
                border-radius: 4px;
            }
            QMenu {
                background-color: #16213e;
                color: #e0e0e0;
                border: 1px solid #2a2a5e;
            }
            QMenu::item:selected {
                background-color: #4a90d9;
            }
            QToolBar {
                background-color: #0a0a1a;
                border-bottom: 1px solid #2a2a5e;
                spacing: 5px;
                padding: 5px;
            }
            QStatusBar {
                background-color: #0a0a1a;
                color: #a0a0b0;
                border-top: 1px solid #2a2a5e;
            }
            QPushButton {
                background-color: #4a90d9;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #5aa0e9;
            }
            QPushButton:pressed {
                background-color: #3a80c9;
            }
            QScrollBar:vertical {
                background: #0f0f23;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.2);
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255,255,255,0.3);
            }
            """
        )

    # ==================================================================
    # Menu bar
    # ==================================================================
    def _create_menu_bar(self):
        menubar = self.menuBar()

        # -- File --
        file_menu = menubar.addMenu("File")

        add_site_action = QAction("Add Site", self)
        add_site_action.setShortcut("Ctrl+N")
        add_site_action.triggered.connect(self._show_add_site)
        file_menu.addAction(add_site_action)

        remove_site_action = QAction("Remove Site", self)
        remove_site_action.triggered.connect(self._show_remove_site)
        file_menu.addAction(remove_site_action)

        file_menu.addSeparator()

        export_action = QAction("Export Report", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._export_report)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self._quit_app)
        file_menu.addAction(exit_action)

        # -- Monitoring --
        monitor_menu = menubar.addMenu("Monitoring")

        check_all_action = QAction("Check All Sites", self)
        check_all_action.setShortcut("F5")
        check_all_action.triggered.connect(self._check_all_now)
        monitor_menu.addAction(check_all_action)

        monitor_menu.addSeparator()

        self.pause_action = QAction("Pause Monitoring", self)
        self.pause_action.setCheckable(True)
        self.pause_action.triggered.connect(self._toggle_pause)
        monitor_menu.addAction(self.pause_action)

        # -- Settings --
        settings_menu = menubar.addMenu("Settings")

        settings_action = QAction("Preferences", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._show_settings)
        settings_menu.addAction(settings_action)

        notifications_action = QAction("Notifications", self)
        notifications_action.triggered.connect(self._show_notification_settings)
        settings_menu.addAction(notifications_action)

        settings_menu.addSeparator()

        license_action = QAction("License", self)
        license_action.triggered.connect(self._show_license_info)
        settings_menu.addAction(license_action)

        # -- Help --
        help_menu = menubar.addMenu("Help")

        docs_action = QAction("Documentation", self)
        docs_action.triggered.connect(self._open_docs)
        help_menu.addAction(docs_action)

        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    # ==================================================================
    # Toolbar
    # ==================================================================
    def _create_toolbar(self):
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        add_btn = QPushButton("Add Site")
        add_btn.clicked.connect(self._show_add_site)
        toolbar.addWidget(add_btn)

        toolbar.addSeparator()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._check_all_now)
        toolbar.addWidget(refresh_btn)

        check_btn = QPushButton("Check All")
        check_btn.clicked.connect(self._check_all_now)
        toolbar.addWidget(check_btn)

        toolbar.addSeparator()

        # License status label
        self.license_status_label = QLabel("License: loading...")
        self.license_status_label.setStyleSheet("padding: 5px 10px; font-size: 12px;")
        toolbar.addWidget(self.license_status_label)

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # Last update time
        self.last_update_label = QLabel("Updated: --")
        self.last_update_label.setStyleSheet("color: #888; font-size: 12px; padding-right: 10px;")
        toolbar.addWidget(self.last_update_label)

    # ==================================================================
    # Central widget (tabs)
    # ==================================================================
    def _create_central_widget(self):
        central = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)

        self.tabs = QTabWidget()

        self.dashboard = DashboardWidget(self)
        self.dashboard.site_selected.connect(self._on_site_selected)
        self.tabs.addTab(self.dashboard, "Dashboard")

        self.site_detail = SiteDetailWidget(self)
        self.tabs.addTab(self.site_detail, "Site Details")

        layout.addWidget(self.tabs)
        central.setLayout(layout)
        self.setCentralWidget(central)

    # ==================================================================
    # Status bar
    # ==================================================================
    def _create_status_bar(self):
        self.statusBar().showMessage("Ready")
        self.connection_label = QLabel("Offline-first mode")
        self.connection_label.setStyleSheet("color: #00e676; padding-right: 10px;")
        self.statusBar().addPermanentWidget(self.connection_label)

    # ==================================================================
    # System tray icon
    # ==================================================================
    def _create_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return

        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip("SiteGuard Monitor Pro")

        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show Window")
        show_action.triggered.connect(self._show_from_tray)
        tray_menu.addSeparator()
        check_action = tray_menu.addAction("Check All Sites")
        check_action.triggered.connect(self._check_all_now)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self._quit_app)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    # ==================================================================
    # Monitoring (background QThread)
    # ==================================================================
    def _initial_load(self):
        self._update_license_status()
        self._refresh_table()
        self._start_monitoring_thread()

    def _start_monitoring_thread(self):
        """Launch a background thread to check all sites."""
        if self._monitor_thread and self._monitor_thread.isRunning():
            return  # already running

        domains = self._load_sites()
        if not domains:
            self._refresh_table()
            return

        self._monitor_thread = QThread()
        self._monitor_worker = MonitorWorker(domains)
        self._monitor_worker.moveToThread(self._monitor_thread)

        self._monitor_thread.started.connect(self._monitor_worker.run)
        self._monitor_worker.results_ready.connect(self._on_monitor_results)
        self._monitor_worker.finished.connect(self._monitor_thread.quit)
        self._monitor_worker.finished.connect(self._monitor_worker.deleteLater)
        self._monitor_thread.finished.connect(self._monitor_thread.deleteLater)

        self.statusBar().showMessage("Checking sites...")
        self._monitor_thread.start()

    def _on_monitor_results(self, results: dict):
        """Called in the main thread when background check completes."""
        self._site_status.update(results)
        self._refresh_table()
        self.last_update_label.setText(
            f"Updated: {datetime.now().strftime('%H:%M:%S')}"
        )
        total = len(self._load_sites())
        up = sum(1 for v in results.values() if v.get("up"))
        self.statusBar().showMessage(
            f"Check complete \u2014 {total} sites, {up} online"
        )

    def _refresh_table(self):
        """Redraw the dashboard table from current local data."""
        domains = self._load_sites()
        self.dashboard.update_from_status(domains, self._site_status)

    # ==================================================================
    # Event handlers
    # ==================================================================
    def _on_site_selected(self, domain: str):
        info = self._site_status.get(domain)
        if info:
            self.site_detail.update_from_status(domain, info)
            self.tabs.setCurrentIndex(1)
        else:
            self.statusBar().showMessage(f"No data yet for {domain}")

    def _show_add_site(self):
        domain, ok = QInputDialog.getText(
            self, "Add Site", "Domain (e.g. example.com):"
        )
        domain = domain.strip().lower() if ok else ""
        if not domain:
            return

        # Strip protocol if user included it
        for prefix in ("https://", "http://"):
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
        domain = domain.rstrip("/")

        sites = self._load_sites()
        if domain in sites:
            QMessageBox.information(self, "Duplicate", f"{domain} is already monitored.")
            return

        sites.append(domain)
        self._save_sites(sites)
        self._refresh_table()
        self.statusBar().showMessage(f"Added {domain}")
        # Trigger an immediate check
        self._start_monitoring_thread()

    def _show_remove_site(self):
        sites = self._load_sites()
        if not sites:
            QMessageBox.information(self, "Remove Site", "No sites to remove.")
            return

        domain, ok = QInputDialog.getItem(
            self, "Remove Site", "Select site:", sites, editable=False
        )
        if ok and domain:
            sites.remove(domain)
            self._save_sites(sites)
            self._site_status.pop(domain, None)
            self._refresh_table()
            self.statusBar().showMessage(f"Removed {domain}")

    def _check_all_now(self):
        self._start_monitoring_thread()

    def _toggle_pause(self, paused: bool):
        if paused:
            self.monitor_timer.stop()
            self.statusBar().showMessage("Monitoring paused")
            self.pause_action.setText("Resume Monitoring")
        else:
            self.monitor_timer.start(60_000)
            self.statusBar().showMessage("Monitoring resumed")
            self.pause_action.setText("Pause Monitoring")
            self._start_monitoring_thread()

    def _show_settings(self):
        QMessageBox.information(self, "Settings", "Settings dialog \u2014 coming soon.")

    def _show_notification_settings(self):
        QMessageBox.information(self, "Notifications", "Notification settings \u2014 coming soon.")

    def _show_license_info(self):
        info = self.license_manager.get_license_info()
        if info:
            plan = info.get("plan", "Unknown")
            days = info.get("days_remaining", 0)
            max_sites = info.get("max_sites", 0)
            key = info.get("license_key", "")
            masked = key[:8] + "****-****-" + key[-5:] if len(key) > 15 else key
            QMessageBox.information(
                self,
                "License",
                f"Key: {masked}\n"
                f"Plan: {plan}\n"
                f"Remaining: {days} days\n"
                f"Max Sites: {max_sites}",
            )
        else:
            QMessageBox.warning(self, "License", "Could not retrieve license information.")

    def _update_license_status(self):
        info = self.license_manager.get_license_info()
        if info:
            plan = info.get("plan", "?")
            days = info.get("days_remaining", 0)
            if days < 10:
                color = "#ff6b6b"
            elif days <= 30:
                color = "#ff9100"
            else:
                color = "#00e676"
            text = f"{plan} \u2014 {days}d remaining"
            self.license_status_label.setText(text)
            self.license_status_label.setStyleSheet(
                f"color: {color}; padding: 5px 10px; font-size: 12px;"
            )
        else:
            self.license_status_label.setText("License: not found")
            self.license_status_label.setStyleSheet(
                "color: #ff6b6b; padding: 5px 10px;"
            )

    def _check_license(self):
        is_valid = self.license_manager.validate()
        if not is_valid:
            QMessageBox.critical(
                self,
                "License",
                "License is invalid!\n\nPlease renew your license to continue.",
            )
        self._update_license_status()

    def _export_report(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Report",
            f"siteguard_report_{datetime.now().strftime('%Y%m%d')}.json",
            "JSON (*.json);;HTML (*.html)",
        )
        if not filepath:
            return
        domains = self._load_sites()
        report = {
            "generated": datetime.now().isoformat(),
            "sites": {d: self._site_status.get(d, {}) for d in domains},
        }
        try:
            Path(filepath).write_text(
                json.dumps(report, indent=2, default=str), encoding="utf-8"
            )
            QMessageBox.information(self, "Export", f"Report saved: {filepath}")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _open_docs(self):
        import webbrowser
        webbrowser.open("https://siteguard.app/docs")

    def _show_about(self):
        QMessageBox.about(
            self,
            "About",
            "<h2>SiteGuard Monitor Pro</h2>"
            "<p>Version 1.1.1</p>"
            "<p>24/7 Offline-First Site Monitoring</p>"
            "<p>&copy; 2024 SiteGuard. All rights reserved.</p>"
            '<p><a href="https://siteguard.app">siteguard.app</a></p>',
        )

    # -- Tray helpers --
    def _show_from_tray(self):
        self.showNormal()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_from_tray()

    def _quit_app(self):
        if self._monitor_worker:
            self._monitor_worker.stop()
        if self.tray:
            self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        if self.tray and self.tray.isVisible():
            self.hide()
            self.tray.showMessage(
                "SiteGuard Monitor",
                "Application minimized to tray. Monitoring continues.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
            event.ignore()
        else:
            if self._monitor_worker:
                self._monitor_worker.stop()
            event.accept()
