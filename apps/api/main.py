"""
Production Guardian — FastAPI Backend

AI-powered autonomous operations system for film production monitoring.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import agent, health, incidents, production, remediation, telemetry
from config import get_settings
from core.database import init_db
from core.logging import configure_logging

# Configure structured logging before anything else
configure_logging()
logger = structlog.get_logger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown."""
    logger.info(
        "production_guardian.startup",
        app_env=settings.app_env,
        gemini_model=settings.gemini_model,
        grafana_url=settings.grafana_url,
    )

    # Validate critical configuration
    _validate_configuration()

    # Initialize database connection pool
    await init_db()
    logger.info("production_guardian.database_ready")

    yield

    logger.info("production_guardian.shutdown")


def _validate_configuration() -> None:
    """Validate required configuration on startup. Warns but does not crash."""
    warnings = []

    if not settings.google_api_key:
        warnings.append("GOOGLE_API_KEY is not configured — Gemini agent will be unavailable")

    if not settings.grafana_url:
        warnings.append("GRAFANA_URL is not configured — Grafana integration will be unavailable")

    if not settings.grafana_service_account_token:
        warnings.append(
            "GRAFANA_SERVICE_ACCOUNT_TOKEN is not configured — Grafana queries will fail"
        )

    if not settings.grafana_mcp_url:
        warnings.append("GRAFANA_MCP_URL is not configured — MCP integration will be unavailable")

    if not settings.grafana_prometheus_remote_write_url:
        warnings.append(
            "GRAFANA_PROMETHEUS_REMOTE_WRITE_URL is not configured — "
            "Telemetry will not reach Grafana"
        )

    for warning in warnings:
        logger.warning("production_guardian.config_warning", message=warning)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Production Guardian API",
        description=(
            "AI-powered autonomous operations system for film and media production. "
            "Monitors infrastructure telemetry, investigates incidents via Grafana MCP, "
            "and predicts production impact using Google Gemini."
        ),
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS — allow frontend in development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url, "http://localhost:3000", "http://localhost:3001"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(production.router, prefix="/api", tags=["production"])
    app.include_router(incidents.router, prefix="/api", tags=["incidents"])
    app.include_router(agent.router, prefix="/api", tags=["agent"])
    app.include_router(remediation.router, prefix="/api", tags=["remediation"])
    app.include_router(telemetry.router, prefix="/api", tags=["telemetry"])

    return app


app = create_app()
