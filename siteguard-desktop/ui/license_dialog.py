"""
SiteGuard Monitor Pro - License Activation Dialog

License activation dialog with key input field (format SG-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX),
plan info display, device management. Dark themed.
"""
import re

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QFrame,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDialogButtonBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from core.api_client import APIClient
from core.license_manager import LicenseManager

# License key pattern: SG-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
LICENSE_KEY_PATTERN = re.compile(
    r"^SG-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}$"
)


class LicenseDialog(QDialog):
    """Dialog for entering and activating a license key."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = APIClient()
        self.license_manager = LicenseManager()
        self._activated_key: str | None = None

        self.setWindowTitle("SiteGuard Monitor - License Activation")
        self.setMinimumSize(600, 520)
        self.setModal(True)

        self._apply_style()
        self._build_ui()

    # ------------------------------------------------------------------
    # Style
    # ------------------------------------------------------------------
    def _apply_style(self):
        self.setStyleSheet(
            """
            QDialog {
                background-color: #1a1a2e;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #16213e;
                border: 1px solid #2a2a5e;
                border-radius: 6px;
                color: #e0e0e0;
                padding: 10px;
                font-size: 14px;
                font-family: 'Courier New', monospace;
            }
            QLineEdit:focus {
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
            QTableWidget {
                background-color: #16213e;
                border: 1px solid #2a2a5e;
                border-radius: 6px;
                color: #e0e0e0;
                gridline-color: #2a2a5e;
            }
            QHeaderView::section {
                background-color: #0a0a1a;
                color: #a0a0b0;
                padding: 6px;
                border: none;
                border-bottom: 2px solid #4a90d9;
                font-weight: bold;
            }
            """
        )

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Title
        title = QLabel("License Activation")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #4a90d9;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # ---- Key input group ----
        key_group = QGroupBox("Enter License Key")
        key_layout = QVBoxLayout()

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("SG-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX")
        self.key_input.setMaxLength(35)
        self.key_input.textChanged.connect(self._on_key_text_changed)
        key_layout.addWidget(self.key_input)

        self.key_format_label = QLabel("Format: SG-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX")
        self.key_format_label.setStyleSheet("color: #888; font-size: 11px;")
        key_layout.addWidget(self.key_format_label)

        btn_row = QHBoxLayout()
        self.activate_btn = QPushButton("Activate Key")
        self.activate_btn.setEnabled(False)
        self.activate_btn.clicked.connect(self._activate_key)
        btn_row.addWidget(self.activate_btn)

        self.trial_btn = QPushButton("Start 14-Day Trial")
        self.trial_btn.setStyleSheet(
            """
            QPushButton { background-color: #2a6e3f; }
            QPushButton:hover { background-color: #3a8e4f; }
            """
        )
        self.trial_btn.clicked.connect(self._start_trial)
        btn_row.addWidget(self.trial_btn)

        key_layout.addLayout(btn_row)
        key_group.setLayout(key_layout)
        layout.addWidget(key_group)

        # ---- Status ----
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # ---- License info group (hidden until activation) ----
        self.info_group = QGroupBox("License Information")
        self.info_group.setVisible(False)
        info_layout = QFormLayout()

        self.plan_label = QLabel("-")
        self.max_sites_label = QLabel("-")
        self.expires_label = QLabel("-")
        self.features_label = QLabel("-")
        self.features_label.setWordWrap(True)

        info_layout.addRow("Plan:", self.plan_label)
        info_layout.addRow("Max Sites:", self.max_sites_label)
        info_layout.addRow("Valid Until:", self.expires_label)
        info_layout.addRow("Features:", self.features_label)

        self.info_group.setLayout(info_layout)
        layout.addWidget(self.info_group)

        # ---- Device management group ----
        self.device_group = QGroupBox("Registered Devices")
        self.device_group.setVisible(False)
        dev_layout = QVBoxLayout()

        self.device_table = QTableWidget()
        self.device_table.setColumnCount(3)
        self.device_table.setHorizontalHeaderLabels(["Device Name", "Hardware ID", "Registered"])
        dh = self.device_table.horizontalHeader()
        dh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.device_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        dev_layout.addWidget(self.device_table)

        deactivate_btn = QPushButton("Deactivate This Device")
        deactivate_btn.setStyleSheet(
            """
            QPushButton { background-color: #c0392b; }
            QPushButton:hover { background-color: #e74c3c; }
            """
        )
        deactivate_btn.clicked.connect(self._deactivate_device)
        dev_layout.addWidget(deactivate_btn)

        self.device_group.setLayout(dev_layout)
        layout.addWidget(self.device_group)

        # ---- Buttons ----
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #2a2a5e;")
        layout.addWidget(separator)

        buy_label = QLabel(
            '<a href="https://siteguard.app/pricing" '
            'style="color: #4a90d9;">Purchase a license</a>'
        )
        buy_label.setOpenExternalLinks(True)
        buy_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(buy_label)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_key_text_changed(self, text: str):
        """Enable the activate button only when key looks valid."""
        cleaned = text.strip().upper()
        valid = bool(LICENSE_KEY_PATTERN.match(cleaned))
        self.activate_btn.setEnabled(valid)
        if text and not valid:
            self.key_format_label.setStyleSheet("color: #ff6b6b; font-size: 11px;")
            self.key_format_label.setText("Invalid format. Expected: SG-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX")
        else:
            self.key_format_label.setStyleSheet("color: #888; font-size: 11px;")
            self.key_format_label.setText("Format: SG-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX")

    def _activate_key(self):
        key = self.key_input.text().strip().upper()
        if not LICENSE_KEY_PATTERN.match(key):
            self.status_label.setText(
                '<span style="color: #ff6b6b;">Invalid license key format</span>'
            )
            return

        self.activate_btn.setEnabled(False)
        self.status_label.setText(
            '<span style="color: #ff9100;">Activating...</span>'
        )

        try:
            result = self.api_client.activate_license(key)
            if result and result.get("success"):
                self._activated_key = key
                self._show_license_info(result)
                self.status_label.setText(
                    '<span style="color: #00e676;">License activated successfully!</span>'
                )
                self.license_manager.store_license_key(key)
            else:
                error = result.get("error", "Unknown error") if result else "No response from server"
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
            result = self.api_client.activate_license("TRIAL")
            if result and result.get("success"):
                self._activated_key = "TRIAL"
                self._show_license_info(result)
                self.status_label.setText(
                    '<span style="color: #00e676;">14-day trial activated!</span>'
                )
                self.license_manager.store_license_key("TRIAL")
                self.trial_btn.setEnabled(False)
            else:
                error = result.get("error", "Unknown error") if result else "Server unavailable"
                self.status_label.setText(
                    f'<span style="color: #ff6b6b;">Could not start trial: {error}</span>'
                )
        except Exception as e:
            self.status_label.setText(
                f'<span style="color: #ff6b6b;">Error: {e}</span>'
            )

    def _show_license_info(self, data: dict):
        """Display license info after successful activation."""
        info = data.get("license_info", data)
        self.plan_label.setText(info.get("plan", "-").upper())
        self.max_sites_label.setText(str(info.get("max_sites", "-")))
        self.expires_label.setText(info.get("expires_at", "-"))

        features = info.get("features", {})
        if isinstance(features, dict):
            feat_list = [k for k, v in features.items() if v]
            self.features_label.setText(", ".join(feat_list) if feat_list else "Basic")
        else:
            self.features_label.setText(str(features))

        self.info_group.setVisible(True)

        # Populate devices
        devices = info.get("devices", [])
        if devices:
            self.device_table.setRowCount(len(devices))
            for i, dev in enumerate(devices):
                self.device_table.setItem(i, 0, QTableWidgetItem(dev.get("name", "-")))
                self.device_table.setItem(i, 1, QTableWidgetItem(dev.get("hardware_id", "-")))
                self.device_table.setItem(i, 2, QTableWidgetItem(dev.get("registered_at", "-")))
            self.device_group.setVisible(True)

    def _deactivate_device(self):
        reply = QMessageBox.question(
            self,
            "Deactivate Device",
            "Are you sure you want to deactivate this device?\n"
            "You will need to re-activate the license to use it again.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.api_client.deactivate_device()
                self.license_manager.clear_license()
                QMessageBox.information(self, "Done", "Device deactivated successfully.")
                self.info_group.setVisible(False)
                self.device_group.setVisible(False)
                self.status_label.setText("")
                self.activate_btn.setEnabled(True)
                self._activated_key = None
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_key(self) -> str | None:
        """Return the activated key, or None if not activated."""
        return self._activated_key
