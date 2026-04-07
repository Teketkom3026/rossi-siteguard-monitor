"""
Application configuration using pydantic-settings.
All environment variables are loaded here.
"""
import os
import secrets
from typing import List, Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Main application settings loaded from environment variables."""

    # --- Application ---
    APP_NAME: str = "SiteGuard Monitor API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # --- Security ---
    SECRET_KEY: str = os.environ.get("SECRET_KEY", secrets.token_hex(32))
    LICENSE_SECRET_KEY: str = os.environ.get(
        "LICENSE_SECRET_KEY", secrets.token_hex(32)
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    ALGORITHM: str = "HS256"

    # --- Database ---
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/siteguard",
        description="PostgreSQL async connection string",
    )

    # --- Redis ---
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for caching and rate limiting",
    )

    # --- CORS ---
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "https://siteguard.pro",
    ]

    # --- SMTP / Email ---
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@siteguard.pro"
    SMTP_FROM_NAME: str = "SiteGuard Monitor"
    SMTP_USE_TLS: bool = True

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # --- SMS ---
    SMS_API_KEY: str = ""
    SMS_API_URL: str = "https://sms.ru/sms/send"
    SMS_FROM: str = "SiteGuard"

    # --- VirusTotal ---
    VIRUSTOTAL_API_KEY: str = ""

    # --- Firebase ---
    FIREBASE_CREDENTIALS_PATH: str = ""

    # --- YooKassa Payment ---
    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""

    # --- Stripe Payment ---
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # --- Frontend ---
    FRONTEND_URL: str = "https://siteguard.pro"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
