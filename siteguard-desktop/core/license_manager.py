"""
SiteGuard Monitor Pro - License Manager

Local license management: store license key, validate via offline HMAC,
hardware ID generation, and local setup data persistence.
All operations are offline — no network calls.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from core.license_validator import validate_key, PLAN_CONFIG

logger = logging.getLogger("SiteGuard.LicenseManager")


class LicenseManager:
    """Manages license state on the local machine — fully offline."""

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
            str(uuid.getnode()),
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
        if license_info:
            data["license_info"] = license_info
        self._save_license_data(data)
        logger.info("License key stored successfully")

    def save_license(self, key: str, validation_result: dict):
        """Convenience helper: write license.json from a validate_key() result."""
        self.store_license_key(key, validation_result)

    def get_stored_key(self) -> str | None:
        data = self._load_license_data()
        return data.get("license_key")

    def clear_license(self):
        """Remove the stored license."""
        if self._license_file.exists():
            self._license_file.unlink()
        logger.info("License cleared")

    # ------------------------------------------------------------------
    # Validation (offline only)
    # ------------------------------------------------------------------
    def validate(self) -> bool:
        """Validate the license using offline HMAC check."""
        data = self._load_license_data()
        key = data.get("license_key")
        if not key:
            logger.warning("No license key stored")
            return False

        is_valid, _msg, info = validate_key(key)
        if not is_valid:
            logger.warning("License key invalid: %s", _msg)
            return False

        # Check expiry from stored license_info
        stored_info = data.get("license_info", {})
        expires_str = stored_info.get("expires")
        if expires_str:
            try:
                expires_dt = datetime.fromisoformat(expires_str)
                if datetime.utcnow() > expires_dt:
                    logger.warning("License expired on %s", expires_str)
                    return False
            except (ValueError, TypeError):
                pass

        logger.info("License validated offline")
        return True

    def validate_on_start(self) -> tuple[bool, str]:
        """
        Validate at application startup.
        Returns (is_valid, message).
        """
        data = self._load_license_data()
        key = data.get("license_key")
        if not key:
            return False, "No license key found. Please activate a license."

        is_valid, error_msg, info = validate_key(key)
        if not is_valid:
            return False, error_msg or "License key is invalid."

        # Check expiry
        stored_info = data.get("license_info", {})
        expires_str = stored_info.get("expires")
        if expires_str:
            try:
                expires_dt = datetime.fromisoformat(expires_str)
                if datetime.utcnow() > expires_dt:
                    return False, "License has expired. Please renew."
            except (ValueError, TypeError):
                pass

        return True, "License is valid"

    # ------------------------------------------------------------------
    # License info (offline only)
    # ------------------------------------------------------------------
    def get_license_info(self) -> dict | None:
        """
        Read license.json and return plan/expiry info using offline
        HMAC validation. No network calls.
        """
        data = self._load_license_data()
        key = data.get("license_key")
        if not key:
            return None

        is_valid, _msg, info = validate_key(key)
        if not is_valid:
            return None

        stored_info = data.get("license_info", {})
        plan = info.get("plan", "unknown")
        label = info.get("label", plan.capitalize())
        max_sites = info.get("max_sites", 0)

        # Calculate days remaining from stored expiry
        days_remaining = 0
        expires_str = stored_info.get("expires")
        if expires_str:
            try:
                expires_dt = datetime.fromisoformat(expires_str)
                days_remaining = max(0, (expires_dt - datetime.utcnow()).days)
            except (ValueError, TypeError):
                # Fallback: use plan default days
                cfg = PLAN_CONFIG.get(plan, {})
                days_remaining = cfg.get("days", 0)
        else:
            # No expiry stored — use plan default
            cfg = PLAN_CONFIG.get(plan, {})
            days_remaining = cfg.get("days", 0)

        return {
            "plan": label,
            "days_remaining": days_remaining,
            "max_sites": max_sites,
            "license_key": key,
        }

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
