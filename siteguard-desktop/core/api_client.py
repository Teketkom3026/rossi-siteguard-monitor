"""
SiteGuard Monitor Pro - API Client

HTTP client (httpx) for communicating with the SiteGuard backend API.
Provides methods for license management, dashboard data, site operations,
alerts, and reporting.
"""
from __future__ import annotations

import logging
import json
import os
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("SiteGuard.APIClient")

# Default backend URL — points to the production server
# Can be overridden via environment variable SITEGUARD_API_URL
DEFAULT_API_URL = os.getenv("SITEGUARD_API_URL", "http://87.228.29.55/api/v1")
DEFAULT_TIMEOUT = 30.0


class APIClient:
    """HTTP client for communicating with the SiteGuard backend API."""

    def __init__(self, base_url: str | None = None, timeout: float = DEFAULT_TIMEOUT):
        self.base_url = (base_url or DEFAULT_API_URL).rstrip("/")
        self.timeout = timeout
        self._token: str | None = None
        self._license_key: str | None = None

        # Attempt to load stored credentials
        self._load_stored_credentials()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_config_dir(self) -> Path:
        config_dir = Path(os.getenv("APPDATA", str(Path.home()))) / "SiteGuard Monitor"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    def _load_stored_credentials(self):
        """Load API token and license key from local storage."""
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
        """Execute an HTTP request and return the JSON response."""
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout, verify=False) as client:
                response = client.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=json_data,
                    params=params,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error("HTTP %s %s -> %s: %s", method, path, e.response.status_code, e.response.text)
            try:
                return e.response.json()
            except Exception:
                return {"error": str(e)}
        except httpx.RequestError as e:
            logger.error("Request error %s %s: %s", method, path, e)
            return None

    # ------------------------------------------------------------------
    # License endpoints
    # ------------------------------------------------------------------
    def activate_license(self, license_key: str) -> dict | None:
        """
        Activate a license key (or start a trial with key='TRIAL').
        Returns license info on success.

        Sends: license_key, device_id (hardware fingerprint), device_type
        Matches FastAPI schema: LicenseActivateRequest
        """
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
        """Validate the current license key against the server (heartbeat)."""
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
        """Retrieve full license information from the server."""
        return self._request("GET", "/license/info")

    def deactivate_device(self) -> dict | None:
        """Deactivate the current device from the license."""
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
    # Dashboard / monitoring endpoints
    # ------------------------------------------------------------------
    def get_dashboard(self) -> dict | None:
        """Get the full dashboard overview data."""
        return self._request("GET", "/dashboard")

    def get_site_status(self, domain: str) -> dict | None:
        """Get detailed status for a specific site."""
        return self._request("GET", f"/sites/{domain}/status")

    def add_site(self, domain: str, settings: dict | None = None) -> dict | None:
        """Add a new site for monitoring."""
        payload: dict[str, Any] = {"domain": domain}
        if settings:
            payload["settings"] = settings
        return self._request("POST", "/sites", json_data=payload)

    def remove_site(self, domain: str) -> dict | None:
        """Remove a site from monitoring."""
        return self._request("DELETE", f"/sites/{domain}")

    def check_all_now(self) -> dict | None:
        """Trigger an immediate check of all monitored sites."""
        return self._request("POST", "/monitoring/check-all")

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------
    def get_alerts(self, limit: int = 50, offset: int = 0) -> dict | None:
        """Retrieve recent alerts."""
        return self._request("GET", "/alerts", params={"limit": limit, "offset": offset})

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------
    def export_report(self, filepath: str) -> bool:
        """Download a report and save it to the given file path."""
        url = f"{self.base_url}/reports/export"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, headers=self._headers())
                response.raise_for_status()
                Path(filepath).write_bytes(response.content)
                return True
        except Exception as e:
            logger.error("Export report failed: %s", e)
            raise RuntimeError(f"Failed to export report: {e}") from e
