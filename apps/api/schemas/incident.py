"""Pydantic schemas for Incident API."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from models.database import IncidentSeverity, IncidentStatus, ScenarioType


class EvidenceItem(BaseModel):
    """A single piece of evidence from the investigation."""
    metric: str
    current_value: str
    baseline_value: str | None = None
    change_pct: float | None = None
    status: str  # "ANOMALOUS" | "NORMAL"
    description: str


class ProductionImpactSchema(BaseModel):
    """Calculated production impact from an incident."""
    current_ingest_rate_gbps: float | None = None
    required_ingest_rate_gbps: float | None = None
    estimated_footage_gb: float | None = None
    footage_ingested_gb: float | None = None
    editorial_deadline: str | None = None
    estimated_completion_time: str | None = None
    projected_delay_minutes: float | None = None
    deadline_at_risk: bool = False
    affected_scene_number: int | None = None
    downstream_risk: list[str] = []
    production_severity: str = "LOW"


class IncidentSchema(BaseModel):
    """Complete incident data for API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    production_id: str
    title: str
    description: str
    severity: str
    status: str
    scenario_type: str | None
    root_cause: str | None
    confidence: float | None
    evidence: list[dict[str, Any]]
    affected_systems: list[str]
    affected_scene_numbers: list[int]
    production_impact: dict[str, Any]
    estimated_delay_minutes: float | None
    deadline_at_risk: bool
    started_at: datetime
    investigated_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class IncidentSummarySchema(BaseModel):
    """Compact incident info for list views."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    severity: str
    status: str
    scenario_type: str | None
    estimated_delay_minutes: float | None
    deadline_at_risk: bool
    started_at: datetime


class SimulateIncidentRequest(BaseModel):
    """Request body for incident simulation."""
    scenario: ScenarioType = Field(
        default=ScenarioType.STORAGE_SATURATION,
        description="The incident scenario to simulate",
    )
    production_id: str | None = Field(
        default=None,
        description="Production ID (defaults to NIGHTFALL)",
    )


class SimulateIncidentResponse(BaseModel):
    """Response after incident simulation starts."""
    incident_id: str
    scenario: str
    message: str
    status: str = "ACTIVE"


class ResetResponse(BaseModel):
    """Response after demo reset."""
    message: str
    reset_items: list[str]
