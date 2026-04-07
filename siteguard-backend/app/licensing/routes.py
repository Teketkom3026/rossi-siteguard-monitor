"""
API endpoints for license management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.auth.jwt_handler import get_current_user
from app.licensing.key_generator import LicenseKeyGenerator
from app.licensing.models import (
    DeviceActivation,
    License,
    LicensePlan,
    LicenseStatus,
    User,
)

router = APIRouter(prefix="/api/v1/license", tags=["licensing"])


# ===== Pydantic schemas =====

class LicenseActivateRequest(BaseModel):
    license_key: str = Field(
        ..., example="SG-A3B5C-D7E9F-G2H4J-K6L8M-N1P3Q"
    )
    device_id: str = Field(..., example="abc123def456")
    device_type: str = Field(default="windows", example="windows")
    device_info: Optional[dict] = Field(default=None)


class LicenseActivateResponse(BaseModel):
    is_valid: bool
    message: str
    plan: Optional[str] = None
    max_sites: Optional[int] = None
    expires_at: Optional[datetime] = None
    days_remaining: Optional[int] = None
    features: Optional[dict] = None
    sites_remaining: Optional[int] = None


class LicenseInfoResponse(BaseModel):
    license_key: str
    plan: str
    status: str
    max_sites: int
    sites_used: int
    sites_remaining: int
    max_devices: int
    devices_used: int
    features: dict
    created_at: datetime
    expires_at: datetime
    days_remaining: int


class PurchaseLicenseRequest(BaseModel):
    plan: str = Field(..., example="professional")
    payment_method: str = Field(default="card")


class LicensePlanInfo(BaseModel):
    name: str
    display_name: str
    max_sites: int
    price: float
    price_display: str
    features: dict
    duration_days: int


# ===== Endpoints =====

@router.post("/activate", response_model=LicenseActivateResponse)
async def activate_license(
    request: LicenseActivateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Activate a license key on a device.
    Called on first application launch.
    """
    is_valid, message, license = await LicenseKeyGenerator.validate_license(
        db=db,
        license_key=request.license_key,
        device_id=request.device_id,
        device_type=request.device_type,
        device_info=request.device_info,
    )

    response = LicenseActivateResponse(
        is_valid=is_valid,
        message=message,
    )

    if license and is_valid:
        response.plan = license.plan.value
        response.max_sites = license.max_sites
        response.expires_at = license.expires_at
        response.days_remaining = license.days_remaining
        response.features = license.features
        response.sites_remaining = license.sites_remaining

    return response


@router.post("/validate")
async def validate_license(
    request: LicenseActivateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Periodic license validation (heartbeat).
    Application calls this every 24 hours.
    """
    is_valid, message, license = await LicenseKeyGenerator.validate_license(
        db=db,
        license_key=request.license_key,
        device_id=request.device_id,
        device_type=request.device_type,
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=message,
        )

    return {
        "valid": True,
        "plan": license.plan.value,
        "expires_at": license.expires_at.isoformat(),
        "days_remaining": license.days_remaining,
        "max_sites": license.max_sites,
        "features": license.features,
    }


@router.get("/info", response_model=LicenseInfoResponse)
async def get_license_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get information about the current active license."""
    result = await db.execute(
        select(License)
        .where(License.user_id == current_user.id)
        .where(License.status == LicenseStatus.ACTIVE)
        .order_by(License.created_at.desc())
    )
    license = result.scalar_one_or_none()

    if not license:
        raise HTTPException(
            status_code=404,
            detail="No active license found",
        )

    sites_used = len(current_user.sites)

    return LicenseInfoResponse(
        license_key=license.license_key,
        plan=license.plan.value,
        status=license.status.value,
        max_sites=license.max_sites,
        sites_used=sites_used,
        sites_remaining=max(0, license.max_sites - sites_used),
        max_devices=license.max_devices,
        devices_used=len(license.activated_devices or []),
        features=license.features,
        created_at=license.created_at,
        expires_at=license.expires_at,
        days_remaining=license.days_remaining,
    )


@router.get("/plans", response_model=List[LicensePlanInfo])
async def get_available_plans():
    """Get list of available license plans."""
    plans = []
    for plan, config in LicenseKeyGenerator.PLAN_CONFIG.items():
        if plan == LicensePlan.TRIAL:
            price_display = "Free (14 days)"
        else:
            price_display = f"{config['price']:,.0f} RUB/year"

        plans.append(LicensePlanInfo(
            name=plan.value,
            display_name=plan.value.replace("_", " ").title(),
            max_sites=config["max_sites"],
            price=config["price"],
            price_display=price_display,
            features=config["features"],
            duration_days=config["duration_days"],
        ))

    return plans


@router.post("/deactivate-device")
async def deactivate_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a device (free up a slot)."""
    result = await db.execute(
        select(License)
        .where(License.user_id == current_user.id)
        .where(License.status == LicenseStatus.ACTIVE)
    )
    license = result.scalar_one_or_none()

    if not license:
        raise HTTPException(404, "License not found")

    devices = license.activated_devices or []
    new_devices = [d for d in devices if d.get("device_id") != device_id]

    if len(new_devices) == len(devices):
        raise HTTPException(404, "Device not found")

    license.activated_devices = new_devices

    # Deactivate in the activations table
    await db.execute(
        update(DeviceActivation)
        .where(DeviceActivation.license_id == license.id)
        .where(DeviceActivation.device_id == device_id)
        .values(is_active=False)
    )

    await db.commit()

    return {"message": "Device deactivated"}
