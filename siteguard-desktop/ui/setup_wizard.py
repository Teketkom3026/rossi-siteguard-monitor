"""
SiteGuard Monitor Pro - Setup Wizard

First-run setup wizard with pages:
  1. Welcome
  2. License
  3. Notification
  4. Sites
  5. MonitoringSettings
  6. Completion

Dark theme (#1a1a2e).
"""
from __future__ import annotations

import re
from typing import Any

from PyQt6.QtWidgets import (
    QWizard,
    QWizardPage,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QCheckBox,
    QSpinBox,
    QComboBox,
    QGroupBox,
    QFormLayout,
    QMessageBox,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QFrame,
    QGridLayout,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor

from core.api_client import APIClient
from core.license_manager import LicenseManager

# License key pattern
LICENSE_KEY_RE = re.compile(
    r"^SG-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}$"
)

# ---------------------------------------------------------------------------
# Dark-theme stylesheet shared across wizard pages
# ---------------------------------------------------------------------------
WIZARD_STYLESHEET = """
    QWizard {
        background-color: #1a1a2e;
        color: #e0e0e0;
    }
    QWizardPage {
        background-color: #1a1a2e;
        color: #e0e0e0;
    }
    QLabel {
        color: #e0e0e0;
        font-size: 13px;
    }
    QLineEdit, QTextEdit, QSpinBox, QComboBox {
        background-color: #16213e;
        border: 1px solid #2a2a5e;
        border-radius: 6px;
        color: #e0e0e0;
        padding: 8px;
        font-size: 13px;
    }
    QLineEdit:focus, QTextEdit:focus {
        border: 1px solid #4a90d9;
    }
    QPushButton {
        background-color: #4a90d9;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 10px 20px;
        font-size: 13px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #5aa0e9;
    }
    QPushButton:pressed {
        background-color: #3a80c9;
    }
    QPushButton:disabled {
        background-color: #555;
        color: #999;
    }
    QCheckBox {
        color: #e0e0e0;
        font-size: 13px;
        spacing: 8px;
    }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border-radius: 4px;
        border: 2px solid #4a90d9;
        background: #16213e;
    }
    QCheckBox::indicator:checked {
        background: #4a90d9;
    }
    QGroupBox {
        color: #4a90d9;
        font-size: 14px;
        font-weight: bold;
        border: 1px solid #2a2a5e;
        border-radius: 8px;
        margin-top: 10px;
        padding-top: 15px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 15px;
        padding: 0 5px;
    }
    QListWidget {
        background-color: #16213e;
        border: 1px solid #2a2a5e;
        border-radius: 6px;
        color: #e0e0e0;
        font-size: 13px;
    }
    QListWidget::item {
        padding: 8px;
        border-bottom: 1px solid #2a2a5e;
    }
    QListWidget::item:selected {
        background-color: #4a90d9;
    }
"""


# =========================================================================
# Wizard
# =========================================================================
class SetupWizard(QWizard):
    """First-run setup wizard."""

    setup_completed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SiteGuard Monitor - Setup")
        self.setMinimumSize(700, 550)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        # Accumulated setup data
        self.setup_data: dict[str, Any] = {
            "license_key": None,
            "license_info": None,
            "notifications": {},
            "sites": [],
            "monitoring_settings": {},
        }

        # Pages
        self.addPage(WelcomePage(self))
        self.addPage(LicensePage(self))
        self.addPage(NotificationPage(self))
        self.addPage(SitesPage(self))
        self.addPage(MonitoringSettingsPage(self))
        self.addPage(CompletionPage(self))

        self.setStyleSheet(WIZARD_STYLESHEET)

    def accept(self):
        """Emit the setup_completed signal and close."""
        self.setup_completed.emit(self.setup_data)
        super().accept()


# =========================================================================
# Page 1 - Welcome
# =========================================================================
class WelcomePage(QWizardPage):
    """Welcome / introduction page."""

    def __init__(self, wizard: SetupWizard):
        super().__init__()
        self.wizard_ref = wizard
        self.setTitle("Welcome!")
        self.setSubTitle("This wizard will help you set up site monitoring")

        layout = QVBoxLayout()

        # Logo placeholder
        logo_label = QLabel("SG")
        logo_label.setFont(QFont("Segoe UI", 48, QFont.Weight.Bold))
        logo_label.setStyleSheet("color: #4a90d9;")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo_label)

        # Title
        title = QLabel("SiteGuard Monitor Pro")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #4a90d9;")
        layout.addWidget(title)

        # Feature list
        desc = QLabel(
            "24/7 Site Monitoring System\n\n"
            "  - Site & page availability\n"
            "  - SSL certificates\n"
            "  - Button & form click testing\n"
            "  - Security & malware scanning\n"
            "  - Telegram, Email, SMS notifications\n"
            "  - Visual Sitemap dashboard\n"
        )
        desc.setFont(QFont("Segoe UI", 13))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addStretch()
        self.setLayout(layout)


# =========================================================================
# Page 2 - License
# =========================================================================
class LicensePage(QWizardPage):
    """License key entry and activation page."""

    def __init__(self, wizard: SetupWizard):
        super().__init__()
        self.wizard_ref = wizard
        self.license_valid = False

        self.setTitle("License Key")
        self.setSubTitle("Enter your activation key or start a free trial")

        layout = QVBoxLayout()

        # Key input group
        key_group = QGroupBox("Activation")
        key_layout = QFormLayout()

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("SG-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX")
        self.key_input.setFont(QFont("Courier New", 14))
        self.key_input.setMaxLength(35)
        self.key_input.textChanged.connect(self._format_key)
        key_layout.addRow("Key:", self.key_input)

        self.activate_btn = QPushButton("Activate Key")
        self.activate_btn.clicked.connect(self._activate_key)
        key_layout.addRow("", self.activate_btn)

        key_group.setLayout(key_layout)
        layout.addWidget(key_group)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # License info (shown after successful activation)
        self.license_info_group = QGroupBox("License Information")
        self.license_info_group.setVisible(False)
        info_layout = QFormLayout()

        self.plan_label = QLabel("")
        self.max_sites_label = QLabel("")
        self.expires_label = QLabel("")
        self.features_label = QLabel("")
        self.features_label.setWordWrap(True)

        info_layout.addRow("Plan:", self.plan_label)
        info_layout.addRow("Max Sites:", self.max_sites_label)
        info_layout.addRow("Valid Until:", self.expires_label)
        info_layout.addRow("Features:", self.features_label)

        self.license_info_group.setLayout(info_layout)
        layout.addWidget(self.license_info_group)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #2a2a5e;")
        layout.addWidget(separator)

        # Trial button
        trial_layout = QHBoxLayout()
        trial_label = QLabel("No key?")
        self.trial_btn = QPushButton("Start Free Trial (14 days)")
        self.trial_btn.setStyleSheet(
            """
            QPushButton { background-color: #2a6e3f; }
            QPushButton:hover { background-color: #3a8e4f; }
            """
        )
        self.trial_btn.clicked.connect(self._start_trial)
        trial_layout.addWidget(trial_label)
        trial_layout.addWidget(self.trial_btn)
        layout.addLayout(trial_layout)

        # Purchase link
        buy_label = QLabel(
            '<a href="https://siteguard.app/pricing" '
            'style="color: #4a90d9;">Purchase a license</a>'
        )
        buy_label.setOpenExternalLinks(True)
        buy_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(buy_label)

        layout.addStretch()
        self.setLayout(layout)

    def _format_key(self, text: str):
        """Auto-format the key as user types."""
        # We just let the user type/paste freely; validation happens on activate.
        pass

    def _activate_key(self):
        key = self.key_input.text().strip().upper()
        if not key:
            self.status_label.setText(
                '<span style="color: #ff6b6b;">Please enter a key</span>'
            )
            return

        if not LICENSE_KEY_RE.match(key):
            self.status_label.setText(
                '<span style="color: #ff6b6b;">Invalid key format (SG-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX)</span>'
            )
            return

        self.activate_btn.setEnabled(False)
        self.status_label.setText(
            '<span style="color: #ff9100;">Activating...</span>'
        )

        try:
            client = APIClient()
            result = client.activate_license(key)
            if result and result.get("success"):
                info = result.get("license_info", {})
                self._show_info(info)
                self.wizard_ref.setup_data["license_key"] = key
                self.wizard_ref.setup_data["license_info"] = info
                self.license_valid = True
                self.status_label.setText(
                    '<span style="color: #00e676;">License activated!</span>'
                )
                LicenseManager().store_license_key(key, info)
            else:
                error = (result or {}).get("error", "Unknown error")
                self.status_label.setText(
                    f'<span style="color: #ff6b6b;">Activation failed: {error}</span>'
                )
                self.activate_btn.setEnabled(True)
        except Exception as e:
            self.status_label.setText(
                f'<span style="color: #ff6b6b;">Error: {e}</span>'
            )
            self.activate_btn.setEnabled(True)

    def _start_trial(self):
        try:
            client = APIClient()
            result = client.activate_license("TRIAL")
            if result and result.get("success"):
                info = result.get("license_info", {})
                self._show_info(info)
                self.wizard_ref.setup_data["license_key"] = "TRIAL"
                self.wizard_ref.setup_data["license_info"] = info
                self.license_valid = True
                self.status_label.setText(
                    '<span style="color: #00e676;">14-day trial activated!</span>'
                )
                self.trial_btn.setEnabled(False)
                LicenseManager().store_license_key("TRIAL", info)
            else:
                error = (result or {}).get("error", "Server unavailable")
                self.status_label.setText(
                    f'<span style="color: #ff6b6b;">Could not start trial: {error}</span>'
                )
        except Exception as e:
            self.status_label.setText(
                f'<span style="color: #ff6b6b;">Error: {e}</span>'
            )

    def _show_info(self, info: dict):
        self.plan_label.setText(info.get("plan", "-").upper())
        self.max_sites_label.setText(str(info.get("max_sites", "-")))
        self.expires_label.setText(info.get("expires_at", "-"))
        features = info.get("features", {})
        if isinstance(features, dict):
            feat_list = [k for k, v in features.items() if v]
            self.features_label.setText(", ".join(feat_list) if feat_list else "Basic")
        else:
            self.features_label.setText(str(features))
        self.license_info_group.setVisible(True)

    def validatePage(self) -> bool:
        if not self.license_valid:
            QMessageBox.warning(
                self,
                "License Required",
                "Please activate a license key or start a trial before continuing.",
            )
            return False
        return True


# =========================================================================
# Page 3 - Notification Settings
# =========================================================================
class NotificationPage(QWizardPage):
    """Configure notification channels: Telegram, Email, SMS."""

    def __init__(self, wizard: SetupWizard):
        super().__init__()
        self.wizard_ref = wizard
        self.setTitle("Notifications")
        self.setSubTitle("Choose how you want to receive alerts")

        layout = QVBoxLayout()

        # -- Telegram --
        tg_group = QGroupBox("Telegram")
        tg_layout = QFormLayout()
        self.tg_enabled = QCheckBox("Enable Telegram notifications")
        self.tg_enabled.setChecked(True)
        tg_layout.addRow(self.tg_enabled)
        self.tg_bot_token = QLineEdit()
        self.tg_bot_token.setPlaceholderText("Bot token from @BotFather")
        tg_layout.addRow("Bot Token:", self.tg_bot_token)
        self.tg_chat_id = QLineEdit()
        self.tg_chat_id.setPlaceholderText("Chat ID or @channel")
        tg_layout.addRow("Chat ID:", self.tg_chat_id)
        self.tg_test_btn = QPushButton("Send Test Message")
        self.tg_test_btn.clicked.connect(self._test_telegram)
        tg_layout.addRow("", self.tg_test_btn)
        tg_group.setLayout(tg_layout)
        layout.addWidget(tg_group)

        # -- Email --
        email_group = QGroupBox("Email")
        email_layout = QFormLayout()
        self.email_enabled = QCheckBox("Enable Email notifications")
        email_layout.addRow(self.email_enabled)
        self.email_address = QLineEdit()
        self.email_address.setPlaceholderText("your@email.com")
        email_layout.addRow("Email:", self.email_address)
        email_group.setLayout(email_layout)
        layout.addWidget(email_group)

        # -- SMS --
        sms_group = QGroupBox("SMS")
        sms_layout = QFormLayout()
        self.sms_enabled = QCheckBox("Enable SMS notifications (critical alerts only)")
        sms_layout.addRow(self.sms_enabled)
        self.sms_phone = QLineEdit()
        self.sms_phone.setPlaceholderText("+1234567890")
        sms_layout.addRow("Phone:", self.sms_phone)
        sms_group.setLayout(sms_layout)
        layout.addWidget(sms_group)

        layout.addStretch()
        self.setLayout(layout)

    def _test_telegram(self):
        token = self.tg_bot_token.text().strip()
        chat_id = self.tg_chat_id.text().strip()
        if not token or not chat_id:
            QMessageBox.warning(self, "Error", "Please enter both Bot Token and Chat ID.")
            return
        QMessageBox.information(
            self,
            "Test",
            "Test message would be sent to Telegram.\n"
            "(Server connectivity required for actual delivery.)",
        )

    def validatePage(self) -> bool:
        notifications: dict[str, Any] = {}

        if self.tg_enabled.isChecked():
            notifications["telegram"] = {
                "enabled": True,
                "bot_token": self.tg_bot_token.text().strip(),
                "chat_id": self.tg_chat_id.text().strip(),
            }
        else:
            notifications["telegram"] = {"enabled": False}

        if self.email_enabled.isChecked():
            notifications["email"] = {
                "enabled": True,
                "address": self.email_address.text().strip(),
            }
        else:
            notifications["email"] = {"enabled": False}

        if self.sms_enabled.isChecked():
            notifications["sms"] = {
                "enabled": True,
                "phone": self.sms_phone.text().strip(),
            }
        else:
            notifications["sms"] = {"enabled": False}

        self.wizard_ref.setup_data["notifications"] = notifications
        return True


# =========================================================================
# Page 4 - Sites
# =========================================================================
class SitesPage(QWizardPage):
    """Add sites to monitor."""

    def __init__(self, wizard: SetupWizard):
        super().__init__()
        self.wizard_ref = wizard
        self.setTitle("Add Sites")
        self.setSubTitle("Enter the domains you want to monitor")

        layout = QVBoxLayout()

        # Single site input
        single_group = QGroupBox("Add Single Site")
        single_layout = QHBoxLayout()
        self.domain_input = QLineEdit()
        self.domain_input.setPlaceholderText("example.com")
        self.domain_input.returnPressed.connect(self._add_single)
        single_layout.addWidget(self.domain_input)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_single)
        single_layout.addWidget(add_btn)
        single_group.setLayout(single_layout)
        layout.addWidget(single_group)

        # Batch input
        batch_group = QGroupBox("Bulk Add (one domain per line)")
        batch_layout = QVBoxLayout()
        self.batch_input = QTextEdit()
        self.batch_input.setPlaceholderText(
            "example.com\nshop.example.com\nblog.example.com"
        )
        self.batch_input.setMaximumHeight(100)
        batch_layout.addWidget(self.batch_input)
        batch_btn = QPushButton("Add All")
        batch_btn.clicked.connect(self._add_batch)
        batch_layout.addWidget(batch_btn)
        batch_group.setLayout(batch_layout)
        layout.addWidget(batch_group)

        # Sites list
        list_group = QGroupBox("Sites to Monitor")
        list_layout = QVBoxLayout()

        self.count_label = QLabel("Added: 0 / 3")
        self.count_label.setStyleSheet("color: #a0a0b0; font-size: 12px;")
        list_layout.addWidget(self.count_label)

        self.sites_list = QListWidget()
        list_layout.addWidget(self.sites_list)

        btn_row = QHBoxLayout()
        remove_btn = QPushButton("Remove Selected")
        remove_btn.setStyleSheet(
            "QPushButton { background-color: #c0392b; }"
            "QPushButton:hover { background-color: #e74c3c; }"
        )
        remove_btn.clicked.connect(self._remove_site)
        btn_row.addWidget(remove_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.setStyleSheet(
            "QPushButton { background-color: #7f8c8d; }"
            "QPushButton:hover { background-color: #95a5a6; }"
        )
        clear_btn.clicked.connect(self._clear_sites)
        btn_row.addWidget(clear_btn)

        list_layout.addLayout(btn_row)
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        self.setLayout(layout)

    # ---- helpers ----
    def _add_single(self):
        domain = self.domain_input.text().strip().lower()
        domain = domain.replace("http://", "").replace("https://", "").rstrip("/")
        if not domain:
            return

        license_info = self.wizard_ref.setup_data.get("license_info", {})
        max_sites = license_info.get("max_sites", 3)

        if self.sites_list.count() >= max_sites:
            QMessageBox.warning(
                self, "Limit Reached", f"Site limit ({max_sites}) reached. Upgrade your plan."
            )
            return

        # Duplicate check
        for i in range(self.sites_list.count()):
            if self.sites_list.item(i).data(Qt.ItemDataRole.UserRole) == domain:
                QMessageBox.warning(self, "Duplicate", f"Site {domain} is already added.")
                return

        if "." not in domain:
            QMessageBox.warning(self, "Error", "Enter a valid domain (e.g. example.com)")
            return

        item = QListWidgetItem(domain)
        item.setData(Qt.ItemDataRole.UserRole, domain)
        self.sites_list.addItem(item)
        self.domain_input.clear()
        self._update_count()

    def _add_batch(self):
        text = self.batch_input.toPlainText().strip()
        if not text:
            return

        license_info = self.wizard_ref.setup_data.get("license_info", {})
        max_sites = license_info.get("max_sites", 3)

        lines = text.split("\n")
        added = 0
        skipped = 0

        for line in lines:
            domain = line.strip().lower()
            domain = domain.replace("http://", "").replace("https://", "").rstrip("/")
            if not domain or "." not in domain:
                skipped += 1
                continue

            if self.sites_list.count() >= max_sites:
                QMessageBox.warning(
                    self,
                    "Limit Reached",
                    f"Limit ({max_sites}) reached. Added {added}, rest skipped.",
                )
                break

            # Duplicate check
            is_dup = False
            for i in range(self.sites_list.count()):
                if self.sites_list.item(i).data(Qt.ItemDataRole.UserRole) == domain:
                    is_dup = True
                    skipped += 1
                    break
            if not is_dup:
                item = QListWidgetItem(domain)
                item.setData(Qt.ItemDataRole.UserRole, domain)
                self.sites_list.addItem(item)
                added += 1

        self.batch_input.clear()
        self._update_count()
        QMessageBox.information(
            self,
            "Result",
            f"Added: {added}\nSkipped: {skipped}",
        )

    def _remove_site(self):
        current = self.sites_list.currentRow()
        if current >= 0:
            self.sites_list.takeItem(current)
            self._update_count()

    def _clear_sites(self):
        reply = QMessageBox.question(
            self,
            "Confirm",
            "Remove all sites from the list?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.sites_list.clear()
            self._update_count()

    def _update_count(self):
        count = self.sites_list.count()
        license_info = self.wizard_ref.setup_data.get("license_info", {})
        max_sites = license_info.get("max_sites", 3)
        self.count_label.setText(f"Added: {count} / {max_sites}")

    def validatePage(self) -> bool:
        sites = []
        for i in range(self.sites_list.count()):
            domain = self.sites_list.item(i).data(Qt.ItemDataRole.UserRole)
            sites.append(domain)

        if not sites:
            QMessageBox.warning(self, "Error", "Please add at least one site.")
            return False

        self.wizard_ref.setup_data["sites"] = sites
        return True


# =========================================================================
# Page 5 - Monitoring Settings
# =========================================================================
class MonitoringSettingsPage(QWizardPage):
    """Configure monitoring parameters."""

    def __init__(self, wizard: SetupWizard):
        super().__init__()
        self.wizard_ref = wizard
        self.setTitle("Monitoring Settings")
        self.setSubTitle("Configure what and how often to check")

        layout = QVBoxLayout()

        # Check interval
        interval_group = QGroupBox("Check Frequency")
        interval_layout = QFormLayout()
        self.check_interval = QComboBox()
        self.check_interval.addItems(
            [
                "Every 1 minute",
                "Every 5 minutes (recommended)",
                "Every 10 minutes",
                "Every 15 minutes",
                "Every 30 minutes",
                "Every hour",
            ]
        )
        self.check_interval.setCurrentIndex(1)
        interval_layout.addRow("Availability check:", self.check_interval)
        interval_group.setLayout(interval_layout)
        layout.addWidget(interval_group)

        # What to check
        checks_group = QGroupBox("What to Check")
        checks_layout = QVBoxLayout()

        self.check_availability = QCheckBox("Site availability (HTTP/DNS/Ping)")
        self.check_availability.setChecked(True)
        self.check_availability.setEnabled(False)  # Always on
        checks_layout.addWidget(self.check_availability)

        self.check_ssl = QCheckBox("SSL certificates")
        self.check_ssl.setChecked(True)
        checks_layout.addWidget(self.check_ssl)

        self.check_pages = QCheckBox("Pages & sections (via Sitemap)")
        self.check_pages.setChecked(True)
        checks_layout.addWidget(self.check_pages)

        self.check_ui = QCheckBox(
            "Buttons & forms (buy, call, contact, cart, etc.)"
        )
        self.check_ui.setChecked(True)
        checks_layout.addWidget(self.check_ui)

        self.check_security = QCheckBox(
            "Security (headers, vulnerabilities, open resources)"
        )
        self.check_security.setChecked(True)
        checks_layout.addWidget(self.check_security)

        self.check_malware = QCheckBox(
            "Malware & viruses (scripts, iframes, suspicious files)"
        )
        self.check_malware.setChecked(True)
        checks_layout.addWidget(self.check_malware)

        self.check_attacks = QCheckBox(
            "External attacks & threats (WAF, suspicious activity)"
        )
        self.check_attacks.setChecked(True)
        checks_layout.addWidget(self.check_attacks)

        checks_group.setLayout(checks_layout)
        layout.addWidget(checks_group)

        # Alert levels
        alert_group = QGroupBox("Alert Levels")
        alert_layout = QVBoxLayout()

        self.alert_critical = QCheckBox(
            "CRITICAL - SMS + Telegram + Email (site down, virus, SSL expired)"
        )
        self.alert_critical.setChecked(True)
        self.alert_critical.setEnabled(False)  # Always on
        alert_layout.addWidget(self.alert_critical)

        self.alert_high = QCheckBox(
            "HIGH - Telegram + Email (buttons broken, SSL expiring soon)"
        )
        self.alert_high.setChecked(True)
        alert_layout.addWidget(self.alert_high)

        self.alert_medium = QCheckBox(
            "MEDIUM - Telegram (slow response, missing headers)"
        )
        self.alert_medium.setChecked(True)
        alert_layout.addWidget(self.alert_medium)

        self.alert_low = QCheckBox("LOW - Dashboard only (informational)")
        self.alert_low.setChecked(False)
        alert_layout.addWidget(self.alert_low)

        alert_group.setLayout(alert_layout)
        layout.addWidget(alert_group)

        layout.addStretch()
        self.setLayout(layout)

    def initializePage(self):
        """Disable features unavailable in the current plan."""
        license_info = self.wizard_ref.setup_data.get("license_info", {})
        features = license_info.get("features", {})

        if not features.get("ui_tests", True):
            self.check_ui.setEnabled(False)
            self.check_ui.setChecked(False)
            self.check_ui.setText(self.check_ui.text() + " [not available in your plan]")

        if not features.get("security_scan", True):
            self.check_security.setEnabled(False)
            self.check_security.setChecked(False)
            self.check_security.setText(self.check_security.text() + " [not available]")
            self.check_attacks.setEnabled(False)
            self.check_attacks.setChecked(False)

        if not features.get("malware_scan", True):
            self.check_malware.setEnabled(False)
            self.check_malware.setChecked(False)
            self.check_malware.setText(self.check_malware.text() + " [not available]")

    def validatePage(self) -> bool:
        interval_map = {0: 60, 1: 300, 2: 600, 3: 900, 4: 1800, 5: 3600}

        self.wizard_ref.setup_data["monitoring_settings"] = {
            "check_interval": interval_map.get(
                self.check_interval.currentIndex(), 300
            ),
            "checks": {
                "availability": True,
                "ssl": self.check_ssl.isChecked(),
                "pages": self.check_pages.isChecked(),
                "ui": self.check_ui.isChecked(),
                "security": self.check_security.isChecked(),
                "malware": self.check_malware.isChecked(),
                "attacks": self.check_attacks.isChecked(),
            },
            "alert_levels": {
                "critical": True,
                "high": self.alert_high.isChecked(),
                "medium": self.alert_medium.isChecked(),
                "low": self.alert_low.isChecked(),
            },
        }
        return True


# =========================================================================
# Page 6 - Completion
# =========================================================================
class CompletionPage(QWizardPage):
    """Final summary page."""

    def __init__(self, wizard: SetupWizard):
        super().__init__()
        self.wizard_ref = wizard
        self.setTitle("All Set!")
        self.setSubTitle("Review your settings and start monitoring")

        layout = QVBoxLayout()

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("font-size: 14px; line-height: 1.6;")
        layout.addWidget(self.summary_label)

        # Progress bar for initial check
        self.progress_group = QGroupBox("Initial Check")
        self.progress_group.setVisible(False)
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                background-color: #16213e;
                border: 1px solid #2a2a5e;
                border-radius: 6px;
                text-align: center;
                color: #e0e0e0;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #00e676;
                border-radius: 5px;
            }
            """
        )
        progress_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("Preparing...")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.progress_label)

        self.progress_group.setLayout(progress_layout)
        layout.addWidget(self.progress_group)

        layout.addStretch()
        self.setLayout(layout)

    def initializePage(self):
        """Build the summary text when the page is shown."""
        data = self.wizard_ref.setup_data
        license_info = data.get("license_info", {})
        plan = license_info.get("plan", "trial").upper()
        max_sites = license_info.get("max_sites", 3)
        days = license_info.get("days_remaining", 0)

        sites = data.get("sites", [])
        sites_text = "\n".join(f"    - {s}" for s in sites)

        notif = data.get("notifications", {})
        channels = []
        if notif.get("telegram", {}).get("enabled"):
            channels.append("Telegram")
        if notif.get("email", {}).get("enabled"):
            channels.append("Email")
        if notif.get("sms", {}).get("enabled"):
            channels.append("SMS")
        notif_text = ", ".join(channels) if channels else "None configured"

        monitoring = data.get("monitoring_settings", {})
        interval = monitoring.get("check_interval", 300)
        checks = monitoring.get("checks", {})
        check_names = {
            "availability": "Availability",
            "ssl": "SSL",
            "pages": "Pages",
            "ui": "UI Elements",
            "security": "Security",
            "malware": "Malware",
            "attacks": "Attacks",
        }
        checks_lines = []
        for key, name in check_names.items():
            status = "ON" if checks.get(key, False) else "OFF"
            checks_lines.append(f"&nbsp;&nbsp;&nbsp;&nbsp;{name}: {status}")

        sites_html = "<br>".join(f"&nbsp;&nbsp;&nbsp;&nbsp;{s}" for s in sites)
        checks_html = "<br>".join(checks_lines)
        interval_min = interval // 60

        summary = (
            f"<h3>Setup Summary</h3>"
            f"<b>License:</b> {plan} ({days} days remaining, up to {max_sites} sites)<br><br>"
            f"<b>Sites ({len(sites)}):</b><br>"
            f"{sites_html}<br><br>"
            f"<b>Notifications:</b> {notif_text}<br><br>"
            f"<b>Check Interval:</b> every {interval_min} min<br><br>"
            f"<b>Checks:</b><br>"
            f"{checks_html}"
            f"<hr>"
            '<p style="color: #00e676; font-size: 16px;">'
            "Click <b>Finish</b> to start monitoring!</p>"
        )
        self.summary_label.setText(summary)
