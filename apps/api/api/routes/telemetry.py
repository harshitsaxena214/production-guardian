"""Telemetry and Grafana integration status routes."""
from fastapi import APIRouter
from pydantic import BaseModel

from integrations.grafana_mcp.client import get_grafana_mcp_client
from simulator.engine import get_simulator
from simulator.generator import MetricGenerator

router = APIRouter()


class TelemetryStatusResponse(BaseModel):
    """Current telemetry snapshot for the UI."""
    simulator_state: str
    scenario: str | None
    incident_active: bool
    metrics: dict
    health_scores: dict
    data_source: str


class GrafanaStatusResponse(BaseModel):
    """Grafana integration status."""
    mcp_available: bool
    grafana_url: str
    mcp_url: str
    message: str | None = None
    tools_available: list[str] = []


@router.get("/telemetry/status", response_model=TelemetryStatusResponse)
async def get_telemetry_status() -> TelemetryStatusResponse:
    """
    Get current telemetry snapshot.

    Returns current metric values from the simulator.
    These are the same values being pushed to Grafana Cloud.
    """
    sim = get_simulator()
    metrics = sim.get_current_metrics()

    gen = MetricGenerator()
    health_scores = gen.calculate_system_health(metrics)

    return TelemetryStatusResponse(
        simulator_state=sim.state.value,
        scenario=sim.active_scenario_name,
        incident_active=sim.is_incident_active,
        metrics=metrics,
        health_scores=health_scores,
        data_source="DEMO_SIMULATOR",
    )


@router.get("/telemetry/history")
async def get_telemetry_history(
    metric: str = "storage_utilization",
    points: int = 30,
) -> dict:
    """
    Get simulated time-series history for a metric.

    Generates realistic historical data that matches the current simulator state.
    In production, this would query Grafana Prometheus.
    """
    import time
    import random

    sim = get_simulator()
    metrics = sim.get_current_metrics()
    current_val = metrics.get(metric, 0)

    from simulator.generator import BASELINE_METRICS
    baseline = BASELINE_METRICS.get(metric, {}).get("value", current_val)
    noise = BASELINE_METRICS.get(metric, {}).get("noise", current_val * 0.02)

    history = []
    now = time.time()

    for i in range(points):
        t = now - (points - i) * 60  # One point per minute going back

        # Progress from baseline to current value
        progress = i / max(points - 1, 1)
        if sim.is_incident_active:
            val = baseline + (current_val - baseline) * min(progress * 1.5, 1.0)
        else:
            val = current_val

        val += random.gauss(0, noise * 0.3)
        history.append({
            "timestamp": t,
            "value": round(max(0, val), 3),
        })

    return {
        "metric": metric,
        "data_source": "DEMO_SIMULATOR",
        "history": history,
        "current_value": current_val,
    }


@router.get("/integrations/grafana/status", response_model=GrafanaStatusResponse)
async def get_grafana_status() -> GrafanaStatusResponse:
    """
    Check Grafana MCP integration status.

    Makes an actual health check to the Grafana MCP server.
    Returns connection status and available tools.
    """
    from config import get_settings
    settings = get_settings()

    client = get_grafana_mcp_client()
    health = await client.check_health()

    # If available, list tools
    tools = []
    if health.get("available"):
        try:
            tool_list = await client.list_tools()
            tools = [t.get("name", "") for t in tool_list if t.get("name")]
        except Exception:
            pass

    return GrafanaStatusResponse(
        mcp_available=health.get("available", False),
        grafana_url=settings.grafana_url or "not configured",
        mcp_url=settings.grafana_mcp_url or "not configured",
        message=health.get("message"),
        tools_available=tools,
    )
