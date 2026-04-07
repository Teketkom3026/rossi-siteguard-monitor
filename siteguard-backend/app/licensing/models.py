"""
Licensing data models.
Defines User, License, MonitoredSite, and DeviceActivation tables,
along with LicensePlan and LicenseStatus enums.
"""
import enum
from datetime import datetime, timedelta

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class LicensePlan(enum.Enum):
    """Available license plans."""
    TRIAL = "trial"                # 14 days free
    STARTER = "starter"            # Up to 5 sites
    PROFESSIONAL = "professional"  # Up to 25 sites
    BUSINESS = "business"          # Up to 100 sites
    ENTERPRISE = "enterprise"      # Unlimited


class LicenseStatus(enum.Enum):
    """License statuses."""
    ACTIVE = "active"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    company_name = Column(String(255))
    full_name = Column(String(255))
    phone = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

    # Firebase token for push notifications
    fcm_token = Column(String(500))

    # Notification preferences
    notification_settings = Column(JSON, default={
        "telegram_enabled": False,
        "telegram_chat_id": None,
        "email_enabled": True,
        "sms_enabled": False,
        "sms_phone": None,
        "push_enabled": True,
    })

    # Relationships
    licenses = relationship("License", back_populates="user")
    sites = relationship("MonitoredSite", back_populates="user")


class License(Base):
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    license_key = Column(
        String(64), unique=True, nullable=False, index=True
    )
    plan = Column(
        Enum(LicensePlan), nullable=False, default=LicensePlan.TRIAL
    )
    status = Column(
        Enum(LicenseStatus), nullable=False,
        default=LicenseStatus.ACTIVE,
    )

    # Limits
    max_sites = Column(Integer, nullable=False, default=5)
    max_checks_per_day = Column(Integer, default=1000)
    features = Column(JSON, default={
        "availability_check": True,
        "ssl_check": True,
        "ui_tests": False,
        "security_scan": False,
        "malware_scan": False,
        "api_access": False,
        "custom_intervals": False,
        "export_reports": False,
        "white_label": False,
    })

    # Dates
    created_at = Column(DateTime, default=datetime.utcnow)
    activated_at = Column(DateTime)
    expires_at = Column(DateTime, nullable=False)
    last_validated_at = Column(DateTime)

    # Device binding
    max_devices = Column(Integer, default=3)
    activated_devices = Column(JSON, default=[])

    # Payment info
    payment_amount = Column(Float, default=0)
    payment_currency = Column(String(3), default="RUB")
    payment_method = Column(String(50))
    payment_id = Column(String(255))

    # Relationships
    user = relationship("User", back_populates="licenses")

    @property
    def is_valid(self):
        return (
            self.status == LicenseStatus.ACTIVE
            and self.expires_at > datetime.utcnow()
        )

    @property
    def days_remaining(self):
        if self.expires_at:
            delta = self.expires_at - datetime.utcnow()
            return max(0, delta.days)
        return 0

    @property
    def sites_remaining(self):
        used = len(self.user.sites) if self.user else 0
        return max(0, self.max_sites - used)


class MonitoredSite(Base):
    __tablename__ = "monitored_sites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    domain = Column(String(255), nullable=False)
    name = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Monitoring settings
    check_interval = Column(Integer, default=300)  # seconds
    settings = Column(JSON, default={
        "check_availability": True,
        "check_ssl": True,
        "check_ui": True,
        "check_security": True,
        "check_malware": True,
        "critical_pages": ["/"],
        "ui_elements": [],
    })

    # Current status
    current_status = Column(JSON, default={})
    last_check_at = Column(DateTime)

    # Relationships
    user = relationship("User", back_populates="sites")


class DeviceActivation(Base):
    __tablename__ = "device_activations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    license_id = Column(
        Integer, ForeignKey("licenses.id"), nullable=False
    )
    device_id = Column(String(255), nullable=False)  # Hardware ID
    device_type = Column(String(50))  # windows, android
    device_name = Column(String(255))
    device_info = Column(JSON)  # OS version, etc.
    activated_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
