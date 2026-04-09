"""
SiteGuard Monitor Pro — API Client

Использует ТОЛЬКО стандартную библиотеку Python (urllib).
Никаких внешних зависимостей (httpx, requests и т.д.) — совместимо с PyInstaller EXE.
"""
from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger("SiteGuard.APIClient")

DEFAULT_API_URL = os.getenv("SITEGUARD_API_URL", "http://87.228.29.55/api/v1")
DEFAULT_TIMEOUT = 10.0

# SSL context — игнорируем ошибки сертификата для HTTP-сервера
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


class APIClient:
    """HTTP клиент для SiteGuard backend. Только stdlib urllib."""

    def __init__(self, base_url: str | None = None, timeout: float = DEFAULT_TIMEOUT):
        self.base_url = (base_url or DEFAULT_API_URL).rstrip("/")
        self.timeout = timeout
        self._token: str | None = None
        self._license_key: str | None = None
        self._load_stored_credentials()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_config_dir(self) -> Path:
        config_dir = Path(os.getenv("APPDATA", str(Path.home()))) / "SiteGuard Monitor"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    def _load_stored_credentials(self):
        cred_file = self._get_config_dir() / "credentials.json"
        if cred_file.exists():
            try:
                data = json.loads(cred_file.read_text(encoding="utf-8"))
                self._token = data.get("token")
                self._license_key = data.get("license_key")
            except Exception:
                logger.warning("Could not load stored credentials")

    def _save_credentials(self):
        cred_file = self._get_config_dir() / "credentials.json"
        data = {"token": self._token, "license_key": self._license_key}
        cred_file.write_text(json.dumps(data), encoding="utf-8")

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SiteGuardMonitor/1.0.0",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if self._license_key:
            headers["X-License-Key"] = self._license_key
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_data: dict | None = None,
        params: dict | None = None,
    ) -> dict | None:
        """Выполняет HTTP-запрос через urllib. Возвращает dict или None при ошибке."""
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        body: bytes | None = None
        if json_data is not None:
            body = json.dumps(json_data).encode("utf-8")

        req = urllib.request.Request(url, data=body, method=method)
        for k, v in self._headers().items():
            req.add_header(k, v)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=_SSL_CTX) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {"raw": raw}
        except urllib.error.HTTPError as e:
            logger.error("HTTP %s %s -> %s", method, path, e.code)
            try:
                raw = e.read().decode("utf-8", errors="replace")
                return json.loads(raw)
            except Exception:
                return {"error": str(e), "status": e.code}
        except urllib.error.URLError as e:
            logger.error("URL error %s %s: %s", method, path, e.reason)
            return None
        except Exception as e:
            logger.error("Request failed %s %s: %s", method, path, e)
            return None

    # ------------------------------------------------------------------
    # License endpoints
    # ------------------------------------------------------------------
    def activate_license(self, license_key: str) -> dict | None:
        from core.license_manager import LicenseManager

        device_id = LicenseManager.generate_hardware_id()
        result = self._request(
            "POST",
            "/license/activate",
            json_data={
                "license_key": license_key,
                "device_id": device_id,
                "device_type": "windows",
                "device_info": {
                    "computer_name": os.getenv("COMPUTERNAME", "Desktop"),
                    "app_version": "1.0.0",
                },
            },
        )
        if result and result.get("is_valid"):
            self._license_key = license_key
            self._save_credentials()
        return result

    def validate_license(self) -> dict | None:
        from core.license_manager import LicenseManager

        device_id = LicenseManager.generate_hardware_id()
        return self._request(
            "POST",
            "/license/validate",
            json_data={
                "license_key": self._license_key,
                "device_id": device_id,
                "device_type": "windows",
            },
        )

    def get_license_info(self) -> dict | None:
        return self._request("GET", "/license/info")

    def deactivate_device(self) -> dict | None:
        from core.license_manager import LicenseManager

        device_id = LicenseManager.generate_hardware_id()
        result = self._request(
            "POST",
            "/license/deactivate-device",
            params={"device_id": device_id},
        )
        if result and result.get("message"):
            self._license_key = None
            self._token = None
            self._save_credentials()
        return result

    # ------------------------------------------------------------------
    # Dashboard / monitoring
    # ------------------------------------------------------------------
    def get_dashboard(self) -> dict | None:
        return self._request("GET", "/dashboard")

    def get_site_status(self, domain: str) -> dict | None:
        return self._request("GET", f"/sites/{domain}/status")

    def add_site(self, domain: str, settings: dict | None = None) -> dict | None:
        payload: dict[str, Any] = {"domain": domain}
        if settings:
            payload["settings"] = settings
        return self._request("POST", "/sites", json_data=payload)

    def remove_site(self, domain: str) -> dict | None:
        return self._request("DELETE", f"/sites/{domain}")

    def check_all_now(self) -> dict | None:
        return self._request("POST", "/monitoring/check-all")

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------
    def get_alerts(self, limit: int = 50, offset: int = 0) -> dict | None:
        return self._request("GET", "/alerts", params={"limit": limit, "offset": offset})

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------
    def export_report(self, filepath: str) -> bool:
        url = f"{self.base_url}/reports/export"
        req = urllib.request.Request(url, method="GET")
        for k, v in self._headers().items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=_SSL_CTX) as resp:
                Path(filepath).write_bytes(resp.read())
                return True
        except Exception as e:
            logger.error("Export report failed: %s", e)
            raise RuntimeError(f"Failed to export report: {e}") from e
