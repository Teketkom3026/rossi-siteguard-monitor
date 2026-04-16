"""
EmailNotifier — sends email alerts via stdlib smtplib.
Reads config from %APPDATA%/SiteGuard Monitor/settings.json.
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("SiteGuard.Notifier")


def _app_data_dir() -> Path:
    base = Path(os.getenv("APPDATA", str(Path.home())))
    d = base / "SiteGuard Monitor"
    d.mkdir(parents=True, exist_ok=True)
    return d


DEFAULT_SETTINGS = {
    "email_enabled": False,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_password": "",
    "notify_to": "",
    "notify_on_down": True,
    "notify_on_threat": True,
    "notify_on_ssl_expiry_days": 14,
    "monitor_interval": 60,
    "monitor_timeout": 15,
    "threat_scan_enabled": True,
    "threat_scan_every_n": 10,
}


class EmailNotifier:
    """Sends email alerts for site status changes, threats, SSL expiry."""

    def __init__(self):
        self._settings_file = _app_data_dir() / "settings.json"

    def _load_settings(self) -> dict:
        try:
            if self._settings_file.exists():
                data = json.loads(self._settings_file.read_text(encoding="utf-8"))
                merged = dict(DEFAULT_SETTINGS)
                merged.update(data)
                return merged
        except Exception:
            pass
        return dict(DEFAULT_SETTINGS)

    def save_settings(self, settings: dict):
        try:
            self._settings_file.write_text(
                json.dumps(settings, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def get_settings(self) -> dict:
        return self._load_settings()

    def send_alert(self, subject: str, body: str) -> Optional[str]:
        """Send email via smtplib. Returns None on success, error string on failure."""
        cfg = self._load_settings()
        if not cfg.get("email_enabled"):
            return None
        if not cfg.get("smtp_user") or not cfg.get("notify_to"):
            return None
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = cfg["smtp_user"]
            msg["To"] = cfg["notify_to"]
            with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=10) as s:
                s.starttls()
                s.login(cfg["smtp_user"], cfg["smtp_password"])
                s.send_message(msg)
            return None
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return str(e)

    def test_connection(self, settings: dict) -> Optional[str]:
        """Test SMTP connection. Returns None on success, error string on failure."""
        try:
            with smtplib.SMTP(settings["smtp_host"], settings["smtp_port"], timeout=10) as s:
                s.starttls()
                s.login(settings["smtp_user"], settings["smtp_password"])
            return None
        except Exception as e:
            return str(e)

    def check_and_notify(self, old_status: dict, new_status: dict):
        """Compare old and new status, send alerts for state changes."""
        cfg = self._load_settings()
        if not cfg.get("email_enabled"):
            return

        for domain, new in new_status.items():
            old = old_status.get(domain, {})

            # Site went down
            if cfg.get("notify_on_down") and old.get("up") is True and new.get("up") is False:
                self.send_alert(
                    f"[SiteGuard] ✗ {domain} недоступен",
                    f"Сайт {domain} не отвечает.\n"
                    f"Время: {new.get('last_check', '—')}\n"
                    f"Ошибка: {new.get('error', '—')}"
                )

            # Site came back up
            if old.get("up") is False and new.get("up") is True:
                self.send_alert(
                    f"[SiteGuard] ✓ {domain} снова онлайн",
                    f"Сайт {domain} восстановился.\n"
                    f"Время: {new.get('last_check', '—')}"
                )

            # New threats
            if cfg.get("notify_on_threat"):
                old_threats = len(old.get("threats", []))
                new_threats = new.get("threats", [])
                if len(new_threats) > old_threats:
                    for t in new_threats[old_threats:]:
                        self.send_alert(
                            f"[SiteGuard] ⚠ Угроза на {domain}",
                            f"Обнаружена угроза на {domain}:\n"
                            f"Тип: {t['type']}\n"
                            f"Описание: {t['desc']}\n"
                            f"Время: {t['time']}"
                        )

            # SSL expiry
            ssl_days = new.get("ssl_days")
            notify_days = cfg.get("notify_on_ssl_expiry_days", 14)
            if (ssl_days is not None and ssl_days <= notify_days
                    and old.get("ssl_days", 999) > notify_days):
                self.send_alert(
                    f"[SiteGuard] SSL истекает: {domain}",
                    f"SSL сертификат {domain} истекает через {ssl_days} дней."
                )
