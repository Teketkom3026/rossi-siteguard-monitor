"""
API endpoints for site monitoring.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict
from datetime import datetime

from app.database import get_db
from app.auth.jwt_handler import get_current_user
from app.licensing.models import (
    License,
    LicenseStatus,
    MonitoredSite,
    User,
)

router = APIRouter(prefix="/api/v1/monitor", tags=["monitoring"])


# ===== Pydantic schemas =====

class AddSiteRequest(BaseModel):
    domain: str = Field(..., example="example.com")
    name: Optional[str] = Field(None, example="My Site")
    check_interval: int = Field(default=300, ge=60, le=3600)
    settings: Optional[dict] = Field(default=None)


class UpdateSiteRequest(BaseModel):
    name: Optional[str] = None
    check_interval: Optional[int] = Field(None, ge=60, le=3600)
    is_active: Optional[bool] = None
    settings: Optional[dict] = None


class SiteResponse(BaseModel):
    id: int
    domain: str
    name: Optional[str]
    is_active: bool
    check_interval: int
    settings: dict
    current_status: dict
    last_check_at: Optional[datetime]
    created_at: datetime


class SiteStatusResponse(BaseModel):
    domain: str
    is_available: bool
    http_status: Optional[int]
    response_time_ms: Optional[float]
    ssl_valid: Optional[bool]
    ssl_days_left: Optional[int]
    security_score: Optional[int]
    malware_detected: Optional[bool]
    ui_elements_ok: Optional[int]
    ui_elements_total: Optional[int]
    overall_severity: str
    issues: List[dict]
    last_check_at: Optional[datetime]
    sitemap_tree: Optional[dict]


class DashboardResponse(BaseModel):
    total_sites: int
    sites_ok: int
    sites_with_issues: int
    ssl_expiring: int
    avg_security_score: float
    sites: List[SiteStatusResponse]
    last_updated: datetime


# ===== Helpers =====

async def check_license_and_limits(
    user: User, db: AsyncSession
) -> License:
    """Check that user has a valid active license."""
    result = await db.execute(
        select(License)
        .where(License.user_id == user.id)
        .where(License.status == LicenseStatus.ACTIVE)
        .order_by(License.created_at.desc())
    )
    license = result.scalar_one_or_none()

    if not license:
        raise HTTPException(
            status_code=403,
            detail="No active license",
        )

    if not license.is_valid:
        raise HTTPException(
            status_code=403,
            detail="License expired",
        )

    return license


async def get_user_sites(
    user: User, db: AsyncSession
) -> List[MonitoredSite]:
    """Get all monitored sites for a user."""
    result = await db.execute(
        select(MonitoredSite)
        .where(MonitoredSite.user_id == user.id)
        .order_by(MonitoredSite.created_at)
    )
    return result.scalars().all()


# ===== Endpoints =====

@router.post("/sites", response_model=SiteResponse)
async def add_site(
    request: AddSiteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a site for monitoring."""
    license = await check_license_and_limits(current_user, db)

    # Check site limit
    existing_sites = await get_user_sites(current_user, db)
    if len(existing_sites) >= license.max_sites:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Site limit reached ({license.max_sites}). "
                f"Upgrade your plan."
            ),
        )

    # Check for duplicate
    for site in existing_sites:
        if site.domain == request.domain:
            raise HTTPException(
                status_code=409,
                detail=f"Site {request.domain} already added",
            )

    # Clean domain
    domain = request.domain.lower().strip()
    domain = domain.replace("http://", "").replace("https://", "")
    domain = domain.rstrip("/")

    # Default settings based on license features
    default_settings = {
        "check_availability": True,
        "check_ssl": license.features.get("ssl_check", True),
        "check_ui": license.features.get("ui_tests", False),
        "check_security": license.features.get("security_scan", False),
        "check_malware": license.features.get("malware_scan", False),
        "critical_pages": ["/"],
        "ui_elements": [
            {
                "name": "Buy Button",
                "selectors": [
                    "button.buy-btn",
                    ".buy-button",
                    "button:has-text('Buy')",
                    "a:has-text('Buy')",
                ],
                "action": "click",
                "critical": True,
            },
            {
                "name": "Call Button",
                "selectors": [
                    "a[href^='tel:']",
                    "a:has-text('Call')",
                    ".phone-link",
                ],
                "action": "exists",
                "critical": True,
            },
            {
                "name": "Callback Form",
                "selectors": [
                    "form.callback",
                    "form.feedback",
                    ".callback-form",
                    "[class*='callback']",
                ],
                "action": "form_check",
                "critical": True,
            },
            {
                "name": "Catalog",
                "selectors": [
                    "a[href*='catalog']",
                    "a:has-text('Catalog')",
                    "[class*='catalog']",
                ],
                "action": "navigate",
                "critical": True,
            },
            {
                "name": "Cart",
                "selectors": [
                    "a[href*='cart']",
                    "a[href*='basket']",
                    ".cart-icon",
                ],
                "action": "navigate",
                "critical": True,
            },
        ],
    }

    if request.settings:
        default_settings.update(request.settings)

    site = MonitoredSite(
        user_id=current_user.id,
        domain=domain,
        name=request.name or domain,
        is_active=True,
        check_interval=request.check_interval,
        settings=default_settings,
        current_status={},
    )

    db.add(site)
    await db.commit()
    await db.refresh(site)

    return SiteResponse(
        id=site.id,
        domain=site.domain,
        name=site.name,
        is_active=site.is_active,
        check_interval=site.check_interval,
        settings=site.settings,
        current_status=site.current_status or {},
        last_check_at=site.last_check_at,
        created_at=site.created_at,
    )


@router.get("/sites", response_model=List[SiteResponse])
async def list_sites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get list of all monitored sites."""
    await check_license_and_limits(current_user, db)
    sites = await get_user_sites(current_user, db)

    return [
        SiteResponse(
            id=site.id,
            domain=site.domain,
            name=site.name,
            is_active=site.is_active,
            check_interval=site.check_interval,
            settings=site.settings or {},
            current_status=site.current_status or {},
            last_check_at=site.last_check_at,
            created_at=site.created_at,
        )
        for site in sites
    ]


@router.put("/sites/{site_id}", response_model=SiteResponse)
async def update_site(
    site_id: int,
    request: UpdateSiteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update site monitoring settings."""
    license = await check_license_and_limits(current_user, db)

    result = await db.execute(
        select(MonitoredSite)
        .where(MonitoredSite.id == site_id)
        .where(MonitoredSite.user_id == current_user.id)
    )
    site = result.scalar_one_or_none()

    if not site:
        raise HTTPException(404, "Site not found")

    if request.name is not None:
        site.name = request.name

    if request.check_interval is not None:
        if not license.features.get("custom_intervals", False):
            raise HTTPException(
                403,
                "Custom intervals not available in your plan",
            )
        site.check_interval = request.check_interval

    if request.is_active is not None:
        site.is_active = request.is_active

    if request.settings is not None:
        current_settings = site.settings or {}
        current_settings.update(request.settings)
        site.settings = current_settings

    await db.commit()
    await db.refresh(site)

    return SiteResponse(
        id=site.id,
        domain=site.domain,
        name=site.name,
        is_active=site.is_active,
        check_interval=site.check_interval,
        settings=site.settings or {},
        current_status=site.current_status or {},
        last_check_at=site.last_check_at,
        created_at=site.created_at,
    )


@router.delete("/sites/{site_id}")
async def delete_site(
    site_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a monitored site."""
    result = await db.execute(
        select(MonitoredSite)
        .where(MonitoredSite.id == site_id)
        .where(MonitoredSite.user_id == current_user.id)
    )
    site = result.scalar_one_or_none()

    if not site:
        raise HTTPException(404, "Site not found")

    await db.delete(site)
    await db.commit()

    return {"message": f"Site {site.domain} deleted"}


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get monitoring dashboard data."""
    await check_license_and_limits(current_user, db)
    sites = await get_user_sites(current_user, db)

    sites_response = []
    sites_ok = 0
    sites_with_issues = 0
    ssl_expiring = 0
    total_security = 0

    for site in sites:
        status = site.current_status or {}
        severity = status.get("overall_severity", "ok")

        if severity == "ok":
            sites_ok += 1
        else:
            sites_with_issues += 1

        ssl_days = status.get("ssl_days_left")
        if ssl_days is not None and ssl_days <= 30:
            ssl_expiring += 1

        sec_score = status.get("security_score", 0)
        total_security += sec_score

        sites_response.append(SiteStatusResponse(
            domain=site.domain,
            is_available=status.get("is_available", False),
            http_status=(
                status.get("https_status") or status.get("http_status")
            ),
            response_time_ms=status.get("response_time_ms"),
            ssl_valid=status.get("ssl", {}).get("is_valid"),
            ssl_days_left=ssl_days,
            security_score=sec_score,
            malware_detected=status.get("malware_detected", False),
            ui_elements_ok=status.get("ui_ok_count"),
            ui_elements_total=status.get("ui_total_count"),
            overall_severity=severity,
            issues=status.get("issues", []),
            last_check_at=site.last_check_at,
            sitemap_tree=status.get("sitemap_tree"),
        ))

    # Sort: problematic sites first
    severity_order = {
        "critical": 0, "high": 1, "medium": 2, "low": 3, "ok": 4,
    }
    sites_response.sort(
        key=lambda s: severity_order.get(s.overall_severity, 4)
    )

    total = len(sites)
    avg_security = round(total_security / total, 1) if total > 0 else 0

    return DashboardResponse(
        total_sites=total,
        sites_ok=sites_ok,
        sites_with_issues=sites_with_issues,
        ssl_expiring=ssl_expiring,
        avg_security_score=avg_security,
        sites=sites_response,
        last_updated=datetime.utcnow(),
    )


@router.get("/sites/{site_id}/status", response_model=SiteStatusResponse)
async def get_site_status(
    site_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed status for a specific site."""
    result = await db.execute(
        select(MonitoredSite)
        .where(MonitoredSite.id == site_id)
        .where(MonitoredSite.user_id == current_user.id)
    )
    site = result.scalar_one_or_none()

    if not site:
        raise HTTPException(404, "Site not found")

    status = site.current_status or {}

    return SiteStatusResponse(
        domain=site.domain,
        is_available=status.get("is_available", False),
        http_status=(
            status.get("https_status") or status.get("http_status")
        ),
        response_time_ms=status.get("response_time_ms"),
        ssl_valid=status.get("ssl", {}).get("is_valid"),
        ssl_days_left=status.get("ssl_days_left"),
        security_score=status.get("security_score", 0),
        malware_detected=status.get("malware_detected", False),
        ui_elements_ok=status.get("ui_ok_count"),
        ui_elements_total=status.get("ui_total_count"),
        overall_severity=status.get("overall_severity", "unknown"),
        issues=status.get("issues", []),
        last_check_at=site.last_check_at,
        sitemap_tree=status.get("sitemap_tree"),
    )


@router.post("/sites/{site_id}/check-now")
async def trigger_check(
    site_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger an immediate check for a site."""
    result = await db.execute(
        select(MonitoredSite)
        .where(MonitoredSite.id == site_id)
        .where(MonitoredSite.user_id == current_user.id)
    )
    site = result.scalar_one_or_none()

    if not site:
        raise HTTPException(404, "Site not found")

    # In production this would trigger the scheduler.
    # For now, return acknowledgement.
    return {"message": f"Check for {site.domain} triggered"}
