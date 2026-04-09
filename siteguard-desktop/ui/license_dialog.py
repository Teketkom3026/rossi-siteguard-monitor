"""
SiteGuard Monitor — License Dialog
Активация 100% офлайн — сеть НЕ НУЖНА.
Ключ проверяется локально по HMAC-SHA256.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from core.license_validator import validate_key, PLAN_CONFIG
from core.license_manager import LicenseManager

logger = logging.getLogger("SiteGuard.LicenseDialog")

SERVER_URL = "http://87.228.29.55/api/v1/license/activate"


def _background_server_notify(license_key: str) -> None:
    """
    Уведомляем сервер в фоновом daemon-потоке.
    Любая ошибка (прокси 407, таймаут, нет сети) молча игнорируется.
    Активация уже прошла офлайн — это просто статистика.
    """
    def _worker():
        try:
            # Используем только stdlib — urllib, чтобы не зависеть от httpx/requests в EXE
            import urllib.request
            import urllib.error
            import json as _json
            import ssl

            payload = _json.dumps({
                "license_key": license_key,
                "device_type": "windows",
                "source": "desktop_app",
            }).encode("utf-8")

            req = urllib.request.Request(
                SERVER_URL,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            with urllib.request.urlopen(req, timeout=3, context=ctx) as resp:
                logger.info("Server notified: %s", resp.status)
        except Exception as exc:
            # 407 прокси, 301 редирект, таймаут, нет сети — всё игнорируем
            logger.debug("Server notify skipped (not critical): %s", exc)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


class LicenseDialog(QDialog):
    """
    Диалог активации лицензии.
    Активация ключа происходит ОФЛАЙН — сеть НЕ ТРЕБУЕТСЯ.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SiteGuard Monitor — Активация")
        self.setFixedWidth(520)
        self.setModal(True)
        self.license_manager = LicenseManager()
        self._activated_key: str | None = None
        self._setup_ui()
        self._check_existing_license()

    # ──────────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog { background: #0f0f23; color: #e0e0ff; }
            QGroupBox {
                border: 1px solid #2a2a4a; border-radius: 8px;
                margin-top: 12px; padding: 12px;
                font-size: 13px; font-weight: bold; color: #e0e0ff;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QLineEdit {
                background: #1a1a2e; border: 1px solid #3a3a5a;
                border-radius: 6px; padding: 10px 14px;
                color: #e0e0ff; font-size: 14px; font-family: monospace;
            }
            QLineEdit:focus { border-color: #6c63ff; }
            QPushButton {
                border-radius: 7px; padding: 10px 20px;
                font-size: 13px; font-weight: bold;
            }
            QPushButton#activateBtn {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #6c63ff, stop:1 #e040fb);
                color: white; border: none;
            }
            QPushButton#activateBtn:disabled { background: #2a2a4a; color: #555; }
            QPushButton#trialBtn {
                background: #2ed573; color: #0f0f23; border: none;
            }
            QPushButton#trialBtn:disabled { background: #1a3a2a; color: #444; }
            QLabel#statusLabel { font-size: 12px; min-height: 20px; }
            QLabel { color: #a0a0c0; }
        """)

        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(24, 24, 24, 24)

        # Заголовок
        title = QLabel("Rossi SiteGuard Monitor")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #e0e0ff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel("Активация лицензии (офлайн — сеть не нужна)")
        subtitle.setStyleSheet("color: #555; font-size: 11px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle)

        # Ввод ключа
        act_box = QGroupBox("Лицензионный ключ")
        act_layout = QVBoxLayout(act_box)

        hint = QLabel("Формат: SG-XXXXX-XXXXX-XXXXX-XXXXX-CHKSUM")
        hint.setStyleSheet("color: #444; font-size: 11px;")
        act_layout.addWidget(hint)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("SG-XXXXX-XXXXX-XXXXX-XXXXX-CHKSUM")
        self.key_input.setMaxLength(34)
        self.key_input.textChanged.connect(self._on_key_changed)
        act_layout.addWidget(self.key_input)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        act_layout.addWidget(self.status_label)

        self.activate_btn = QPushButton("Активировать ключ")
        self.activate_btn.setObjectName("activateBtn")
        self.activate_btn.setEnabled(False)
        self.activate_btn.setMinimumHeight(44)
        self.activate_btn.clicked.connect(self._activate_key)
        act_layout.addWidget(self.activate_btn)

        root.addWidget(act_box)

        # Информация о лицензии
        self.info_box = QGroupBox("Информация о лицензии")
        self.info_box.setVisible(False)
        info_layout = QVBoxLayout(self.info_box)

        def _row(label_text: str, attr: str):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #666;")
            val = QLabel("—")
            val.setStyleSheet("color: #e0e0ff; font-weight: bold;")
            setattr(self, attr, val)
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(val)
            info_layout.addLayout(row)

        _row("Тариф:", "plan_label")
        _row("Максимум сайтов:", "max_sites_label")
        _row("Ключ:", "key_label")

        root.addWidget(self.info_box)

        # Пробный период
        trial_row = QHBoxLayout()
        trial_row.addWidget(QLabel("Нет ключа?"))
        trial_row.addStretch()
        self.trial_btn = QPushButton("Пробный период (14 дней)")
        self.trial_btn.setObjectName("trialBtn")
        self.trial_btn.setMinimumHeight(40)
        self.trial_btn.clicked.connect(self._start_trial)
        trial_row.addWidget(self.trial_btn)
        root.addLayout(trial_row)

        # OK / Отмена
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Продолжить")
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        root.addWidget(self.button_box)

    # ──────────────────────────────────────────────────────────────
    # Logic
    # ──────────────────────────────────────────────────────────────

    def _on_key_changed(self, text: str):
        cleaned = text.upper().strip()
        if len(cleaned) >= 30:
            is_valid, _, _ = validate_key(cleaned)
        else:
            is_valid = False
        self.activate_btn.setEnabled(is_valid)
        if is_valid:
            self.status_label.setText(
                '<span style="color:#2ed573;">✓ Формат ключа верный — нажмите Активировать</span>'
            )
        else:
            self.status_label.setText("")

    def _activate_key(self):
        """
        Офлайн-активация: проверяем HMAC локально.
        Сеть не нужна. Ошибка сети не влияет на результат.
        """
        key = self.key_input.text().strip().upper()
        is_valid, error, info = validate_key(key)

        if not is_valid:
            self.status_label.setText(
                f'<span style="color:#ff4757;">✗ {error}</span>'
            )
            return

        # Ключ валиден — сохраняем локально, показываем инфо
        try:
            self.license_manager.store_license_key(key)
        except Exception as e:
            logger.warning("Could not store license key: %s", e)

        self._activated_key = key
        self._show_info(key, info)
        self.status_label.setText(
            '<span style="color:#2ed573;">✓ Лицензия активирована успешно</span>'
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        self.activate_btn.setEnabled(False)
        self.trial_btn.setEnabled(False)

        # Фоновое уведомление сервера — не влияет на активацию
        _background_server_notify(key)

    def _start_trial(self):
        """14-дневный пробный период — без ключа и без сети."""
        TRIAL_KEY = "TRIAL-MODE"
        try:
            self.license_manager.store_license_key(TRIAL_KEY)
        except Exception as e:
            logger.warning("Could not store trial key: %s", e)
        self._activated_key = TRIAL_KEY
        self.status_label.setText(
            '<span style="color:#2ed573;">✓ Пробный период активирован (14 дней)</span>'
        )
        self.info_box.setVisible(True)
        self.plan_label.setText("Trial")
        self.max_sites_label.setText("3")
        self.key_label.setText("TRIAL-MODE")
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        self.trial_btn.setEnabled(False)
        self.activate_btn.setEnabled(False)

    def _show_info(self, key: str, info: dict):
        self.info_box.setVisible(True)
        plan = info.get("label", info.get("plan", "—"))
        self.plan_label.setText(str(plan).title())
        self.max_sites_label.setText(str(info.get("max_sites", "—")))
        self.key_label.setText(key[:22] + "…" if len(key) > 22 else key)

    def _check_existing_license(self):
        """При открытии восстанавливает уже активированную лицензию."""
        try:
            key = self.license_manager.get_stored_key()
        except Exception:
            return
        if not key:
            return
        if key == "TRIAL-MODE":
            self._start_trial()
            return
        is_valid, _, info = validate_key(key)
        if is_valid:
            self.key_input.setText(key)
            self._activated_key = key
            self._show_info(key, info)
            self.status_label.setText(
                '<span style="color:#2ed573;">✓ Лицензия уже активирована</span>'
            )
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
            self.activate_btn.setEnabled(False)

    def get_activated_key(self) -> str | None:
        return self._activated_key
