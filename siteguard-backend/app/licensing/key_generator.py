"""
License key generator and validator.
Key format: SG-XXXXX-XXXXX-XXXXX-XXXXX-CHECKSUM
"""
import hashlib
import hmac
import platform
import secrets
import string
import subprocess
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.licensing.models import (
    DeviceActivation,
    License,
    LicensePlan,
    LicenseStatus,
    User,
)


class LicenseKeyGenerator:
    """License key generator and validator."""

    SECRET_KEY = settings.LICENSE_SECRET_KEY  # Signing secret

    KEY_LENGTH = 25  # 5 groups of 5 characters

    # Plan configurations
    PLAN_CONFIG = {
        LicensePlan.TRIAL: {
            "max_sites": 3,
            "max_checks_per_day": 100,
            "duration_days": 14,
            "price": 0,
            "features": {
                "availability_check": True,
                "ssl_check": True,
                "ui_tests": False,
                "security_scan": False,
                "malware_scan": False,
                "api_access": False,
                "custom_intervals": False,
                "export_reports": False,
                "white_label": False,
            },
            "max_devices": 1,
        },
        LicensePlan.STARTER: {
            "max_sites": 5,
            "max_checks_per_day": 500,
            "duration_days": 365,
            "price": 2990,
            "features": {
                "availability_check": True,
                "ssl_check": True,
                "ui_tests": True,
                "security_scan": False,
                "malware_scan": False,
                "api_access": False,
                "custom_intervals": False,
                "export_reports": True,
                "white_label": False,
            },
            "max_devices": 2,
        },
        LicensePlan.PROFESSIONAL: {
            "max_sites": 25,
            "max_checks_per_day": 5000,
            "duration_days": 365,
            "price": 9990,
            "features": {
                "availability_check": True,
                "ssl_check": True,
                "ui_tests": True,
                "security_scan": True,
                "malware_scan": True,
                "api_access": True,
                "custom_intervals": True,
                "export_reports": True,
                "white_label": False,
            },
            "max_devices": 5,
        },
        LicensePlan.BUSINESS: {
            "max_sites": 100,
            "max_checks_per_day": 50000,
            "duration_days": 365,
            "price": 29990,
            "features": {
                "availability_check": True,
                "ssl_check": True,
                "ui_tests": True,
                "security_scan": True,
                "malware_scan": True,
                "api_access": True,
                "custom_intervals": True,
                "export_reports": True,
                "white_label": True,
            },
            "max_devices": 10,
        },
        LicensePlan.ENTERPRISE: {
            "max_sites": 999999,
            "max_checks_per_day": 999999,
            "duration_days": 365,
            "price": 99990,
            "features": {
                "availability_check": True,
                "ssl_check": True,
                "ui_tests": True,
                "security_scan": True,
                "malware_scan": True,
                "api_access": True,
                "custom_intervals": True,
                "export_reports": True,
                "white_label": True,
            },
            "max_devices": 50,
        },
    }

    @classmethod
    def generate_key(cls) -> str:
        """
        Generate a unique license key.
        Format: SG-XXXXX-XXXXX-XXXXX-XXXXX-CHECKSUM
        """
        chars = string.ascii_uppercase + string.digits
        # Remove ambiguous characters: O/0, I/1, L
        chars = chars.replace("O", "").replace("I", "").replace("L", "")

        # Generate 4 groups of 5 characters
        groups = []
        for _ in range(4):
            group = "".join(secrets.choice(chars) for _ in range(5))
            groups.append(group)

        key = f"SG-{'-'.join(groups)}"

        # Add checksum
        checksum = cls._calculate_checksum(key)
        key_with_check = f"{key}-{checksum}"

        return key_with_check

    @classmethod
    def _calculate_checksum(cls, key: str) -> str:
        """Calculate HMAC checksum for the key."""
        mac = hmac.new(
            cls.SECRET_KEY.encode(),
            key.encode(),
            hashlib.sha256,
        ).hexdigest()[:5].upper()
        return mac

    @classmethod
    def validate_key_format(cls, key: str) -> bool:
        """Validate the format and checksum of a license key."""
        parts = key.split("-")
        if len(parts) != 6:
            return False
        if parts[0] != "SG":
            return False

        # Verify checksum
        key_without_check = "-".join(parts[:5])
        expected_checksum = cls._calculate_checksum(key_without_check)
        return parts[5] == expected_checksum

    @classmethod
    async def create_license(
        cls,
        db: AsyncSession,
        user_id: int,
        plan: LicensePlan,
        payment_amount: float = 0,
        payment_method: str = None,
        payment_id: str = None,
        custom_duration_days: int = None,
    ) -> License:
        """Create a new license for a user."""
        config = cls.PLAN_CONFIG[plan]
        key = cls.generate_key()
        duration = custom_duration_days or config["duration_days"]

        license = License(
            user_id=user_id,
            license_key=key,
            plan=plan,
            status=LicenseStatus.ACTIVE,
            max_sites=config["max_sites"],
            max_checks_per_day=config["max_checks_per_day"],
            features=config["features"],
            expires_at=datetime.utcnow() + timedelta(days=duration),
            activated_at=datetime.utcnow(),
            max_devices=config["max_devices"],
            activated_devices=[],
            payment_amount=payment_amount,
            payment_currency="RUB",
            payment_method=payment_method,
            payment_id=payment_id,
        )

        db.add(license)
        await db.commit()
        await db.refresh(license)

        return license

    @classmethod
    async def validate_license(
        cls,
        db: AsyncSession,
        license_key: str,
        device_id: str,
        device_type: str = "windows",
        device_info: dict = None,
    ) -> Tuple[bool, str, Optional[License]]:
        """
        Validate a license key and bind it to a device.

        Returns:
            Tuple of (is_valid, message, license_object).
        """
        # 1. Check format
        if not cls.validate_key_format(license_key):
            return False, "Invalid key format", None

        # 2. Look up in database
        result = await db.execute(
            select(License).where(License.license_key == license_key)
        )
        license = result.scalar_one_or_none()

        if not license:
            return False, "Key not found", None

        # 3. Check status
        if license.status == LicenseStatus.REVOKED:
            return False, "License revoked", None

        if license.status == LicenseStatus.SUSPENDED:
            return False, "License suspended", None

        # 4. Check expiration
        if license.expires_at < datetime.utcnow():
            license.status = LicenseStatus.EXPIRED
            await db.commit()
            return False, "License expired", license

        # 5. Check device binding
        activated_devices = license.activated_devices or []
        device_ids = [d.get("device_id") for d in activated_devices]

        if device_id not in device_ids:
            # New device -- check limit
            if len(activated_devices) >= license.max_devices:
                return (
                    False,
                    f"Device limit reached ({license.max_devices}). "
                    f"Deactivate one of the existing devices.",
                    license,
                )

            # Add device
            activated_devices.append({
                "device_id": device_id,
                "device_type": device_type,
                "device_info": device_info or {},
                "activated_at": datetime.utcnow().isoformat(),
            })
            license.activated_devices = activated_devices

            # Create activation record
            activation = DeviceActivation(
                license_id=license.id,
                device_id=device_id,
                device_type=device_type,
                device_name=(
                    device_info.get("name", "") if device_info else ""
                ),
                device_info=device_info,
            )
            db.add(activation)

        # 6. Update last validation timestamp
        license.last_validated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(license)

        return True, "License is active", license

    @classmethod
    def get_hardware_id(cls) -> str:
        """Get a unique hardware identifier for the current device."""
        system_info = (
            f"{platform.node()}-{platform.machine()}-{platform.processor()}"
        )

        # Try to get MAC address
        try:
            mac = uuid.getnode()
            system_info += f"-{mac}"
        except Exception:
            pass

        # Try to get disk serial number
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["wmic", "diskdrive", "get", "serialnumber"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                serial = result.stdout.strip().split("\n")[-1].strip()
                if serial:
                    system_info += f"-{serial}"
            elif platform.system() == "Linux":
                result = subprocess.run(
                    ["cat", "/etc/machine-id"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    system_info += f"-{result.stdout.strip()}"
        except Exception:
            pass

        # Hash and return
        return hashlib.sha256(system_info.encode()).hexdigest()[:32]
