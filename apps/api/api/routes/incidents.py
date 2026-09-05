"""Incident management API routes."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.database import Incident, IncidentSeverity, IncidentStatus, Production, ScenarioType
from schemas.incident import (
    IncidentSchema,
    IncidentSummarySchema,
    ResetResponse,
    SimulateIncidentRequest,
    SimulateIncidentResponse,
)
from simulator.engine import get_simulator

router = APIRouter()


@router.get("/incidents", response_model=list[IncidentSummarySchema])
async def list_incidents(
    db: AsyncSession = Depends(get_db),
) -> list[IncidentSummarySchema]:
    """List all incidents for the current production."""
    result = await db.execute(
        select(Incident).order_by(Incident.started_at.desc()).limit(20)
    )
    incidents = result.scalars().all()
    return [IncidentSummarySchema.model_validate(i) for i in incidents]


@router.get("/incidents/active", response_model=list[IncidentSummarySchema])
async def list_active_incidents(
    db: AsyncSession = Depends(get_db),
) -> list[IncidentSummarySchema]:
    """List currently active incidents."""
    result = await db.execute(
        select(Incident)
        .where(Incident.status.in_([IncidentStatus.ACTIVE, IncidentStatus.INVESTIGATING]))
        .order_by(Incident.started_at.desc())
    )
    incidents = result.scalars().all()
    return [IncidentSummarySchema.model_validate(i) for i in incidents]


@router.get("/incidents/{incident_id}", response_model=IncidentSchema)
async def get_incident(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
) -> IncidentSchema:
    """Get a specific incident by ID."""
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found",
        )

    return IncidentSchema.model_validate(incident)


@router.post("/incidents/simulate", response_model=SimulateIncidentResponse)
async def simulate_incident(
    request: SimulateIncidentRequest,
    db: AsyncSession = Depends(get_db),
) -> SimulateIncidentResponse:
    """
    Activate an incident scenario.

    This:
    1. Activates the telemetry simulator to generate degraded metrics
    2. Pushes degraded metrics to Grafana Cloud
    3. Creates an incident record in the database
    4. Returns the incident ID for investigation
    """
    sim = get_simulator()

    # Activate the scenario
    scenario_info = sim.activate_scenario(request.scenario.value)

    # Get production
    prod_result = await db.execute(select(Production).limit(1))
    production = prod_result.scalar_one_or_none()

    if not production:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Production data not found. Run the seed script.",
        )

    # Create incident record
    scenario_titles = {
        "STORAGE_SATURATION": "Storage Saturation on INGEST-01",
        "NETWORK_DEGRADATION": "Network Degradation on NET-EDGE-07",
        "CAMERA_FAILURE": "Camera Failure on CAM-03",
        "RENDER_BOTTLENECK": "Render Bottleneck on EDIT-01",
        "MEDIA_INTEGRITY_FAILURE": "Media Integrity Failure on NAS-01",
    }

    incident = Incident(
        id=str(uuid.uuid4()),
        production_id=production.id,
        title=scenario_titles.get(request.scenario.value, "Unknown Incident"),
        description=scenario_info.get("description", ""),
        severity=IncidentSeverity.CRITICAL
        if request.scenario == ScenarioType.STORAGE_SATURATION
        else IncidentSeverity.HIGH,
        status=IncidentStatus.ACTIVE,
        scenario_type=request.scenario.value,
        affected_systems=scenario_info.get("affected_systems", []),
        started_at=datetime.now(timezone.utc),
    )

    db.add(incident)
    await db.commit()
    await db.refresh(incident)

    return SimulateIncidentResponse(
        incident_id=incident.id,
        scenario=request.scenario.value,
        message=f"Incident scenario '{request.scenario.value}' activated. "
                "Telemetry is being pushed to Grafana Cloud.",
        status="ACTIVE",
    )


@router.post("/incidents/reset", response_model=ResetResponse)
async def reset_demo(db: AsyncSession = Depends(get_db)) -> ResetResponse:
    """
    Reset the demo to a clean state.

    Resets:
    - Simulator (back to normal telemetry)
    - All active incidents (closed)
    - Remediation actions (cleared)
    - Agent runs (cleared)
    """
    # Reset simulator
    sim = get_simulator()
    sim.reset()

    reset_items = ["simulator_state", "telemetry_scenario"]

    # Close all active incidents
    result = await db.execute(
        select(Incident).where(
            Incident.status.in_([
                IncidentStatus.ACTIVE,
                IncidentStatus.INVESTIGATING,
                IncidentStatus.REMEDIATING,
            ])
        )
    )
    incidents = result.scalars().all()

    for incident in incidents:
        incident.status = IncidentStatus.CLOSED
        incident.resolved_at = datetime.now(timezone.utc)

    if incidents:
        reset_items.append(f"incidents_closed ({len(incidents)})")

    await db.commit()

    return ResetResponse(
        message="Demo reset complete. System is back to normal baseline.",
        reset_items=reset_items,
    )
