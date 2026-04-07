"""
FastAPI application entry point.
Configures CORS, rate limiting, routers, and lifecycle events.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.database import init_db, close_db

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup
    logger.info("Starting SiteGuard Monitor API...")
    await init_db()
    logger.info("Database initialized.")
    yield
    # Shutdown
    logger.info("Shutting down SiteGuard Monitor API...")
    await close_db()
    logger.info("Database connection closed.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="SiteGuard Monitor -- 24/7 Website Monitoring API",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== Include routers =====

from app.auth.routes import router as auth_router
from app.licensing.routes import router as licensing_router
from app.monitoring.routes import router as monitoring_router
from app.payments.routes import router as payments_router

app.include_router(auth_router)
app.include_router(licensing_router)
app.include_router(monitoring_router)
app.include_router(payments_router)

# Admin and notifications routers are included when their route
# modules are populated. The __init__.py files are already created.
try:
    from app.admin.routes import router as admin_router
    app.include_router(admin_router)
except (ImportError, AttributeError):
    logger.debug("Admin routes not yet implemented, skipping.")

try:
    from app.notifications.routes import router as notifications_router
    app.include_router(notifications_router)
except (ImportError, AttributeError):
    logger.debug("Notification routes not yet implemented, skipping.")


# ===== Health check =====

@app.get("/api/health", tags=["health"])
async def health_check():
    """Health check endpoint. Returns service status."""
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/api/docs",
        "health": "/api/health",
    }
