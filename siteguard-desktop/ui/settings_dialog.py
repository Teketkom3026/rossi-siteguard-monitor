"""
SettingsDialog — Email notifications and monitoring configuration.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QCheckBox, QSpinBox, QPushButton,
    QFormLayout, QGroupBox, QMessageBox,
)
from PyQt6.QtCore import Qt

from core.notifier import EmailNotifier

# Style constants (match main window)
DARK_BG = "#0f0f23"
DARK_PANEL = "#1a1a2e"
DARK_BORDER = "#2d2d4e"
ACCENT = "#1565C0"
TEXT_MAIN = "#e0e0e0"
TEXT_DIM = "#888888"

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
QGroupBox {{
    border: 1px solid {DARK_BORDER};
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 14px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    padding: 0 6px;
}}
QLineEdit, QSpinBox {{
    background: {DARK_PANEL};
    color: {TEXT_MAIN};
    border: 1px solid {DARK_BORDER};
    border-radius: 4px;
    padding: 6px;
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
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {DARK_BORDER};
    border-radius: 3px;
    background: {DARK_PANEL};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
"""


class SettingsDialog(QDialog):
    """Settings dialog with Email and Monitoring tabs."""

    def __init__(self, notifier: EmailNotifier, parent=None):
        super().__init__(parent)
        self._notifier = notifier
        self.setWindowTitle("Настройки")
        self.setMinimumSize(520, 480)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Email tab
        tabs.addTab(self._build_email_tab(), "Email уведомления")
        # Monitoring tab
        tabs.addTab(self._build_monitoring_tab(), "Мониторинг")

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_save = QPushButton("Сохранить")
        btn_save.clicked.connect(self._save)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.setStyleSheet(f"background: {DARK_PANEL}; border: 1px solid {DARK_BORDER};")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        self._load_settings()

    def _build_email_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self._email_enabled = QCheckBox("Включить email уведомления")
        layout.addWidget(self._email_enabled)

        grp = QGroupBox("SMTP сервер")
        form = QFormLayout(grp)
        self._smtp_host = QLineEdit()
        self._smtp_host.setPlaceholderText("smtp.gmail.com")
        form.addRow("SMTP хост:", self._smtp_host)

        self._smtp_port = QSpinBox()
        self._smtp_port.setRange(1, 65535)
        self._smtp_port.setValue(587)
        form.addRow("Порт:", self._smtp_port)

        self._smtp_user = QLineEdit()
        self._smtp_user.setPlaceholderText("user@gmail.com")
        form.addRow("Логин:", self._smtp_user)

        self._smtp_password = QLineEdit()
        self._smtp_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._smtp_password.setPlaceholderText("App password")
        form.addRow("Пароль:", self._smtp_password)

        self._notify_to = QLineEdit()
        self._notify_to.setPlaceholderText("admin@example.com")
        form.addRow("Получатель:", self._notify_to)

        btn_test = QPushButton("Проверить подключение")
        btn_test.clicked.connect(self._test_smtp)
        form.addRow("", btn_test)
        layout.addWidget(grp)

        grp2 = QGroupBox("Уведомлять при")
        form2 = QFormLayout(grp2)
        self._notify_down = QCheckBox("Сайт недоступен")
        form2.addRow(self._notify_down)
        self._notify_threat = QCheckBox("Обнаружена угроза")
        form2.addRow(self._notify_threat)

        ssl_row = QHBoxLayout()
        self._notify_ssl = QCheckBox("SSL истекает менее чем за")
        self._ssl_days = QSpinBox()
        self._ssl_days.setRange(1, 90)
        self._ssl_days.setValue(14)
        self._ssl_days.setSuffix(" дней")
        ssl_row.addWidget(self._notify_ssl)
        ssl_row.addWidget(self._ssl_days)
        ssl_row.addStretch()
        form2.addRow(ssl_row)
        layout.addWidget(grp2)

        layout.addStretch()
        return w

    def _build_monitoring_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        grp = QGroupBox("Параметры мониторинга")
        form = QFormLayout(grp)

        self._interval = QSpinBox()
        self._interval.setRange(30, 3600)
        self._interval.setValue(60)
        self._interval.setSuffix(" сек")
        form.addRow("Интервал проверки:", self._interval)

        self._timeout = QSpinBox()
        self._timeout.setRange(5, 30)
        self._timeout.setValue(15)
        self._timeout.setSuffix(" сек")
        form.addRow("Таймаут запроса:", self._timeout)

        layout.addWidget(grp)

        grp2 = QGroupBox("Сканирование угроз")
        form2 = QFormLayout(grp2)
        self._threat_scan = QCheckBox("Сканировать угрозы")
        self._threat_scan.setChecked(True)
        form2.addRow(self._threat_scan)

        self._scan_every = QSpinBox()
        self._scan_every.setRange(1, 100)
        self._scan_every.setValue(10)
        self._scan_every.setSuffix(" проверок")
        form2.addRow("Частота сканирования: каждые", self._scan_every)

        layout.addWidget(grp2)
        layout.addStretch()
        return w

    def _load_settings(self):
        cfg = self._notifier.get_settings()
        self._email_enabled.setChecked(cfg.get("email_enabled", False))
        self._smtp_host.setText(cfg.get("smtp_host", "smtp.gmail.com"))
        self._smtp_port.setValue(cfg.get("smtp_port", 587))
        self._smtp_user.setText(cfg.get("smtp_user", ""))
        self._smtp_password.setText(cfg.get("smtp_password", ""))
        self._notify_to.setText(cfg.get("notify_to", ""))
        self._notify_down.setChecked(cfg.get("notify_on_down", True))
        self._notify_threat.setChecked(cfg.get("notify_on_threat", True))
        self._notify_ssl.setChecked(cfg.get("notify_on_ssl_expiry_days", 14) > 0)
        self._ssl_days.setValue(cfg.get("notify_on_ssl_expiry_days", 14))
        self._interval.setValue(cfg.get("monitor_interval", 60))
        self._timeout.setValue(cfg.get("monitor_timeout", 15))
        self._threat_scan.setChecked(cfg.get("threat_scan_enabled", True))
        self._scan_every.setValue(cfg.get("threat_scan_every_n", 10))

    def _save(self):
        settings = {
            "email_enabled": self._email_enabled.isChecked(),
            "smtp_host": self._smtp_host.text().strip(),
            "smtp_port": self._smtp_port.value(),
            "smtp_user": self._smtp_user.text().strip(),
            "smtp_password": self._smtp_password.text(),
            "notify_to": self._notify_to.text().strip(),
            "notify_on_down": self._notify_down.isChecked(),
            "notify_on_threat": self._notify_threat.isChecked(),
            "notify_on_ssl_expiry_days": self._ssl_days.value() if self._notify_ssl.isChecked() else 0,
            "monitor_interval": self._interval.value(),
            "monitor_timeout": self._timeout.value(),
            "threat_scan_enabled": self._threat_scan.isChecked(),
            "threat_scan_every_n": self._scan_every.value(),
        }
        self._notifier.save_settings(settings)
        self.accept()

    def _test_smtp(self):
        settings = {
            "smtp_host": self._smtp_host.text().strip(),
            "smtp_port": self._smtp_port.value(),
            "smtp_user": self._smtp_user.text().strip(),
            "smtp_password": self._smtp_password.text(),
        }
        if not settings["smtp_user"] or not settings["smtp_password"]:
            QMessageBox.warning(self, "Ошибка", "Заполните логин и пароль SMTP.")
            return
        err = self._notifier.test_connection(settings)
        if err is None:
            QMessageBox.information(self, "Успех", "Подключение к SMTP серверу успешно!")
        else:
            QMessageBox.warning(self, "Ошибка подключения", f"Не удалось подключиться:\n{err}")
