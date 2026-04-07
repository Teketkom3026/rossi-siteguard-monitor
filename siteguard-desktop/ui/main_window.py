"""
SiteGuard Monitor Pro - Main Application Window

QMainWindow with menu bar, toolbar, tab widget (Dashboard + Site Details),
status bar, system tray icon. 30s refresh timer, 24h license check timer.
Dark theme (#0f0f23).
"""
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QLabel,
    QStatusBar,
    QToolBar,
    QMenu,
    QSystemTrayIcon,
    QPushButton,
    QMessageBox,
    QSplitter,
    QFrame,
    QScrollArea,
    QGridLayout,
    QApplication,
    QFileDialog,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressBar,
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QAction, QFont, QColor, QPalette

from core.api_client import APIClient
from core.license_manager import LicenseManager


# ---------------------------------------------------------------------------
# Dashboard Widget (embedded)
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

        # -- Summary cards row --
        cards_layout = QHBoxLayout()
        self.card_total = self._make_card("Total Sites", "0", "#4a90d9")
        self.card_up = self._make_card("Online", "0", "#00e676")
        self.card_down = self._make_card("Offline", "0", "#ff6b6b")
        self.card_warnings = self._make_card("Warnings", "0", "#ff9100")
        cards_layout.addWidget(self.card_total)
        cards_layout.addWidget(self.card_up)
        cards_layout.addWidget(self.card_down)
        cards_layout.addWidget(self.card_warnings)
        layout.addLayout(cards_layout)

        # -- Sites table --
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Status", "Domain", "Response (ms)", "SSL", "Last Check", "Issues"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
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

    # -- helpers --
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
        domain_item = self.table.item(row, 1)
        if domain_item:
            self.site_selected.emit(domain_item.text())

    # -- public API --
    def update_data(self, data: dict):
        """Refresh the dashboard with new data from the API."""
        total = data.get("total_sites", 0)
        up = data.get("sites_up", 0)
        down = data.get("sites_down", 0)
        warnings = data.get("warnings", 0)

        self.card_total.findChild(QLabel, "card_value").setText(str(total))
        self.card_up.findChild(QLabel, "card_value").setText(str(up))
        self.card_down.findChild(QLabel, "card_value").setText(str(down))
        self.card_warnings.findChild(QLabel, "card_value").setText(str(warnings))

        sites = data.get("sites", [])
        self.table.setRowCount(len(sites))
        for i, site in enumerate(sites):
            status = site.get("status", "unknown")
            status_icon = {"up": "🟢", "down": "🔴", "warning": "🟡"}.get(status, "⚪")
            self.table.setItem(i, 0, QTableWidgetItem(status_icon))
            self.table.setItem(i, 1, QTableWidgetItem(site.get("domain", "")))
            self.table.setItem(i, 2, QTableWidgetItem(str(site.get("response_ms", "-"))))
            ssl_status = site.get("ssl_status", "unknown")
            ssl_icon = {"valid": "🟢", "expiring": "🟡", "expired": "🔴"}.get(ssl_status, "⚪")
            self.table.setItem(i, 3, QTableWidgetItem(ssl_icon))
            self.table.setItem(i, 4, QTableWidgetItem(site.get("last_check", "-")))
            self.table.setItem(i, 5, QTableWidgetItem(str(site.get("issues", 0))))


# ---------------------------------------------------------------------------
# Site Detail Widget (embedded)
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

        # Info grid
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
            ("IP Address:", "ip_val"),
            ("Response Time:", "response_val"),
            ("SSL Certificate:", "ssl_val"),
            ("SSL Expires:", "ssl_exp_val"),
            ("Last Check:", "last_check_val"),
            ("Uptime (30d):", "uptime_val"),
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

        # Issues list
        issues_label = QLabel("Active Issues")
        issues_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        issues_label.setStyleSheet("color: #ff9100; margin-top: 10px;")
        layout.addWidget(issues_label)

        self.issues_table = QTableWidget()
        self.issues_table.setColumnCount(4)
        self.issues_table.setHorizontalHeaderLabels(["Severity", "Type", "Description", "Detected"])
        ih = self.issues_table.horizontalHeader()
        ih.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        ih.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.issues_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.issues_table.setStyleSheet(
            """
            QTableWidget {
                background-color: #16213e;
                border: 1px solid #2a2a5e;
                border-radius: 8px;
                gridline-color: #2a2a5e;
                color: #e0e0e0;
            }
            QHeaderView::section {
                background-color: #0a0a1a;
                color: #a0a0b0;
                padding: 6px;
                border: none;
                border-bottom: 2px solid #ff9100;
                font-weight: bold;
            }
            """
        )
        layout.addWidget(self.issues_table)
        layout.addStretch()

    def update_data(self, data: dict):
        """Populate detail view with site data."""
        domain = data.get("domain", "")
        self.header_label.setText(f"Site Details: {domain}")

        status = data.get("status", "unknown")
        status_text = {"up": "Online", "down": "OFFLINE", "warning": "Warning"}.get(status, status)
        status_color = {"up": "#00e676", "down": "#ff6b6b", "warning": "#ff9100"}.get(status, "#e0e0e0")

        self._info_labels["status_val"].setText(status_text)
        self._info_labels["status_val"].setStyleSheet(
            f"color: {status_color}; font-size: 13px; font-weight: bold; padding: 4px;"
        )
        self._info_labels["domain_val"].setText(domain)
        self._info_labels["ip_val"].setText(data.get("ip", "-"))
        self._info_labels["response_val"].setText(f'{data.get("response_ms", "-")} ms')
        self._info_labels["ssl_val"].setText(data.get("ssl_status", "-"))
        self._info_labels["ssl_exp_val"].setText(data.get("ssl_expires", "-"))
        self._info_labels["last_check_val"].setText(data.get("last_check", "-"))
        self._info_labels["uptime_val"].setText(f'{data.get("uptime_30d", "-")}%')

        issues = data.get("issues", [])
        self.issues_table.setRowCount(len(issues))
        for i, issue in enumerate(issues):
            sev = issue.get("severity", "info")
            sev_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}.get(sev, "⚪")
            self.issues_table.setItem(i, 0, QTableWidgetItem(sev_icon))
            self.issues_table.setItem(i, 1, QTableWidgetItem(issue.get("type", "")))
            self.issues_table.setItem(i, 2, QTableWidgetItem(issue.get("description", "")))
            self.issues_table.setItem(i, 3, QTableWidgetItem(issue.get("detected_at", "")))


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """Main application window with dark theme, menus, toolbar, tabs, tray."""

    def __init__(self, setup_data: dict | None = None):
        super().__init__()
        self.setup_data = setup_data or {}
        self.license_manager = LicenseManager()
        self.api_client = APIClient()

        # Window properties
        self.setWindowTitle("SiteGuard Monitor Pro")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        # Apply dark theme
        self._apply_dark_theme()

        # Build UI components
        self._create_menu_bar()
        self._create_toolbar()
        self._create_central_widget()
        self._create_status_bar()
        self._create_tray_icon()

        # Data refresh timer (30 seconds)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_data)
        self.refresh_timer.start(30_000)

        # License check timer (24 hours)
        self.license_timer = QTimer(self)
        self.license_timer.timeout.connect(self._check_license)
        self.license_timer.start(86_400_000)

        # Initial data load after 1 second
        QTimer.singleShot(1000, self._initial_load)

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
        refresh_btn.clicked.connect(self._refresh_data)
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

        # Dashboard tab
        self.dashboard = DashboardWidget(self)
        self.dashboard.site_selected.connect(self._on_site_selected)
        self.tabs.addTab(self.dashboard, "Dashboard")

        # Site Details tab
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
        self.connection_label = QLabel("Connected")
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

        # Context menu
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
    # Event handlers
    # ==================================================================
    def _initial_load(self):
        self._refresh_data()
        self._update_license_status()

    def _refresh_data(self):
        try:
            dashboard_data = self.api_client.get_dashboard()
            if dashboard_data:
                self.dashboard.update_data(dashboard_data)
                self.last_update_label.setText(
                    f"Updated: {datetime.now().strftime('%H:%M:%S')}"
                )
                self.connection_label.setText("Connected")
                self.connection_label.setStyleSheet("color: #00e676; padding-right: 10px;")
                total = dashboard_data.get("total_sites", 0)
                self.statusBar().showMessage(f"Data refreshed - {total} sites monitored")
            else:
                self.connection_label.setText("No data")
                self.connection_label.setStyleSheet("color: #ff6b6b; padding-right: 10px;")
        except Exception as e:
            self.connection_label.setText("Connection error")
            self.connection_label.setStyleSheet("color: #ff6b6b; padding-right: 10px;")
            self.statusBar().showMessage(f"Error: {e}")

    def _on_site_selected(self, domain: str):
        try:
            site_data = self.api_client.get_site_status(domain)
            if site_data:
                self.site_detail.update_data(site_data)
                self.tabs.setCurrentIndex(1)
        except Exception as e:
            self.statusBar().showMessage(f"Error loading site data: {e}")

    def _show_add_site(self):
        from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle("Add Site")
        dialog.setMinimumWidth(400)
        dialog.setStyleSheet(
            """
            QDialog { background-color: #1a1a2e; }
            QLabel { color: #e0e0e0; }
            QLineEdit {
                background-color: #16213e; border: 1px solid #2a2a5e;
                border-radius: 6px; color: #e0e0e0; padding: 8px;
            }
            """
        )
        form = QFormLayout(dialog)
        domain_input = QLineEdit()
        domain_input.setPlaceholderText("example.com")
        form.addRow("Domain:", domain_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec():
            domain = domain_input.text().strip()
            if domain:
                try:
                    result = self.api_client.add_site(domain)
                    if result:
                        QMessageBox.information(self, "Success", f"Site {domain} added!")
                        self._refresh_data()
                except Exception as e:
                    QMessageBox.warning(self, "Error", str(e))

    def _check_all_now(self):
        try:
            self.api_client.check_all_now()
            self.statusBar().showMessage("Checking all sites...")
            QTimer.singleShot(30_000, self._refresh_data)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _toggle_pause(self, paused: bool):
        if paused:
            self.refresh_timer.stop()
            self.statusBar().showMessage("Monitoring paused")
            self.pause_action.setText("Resume Monitoring")
        else:
            self.refresh_timer.start(30_000)
            self.statusBar().showMessage("Monitoring resumed")
            self.pause_action.setText("Pause Monitoring")
            self._refresh_data()

    def _show_settings(self):
        QMessageBox.information(self, "Settings", "Settings dialog - coming soon.")

    def _show_notification_settings(self):
        QMessageBox.information(self, "Notifications", "Notification settings - coming soon.")

    def _show_license_info(self):
        info = self.license_manager.get_license_info()
        if info:
            plan = info.get("plan", "unknown").upper()
            days = info.get("days_remaining", 0)
            max_sites = info.get("max_sites", 0)
            sites_used = info.get("sites_used", 0)
            key = info.get("license_key", "")
            masked = key[:8] + "****-****-" + key[-5:] if len(key) > 15 else key
            QMessageBox.information(
                self,
                "License",
                f"Key: {masked}\n"
                f"Plan: {plan}\n"
                f"Remaining: {days} days\n"
                f"Sites: {sites_used} / {max_sites}",
            )
        else:
            QMessageBox.warning(self, "License", "Could not retrieve license information.")

    def _update_license_status(self):
        info = self.license_manager.get_license_info()
        if info:
            plan = info.get("plan", "?").upper()
            days = info.get("days_remaining", 0)
            if days <= 7:
                color = "#ff6b6b"
                text = f"License: {plan} - {days}d remaining"
            elif days <= 30:
                color = "#ff9100"
                text = f"License: {plan} - {days}d"
            else:
                color = "#00e676"
                text = f"License: {plan} - {days}d"
            self.license_status_label.setText(text)
            self.license_status_label.setStyleSheet(
                f"color: {color}; padding: 5px 10px; font-size: 12px;"
            )
        else:
            self.license_status_label.setText("License: Error")
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
            f"siteguard_report_{datetime.now().strftime('%Y%m%d')}.html",
            "HTML (*.html);;JSON (*.json);;PDF (*.pdf)",
        )
        if filepath:
            try:
                self.api_client.export_report(filepath)
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
            "<p>Version 1.0.0</p>"
            "<p>24/7 Site Monitoring System</p>"
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
        """Actually quit (not just minimize to tray)."""
        if self.tray:
            self.tray.hide()
        QApplication.quit()

    # -- Override close to minimize to tray --
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
            event.accept()
