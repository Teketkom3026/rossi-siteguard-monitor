"""
Admin panel routes
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from typing import Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth.jwt_handler import get_current_admin_user
from app.licensing.models import (
    User, License, LicensePlan, LicenseStatus, MonitoredSite, DeviceActivation
)
from app.licensing.key_generator import LicenseKeyGenerator

import os

router = APIRouter(prefix="/admin", tags=["admin"])

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)


# ===== Admin Panel HTML =====
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def admin_panel(request: Request):
    """Serve the admin panel HTML"""
    return templates.TemplateResponse("admin.html", {"request": request})


# ===== Admin API Endpoints =====
class CreateLicenseRequest(BaseModel):
    user_email: str
    plan: str = Field(..., example="professional")
    custom_duration_days: Optional[int] = None


class RevokeLicenseRequest(BaseModel):
    reason: Optional[str] = None


class CreateUserRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    is_admin: bool = False


@router.get("/api/stats")
async def get_admin_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get admin dashboard statistics"""
    # Total users
    total_users_result = await db.execute(select(func.count(User.id)))
    total_users = total_users_result.scalar() or 0

    # Active licenses
    active_licenses_result = await db.execute(
        select(func.count(License.id)).where(
            License.status == LicenseStatus.ACTIVE
        )
    )
    active_licenses = active_licenses_result.scalar() or 0

    # Total revenue
    revenue_result = await db.execute(
        select(func.sum(License.payment_amount)).where(
            License.payment_amount > 0
        )
    )
    total_revenue = revenue_result.scalar() or 0

    # Monitored sites
    total_sites_result = await db.execute(
        select(func.count(MonitoredSite.id))
    )
    total_sites = total_sites_result.scalar() or 0

    # Licenses by plan
    plans_result = await db.execute(
        select(License.plan, func.count(License.id))
        .where(License.status == LicenseStatus.ACTIVE)
        .group_by(License.plan)
    )
    plans_breakdown = {row[0].value: row[1] for row in plans_result.fetchall()}

    # Recent registrations (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_users_result = await db.execute(
        select(func.count(User.id)).where(
            User.created_at >= thirty_days_ago
        )
    )
    recent_users = recent_users_result.scalar() or 0

    return {
        "total_users": total_users,
        "active_licenses": active_licenses,
        "total_revenue": round(total_revenue, 2),
        "total_sites": total_sites,
        "plans_breakdown": plans_breakdown,
        "recent_users_30d": recent_users,
    }


@router.get("/api/licenses")
async def list_licenses(
    status_filter: Optional[str] = None,
    plan_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List all licenses with filtering"""
    query = select(License).order_by(License.created_at.desc())

    if status_filter:
        try:
            status_enum = LicenseStatus(status_filter)
            query = query.where(License.status == status_enum)
        except ValueError:
            pass

    if plan_filter:
        try:
            plan_enum = LicensePlan(plan_filter)
            query = query.where(License.plan == plan_enum)
        except ValueError:
            pass

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    licenses = result.scalars().all()

    return [
        {
            "id": lic.id,
            "license_key": lic.license_key,
            "user_id": lic.user_id,
            "plan": lic.plan.value,
            "status": lic.status.value,
            "max_sites": lic.max_sites,
            "max_devices": lic.max_devices,
            "devices_used": len(lic.activated_devices or []),
            "created_at": lic.created_at.isoformat() if lic.created_at else None,
            "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
            "days_remaining": lic.days_remaining,
            "payment_amount": lic.payment_amount,
            "payment_method": lic.payment_method,
        }
        for lic in licenses
    ]


@router.post("/api/licenses")
async def create_license(
    request: CreateLicenseRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a new license for a user"""
    # Find user by email
    result = await db.execute(
        select(User).where(User.email == request.user_email)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, f"User {request.user_email} not found")

    try:
        plan = LicensePlan(request.plan)
    except ValueError:
        raise HTTPException(400, f"Invalid plan: {request.plan}")

    license = await LicenseKeyGenerator.create_license(
        db=db,
        user_id=user.id,
        plan=plan,
        custom_duration_days=request.custom_duration_days,
    )

    return {
        "id": license.id,
        "license_key": license.license_key,
        "plan": license.plan.value,
        "status": license.status.value,
        "expires_at": license.expires_at.isoformat(),
        "message": f"License created for {request.user_email}",
    }


@router.post("/api/licenses/{license_id}/revoke")
async def revoke_license(
    license_id: int,
    request: RevokeLicenseRequest,
    db: AsyncSession = Depends(get_db)
):
    """Revoke a license"""
    result = await db.execute(
        select(License).where(License.id == license_id)
    )
    license = result.scalar_one_or_none()
    if not license:
        raise HTTPException(404, "License not found")

    license.status = LicenseStatus.REVOKED
    await db.commit()

    return {
        "message": f"License {license.license_key} revoked",
        "reason": request.reason,
    }


@router.post("/api/licenses/{license_id}/activate")
async def activate_license_admin(
    license_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Reactivate a suspended/revoked license"""
    result = await db.execute(
        select(License).where(License.id == license_id)
    )
    license = result.scalar_one_or_none()
    if not license:
        raise HTTPException(404, "License not found")

    license.status = LicenseStatus.ACTIVE
    await db.commit()

    return {"message": f"License {license.license_key} activated"}


@router.get("/api/users")
async def list_users(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List all users"""
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    users = result.scalars().all()

    return [
        {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "company_name": user.company_name,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
        for user in users
    ]


@router.post("/api/users")
async def create_user(
    request: CreateUserRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a new user"""
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    # Check if user exists
    existing = await db.execute(
        select(User).where(User.email == request.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "User with this email already exists")

    user = User(
        email=request.email,
        password_hash=pwd_context.hash(request.password),
        full_name=request.full_name,
        company_name=request.company_name,
        is_admin=request.is_admin,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {
        "id": user.id,
        "email": user.email,
        "message": "User created successfully",
    }


@router.post("/api/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Toggle user active status"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    user.is_active = not user.is_active
    await db.commit()

    return {
        "id": user.id,
        "is_active": user.is_active,
        "message": f"User {'activated' if user.is_active else 'deactivated'}",
    }
