"""Pydantic schemas for Agent API (investigation, impact analysis)."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentEvent(BaseModel):
    """A single operational event from an agent run."""
    timestamp: datetime
    event_type: str  # "TOOL_CALL" | "REASONING" | "RESULT" | "ERROR"
    message: str
    tool_name: str | None = None
    success: bool | None = None
    duration_ms: int | None = None


class AgentRunSchema(BaseModel):
    """Agent run status and results."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_id: str | None
    run_type: str
    status: str
    events: list[dict[str, Any]]
    result: dict[str, Any]
    tool_calls: list[dict[str, Any]]
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None


class InvestigateRequest(BaseModel):
    """Request body for starting an agent investigation."""
    incident_id: str = Field(..., description="ID of the incident to investigate")


class IncidentAnalysisResult(BaseModel):
    """Structured output from the investigation agent."""
    incident_id: str
    severity: str
    confidence: float = Field(ge=0.0, le=1.0)
    root_cause: str
    root_cause_system: str
    evidence: list[dict[str, Any]]
    affected_systems: list[str]
    affected_scene_numbers: list[int]
    production_impact: dict[str, Any]
    recommended_actions: list[dict[str, Any]]
    estimated_delay_minutes: float
    expected_recovery_minutes: int
    deadline_at_risk: bool
    investigation_summary: str


class WhatIfRequest(BaseModel):
    """Request body for 'What if we do nothing?' analysis."""
    incident_id: str


class WhatIfResponse(BaseModel):
    """Projected consequences if no action is taken."""
    incident_id: str
    projections: list[dict[str, Any]]
    immediate_risk: str
    downstream_risks: list[str]
    probability_of_production_failure: float
    analysis: str


class StreamEvent(BaseModel):
    """Server-sent event for agent activity streaming."""
    type: str  # "event" | "result" | "error" | "done"
    data: dict[str, Any]
