"""
SiteGuard Monitor Pro - License Manager

Local license management: store license key, validate periodically,
hardware ID generation, offline grace period tracking, and local
setup data persistence.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("SiteGuard.LicenseManager")

# Offline grace period in seconds (7 days)
OFFLINE_GRACE_PERIOD = 7 * 24 * 60 * 60


class LicenseManager:
    """Manages license state on the local machine."""

    def __init__(self):
        self._config_dir = self._get_config_dir()
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._license_file = self._config_dir / "license.json"
        self._setup_file = self._config_dir / "setup_data.json"
        self._state_file = self._config_dir / "state.json"

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    @staticmethod
    def _get_config_dir() -> Path:
        base = os.getenv("APPDATA", str(Path.home()))
        return Path(base) / "SiteGuard Monitor"

    # ------------------------------------------------------------------
    # Hardware ID
    # ------------------------------------------------------------------
    @staticmethod
    def generate_hardware_id() -> str:
        """
        Generate a deterministic hardware ID from machine characteristics.
        Uses a combination of hostname, platform info, and MAC address.
        """
        components = [
            platform.node(),
            platform.machine(),
            platform.processor(),
            str(uuid.getnode()),  # MAC-based node
        ]
        raw = "|".join(components)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    # ------------------------------------------------------------------
    # License key storage
    # ------------------------------------------------------------------
    def store_license_key(self, key: str, license_info: dict | None = None):
        """Persist the license key and optional info locally."""
        data = self._load_license_data()
        data["license_key"] = key
        data["activated_at"] = datetime.utcnow().isoformat()
        data["hardware_id"] = self.generate_hardware_id()
        data["last_validated"] = datetime.utcnow().isoformat()
        if license_info:
            data["license_info"] = license_info
        self._save_license_data(data)
        logger.info("License key stored successfully")

    def get_stored_key(self) -> str | None:
        data = self._load_license_data()
        return data.get("license_key")

    def clear_license(self):
        """Remove the stored license."""
        if self._license_file.exists():
            self._license_file.unlink()
        logger.info("License cleared")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate(self) -> bool:
        """
        Validate the license. Tries server first; falls back to
        offline grace period if server is unreachable.
        """
        data = self._load_license_data()
        key = data.get("license_key")
        if not key:
            logger.warning("No license key stored")
            return False

        # Try server validation
        try:
            from core.api_client import APIClient

            client = APIClient()
            result = client.validate_license()
            if result and result.get("valid"):
                data["last_validated"] = datetime.utcnow().isoformat()
                data["license_info"] = result.get("license_info", data.get("license_info", {}))
                self._save_license_data(data)
                logger.info("License validated online")
                return True
            elif result and not result.get("valid"):
                logger.warning("License invalid per server")
                return False
        except Exception as e:
            logger.warning("Could not reach server for validation: %s", e)

        # Offline grace period
        return self._check_offline_grace(data)

    def validate_on_start(self) -> tuple[bool, str]:
        """
        Validate at application startup.
        Returns (is_valid, message).
        """
        data = self._load_license_data()
        key = data.get("license_key")

        if not key:
            return False, "No license key found. Please activate a license."

        # Try online validation
        try:
            from core.api_client import APIClient

            client = APIClient()
            result = client.validate_license()
            if result is not None:
                if result.get("valid"):
                    data["last_validated"] = datetime.utcnow().isoformat()
                    data["license_info"] = result.get("license_info", data.get("license_info", {}))
                    self._save_license_data(data)
                    return True, "License is valid"
                else:
                    reason = result.get("reason", "License expired or revoked")
                    return False, reason
        except Exception as e:
            logger.warning("Server unreachable during startup validation: %s", e)

        # Offline fallback
        if self._check_offline_grace(data):
            return True, "License valid (offline mode - grace period active)"
        else:
            return False, "License could not be validated and offline grace period has expired."

    def _check_offline_grace(self, data: dict) -> bool:
        """Check if we are still within the offline grace period."""
        last_validated = data.get("last_validated")
        if not last_validated:
            return False
        try:
            last_dt = datetime.fromisoformat(last_validated)
            elapsed = (datetime.utcnow() - last_dt).total_seconds()
            if elapsed <= OFFLINE_GRACE_PERIOD:
                logger.info(
                    "Within offline grace period (%.0f/%.0f seconds)",
                    elapsed,
                    OFFLINE_GRACE_PERIOD,
                )
                return True
            else:
                logger.warning("Offline grace period expired")
                return False
        except Exception:
            return False

    # ------------------------------------------------------------------
    # License info
    # ------------------------------------------------------------------
    def get_license_info(self) -> dict | None:
        """Return locally cached license info, or fetch from server."""
        data = self._load_license_data()
        info = data.get("license_info")

        # Try refreshing from server
        try:
            from core.api_client import APIClient

            client = APIClient()
            server_info = client.get_license_info()
            if server_info:
                data["license_info"] = server_info
                self._save_license_data(data)
                return server_info
        except Exception:
            pass

        return info

    # ------------------------------------------------------------------
    # First-run and setup data
    # ------------------------------------------------------------------
    def is_first_run(self) -> bool:
        state = self._load_state()
        return not state.get("first_run_complete", False)

    def mark_first_run_complete(self):
        state = self._load_state()
        state["first_run_complete"] = True
        state["first_run_completed_at"] = datetime.utcnow().isoformat()
        self._save_state(state)

    def save_setup_data(self, data: dict):
        """Persist the setup wizard data."""
        self._setup_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Setup data saved")

    def load_setup_data(self) -> dict:
        """Load previously saved setup data."""
        if self._setup_file.exists():
            try:
                return json.loads(self._setup_file.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("Could not load setup data")
        return {}

    # ------------------------------------------------------------------
    # Internal JSON helpers
    # ------------------------------------------------------------------
    def _load_license_data(self) -> dict:
        if self._license_file.exists():
            try:
                return json.loads(self._license_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_license_data(self, data: dict):
        self._license_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_state(self) -> dict:
        if self._state_file.exists():
            try:
                return json.loads(self._state_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_state(self, data: dict):
        self._state_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
