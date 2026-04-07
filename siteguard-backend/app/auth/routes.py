"""
Authentication routes: registration, login, and current user info.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.jwt_handler import create_access_token, get_current_user
from app.licensing.models import User
from app.licensing.key_generator import LicenseKeyGenerator
from app.licensing.models import LicensePlan

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ===== Pydantic schemas =====

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=255)
    company_name: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=50)


class RegisterResponse(BaseModel):
    id: int
    email: str
    full_name: str
    company_name: str
    message: str
    trial_license_key: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    full_name: str


class UserInfoResponse(BaseModel):
    id: int
    email: str
    full_name: str
    company_name: str
    phone: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    notification_settings: dict


# ===== Endpoints =====

@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user account.
    Automatically creates a 14-day trial license.
    """
    # Check if email already registered
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create user
    hashed_password = pwd_context.hash(request.password)
    user = User(
        email=request.email,
        password_hash=hashed_password,
        full_name=request.full_name,
        company_name=request.company_name,
        phone=request.phone,
        is_active=True,
        is_admin=False,
        notification_settings={
            "telegram_enabled": False,
            "telegram_chat_id": None,
            "email_enabled": True,
            "sms_enabled": False,
            "sms_phone": None,
            "push_enabled": True,
        },
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Create trial license
    trial_license = await LicenseKeyGenerator.create_license(
        db=db,
        user_id=user.id,
        plan=LicensePlan.TRIAL,
    )

    return RegisterResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name or "",
        company_name=user.company_name or "",
        message="Registration successful. Trial license activated for 14 days.",
        trial_license_key=trial_license.license_key,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate user and return a JWT access token.
    """
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()

    if not user or not pwd_context.verify(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    access_token = create_access_token(data={"sub": str(user.id)})

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name or "",
    )


@router.get("/me", response_model=UserInfoResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    Get current authenticated user's profile information.
    """
    return UserInfoResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name or "",
        company_name=current_user.company_name or "",
        phone=current_user.phone or "",
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
        notification_settings=current_user.notification_settings or {},
    )
