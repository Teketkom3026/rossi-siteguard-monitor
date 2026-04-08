"""
SiteGuard Monitor — License Dialog
Offline-first активация: ключ проверяется локально по HMAC.
Сервер используется опционально для синхронизации (3 сек таймаут).
407/502/timeout — не ошибка, активация всё равно проходит.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.license_validator import validate_key, PLAN_CONFIG
from core.license_manager import LicenseManager

logger = logging.getLogger("SiteGuard.LicenseDialog")


class _ServerSync(QObject):
    """Асинхронная синхронизация с сервером — не блокирует UI."""
    done = pyqtSignal(bool, str)

    def run(self, license_key: str):
        def _worker():
            try:
                import httpx
                resp = httpx.post(
                    "http://87.228.29.55/api/v1/license/activate",
                    json={
                        "license_key": license_key,
                        "device_id": LicenseManager.generate_hardware_id(),
                        "device_type": "windows",
                    },
                    timeout=3.0,
                    verify=False,
                )
                data = resp.json()
                self.done.emit(True, json.dumps(data))
            except Exception as e:
                # Сеть недоступна / прокси / таймаут — не критично
                logger.warning("Server sync skipped: %s", e)
                self.done.emit(False, str(e))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()


class LicenseDialog(QDialog):
    """
    Диалог активации лицензии.
    Активация ключа происходит ОФЛАЙН — сеть не требуется.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SiteGuard Monitor — Лицензия")
        self.setFixedWidth(520)
        self.setModal(True)
        self.license_manager = LicenseManager()
        self._activated_key: str | None = None
        self._setup_ui()
        self._check_existing_license()

    # ──────────────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────────────

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

        # ── Заголовок ──────────────────────────────────────────────
        title = QLabel("🛡 Rossi SiteGuard Monitor")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #e0e0ff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        # ── Ввод ключа ─────────────────────────────────────────────
        activation_box = QGroupBox("Активация лицензии")
        act_layout = QVBoxLayout(activation_box)

        hint = QLabel("Формат: SG-XXXXX-XXXXX-XXXXX-XXXXX-CHKSUM")
        hint.setStyleSheet("color: #555; font-size: 11px;")
        act_layout.addWidget(hint)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("SG-XXXXX-XXXXX-XXXXX-XXXXX-CHKSUM")
        self.key_input.setMaxLength(32)
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

        root.addWidget(activation_box)

        # ── Информация о лицензии (скрыта до активации) ────────────
        self.info_box = QGroupBox("Информация о лицензии")
        self.info_box.setVisible(False)
        info_layout = QVBoxLayout(self.info_box)

        def info_row(label_text, value_name):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #666;")
            val = QLabel("—")
            val.setStyleSheet("color: #e0e0ff; font-weight: bold;")
            setattr(self, value_name, val)
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(val)
            info_layout.addLayout(row)

        info_row("Тариф:", "plan_label")
        info_row("Максимум сайтов:", "max_sites_label")
        info_row("Лицензионный ключ:", "key_label")

        root.addWidget(self.info_box)

        # ── Пробный период ─────────────────────────────────────────
        trial_row = QHBoxLayout()
        trial_row.addWidget(QLabel("Нет ключа?"))
        trial_row.addStretch()
        self.trial_btn = QPushButton("Начать пробный период (14 дней)")
        self.trial_btn.setObjectName("trialBtn")
        self.trial_btn.setMinimumHeight(40)
        self.trial_btn.clicked.connect(self._start_trial)
        trial_row.addWidget(self.trial_btn)
        root.addLayout(trial_row)

        # ── Кнопки OK / Закрыть ────────────────────────────────────
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Продолжить")
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        root.addWidget(self.button_box)

    # ──────────────────────────────────────────────────────────────────
    # Logic
    # ──────────────────────────────────────────────────────────────────

    def _on_key_changed(self, text: str):
        """Форматирует ввод и включает кнопку при корректном ключе."""
        # Нормализуем — убираем лишние символы, ставим дефисы
        cleaned = text.upper().replace(" ", "").replace("_", "-")
        is_valid, _, _ = validate_key(cleaned) if len(cleaned) >= 30 else (False, "", {})
        self.activate_btn.setEnabled(is_valid)
        if is_valid:
            self.status_label.setText(
                '<span style="color:#2ed573;">✓ Формат ключа верный — нажмите Активировать</span>'
            )
        else:
            self.status_label.setText("")

    def _activate_key(self):
        """
        Офлайн-активация: проверяем ключ локально по HMAC.
        Сервер — только опциональная синхронизация.
        """
        key = self.key_input.text().strip().upper()
        is_valid, error, info = validate_key(key)

        if not is_valid:
            self.status_label.setText(
                f'<span style="color:#ff4757;">✗ {error}</span>'
            )
            return

        # Ключ валиден — сохраняем локально
        self.license_manager.store_license_key(key)
        self._activated_key = key
        self._show_info(key, info)

        self.status_label.setText(
            '<span style="color:#2ed573;">✓ Лицензия активирована</span>'
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        self.activate_btn.setEnabled(False)
        self.trial_btn.setEnabled(False)

        # Асинхронно сообщаем серверу (не блокируем UI, ошибки игнорируем)
        self._sync_with_server(key)

    def _start_trial(self):
        """Активирует 14-дневный пробный период без ключа и без сети."""
        TRIAL_KEY = "TRIAL-MODE"
        self.license_manager.store_license_key(TRIAL_KEY)
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
        """Показывает информацию о лицензии."""
        self.info_box.setVisible(True)
        self.plan_label.setText(info.get("label", info.get("plan", "—")).title())
        self.max_sites_label.setText(str(info.get("max_sites", "—")))
        self.key_label.setText(key[:20] + "…")

    def _sync_with_server(self, license_key: str):
        """Фоновая синхронизация с сервером — не влияет на активацию."""
        sync = _ServerSync()
        sync.setParent(self)
        sync.done.connect(lambda ok, msg: logger.info("Server sync: ok=%s %s", ok, msg[:80]))
        sync.run(license_key)

    def _check_existing_license(self):
        """При открытии показывает уже активированную лицензию."""
        key = self.license_manager.get_stored_key()
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
