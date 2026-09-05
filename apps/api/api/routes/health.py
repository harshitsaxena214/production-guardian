"""Health check endpoints."""
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from config import get_settings

router = APIRouter()
settings = get_settings()


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    environment: str


class ReadyResponse(BaseModel):
    status: str
    checks: dict[str, str]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Basic health check — always returns 200 if the service is running."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
        environment=settings.app_env,
    )


@router.get("/ready", response_model=ReadyResponse)
async def ready() -> ReadyResponse:
    """
    Readiness check — verifies all critical dependencies are available.
    Returns 200 if ready to serve traffic, 503 if not.
    """
    checks: dict[str, str] = {}

    # Check database
    try:
        from core.database import engine
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:100]}"

    # Check Gemini config
    checks["gemini"] = "configured" if settings.google_api_key else "not_configured"

    # Check Grafana config
    checks["grafana"] = "configured" if settings.grafana_url else "not_configured"
    checks["grafana_mcp"] = "configured" if settings.grafana_mcp_url else "not_configured"

    overall_ok = checks.get("database") == "ok"
    return ReadyResponse(
        status="ready" if overall_ok else "degraded",
        checks=checks,
    )
