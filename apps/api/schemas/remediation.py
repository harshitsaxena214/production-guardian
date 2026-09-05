"""Pydantic schemas for Remediation API."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RecommendedAction(BaseModel):
    """A single recommended remediation action."""
    id: str
    action: str
    action_type: str
    risk_level: str
    expected_benefit: str
    expected_recovery_minutes: int
    confidence: float
    details: dict[str, Any] = {}


class RemediationSchema(BaseModel):
    """Remediation action for API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_id: str
    action: str
    action_type: str
    risk_level: str
    expected_benefit: str
    expected_recovery_minutes: int
    confidence: float
    details: dict[str, Any]
    status: str
    approved_by: str | None
    approved_at: datetime | None
    executed_at: datetime | None
    verification_result: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ApproveRemediationRequest(BaseModel):
    """Request body for approving a remediation action."""
    remediation_id: str = Field(..., description="ID of the remediation action to approve")
    approved_by: str = Field(default="OPERATOR", description="Name/role of the approver")


class RejectRemediationRequest(BaseModel):
    """Request body for rejecting a remediation action."""
    remediation_id: str
    reason: str | None = None


class SimulateRemediationRequest(BaseModel):
    """Request body for executing simulated remediation."""
    remediation_id: str


class VerificationResult(BaseModel):
    """Result of post-remediation verification."""
    storage_utilization_after: float | None
    write_latency_after_ms: float | None
    ingest_throughput_after_gbps: float | None
    transfer_queue_after: int | None
    production_risk_before: str
    production_risk_after: str
    scene_status: str
    delay_avoided_minutes: float | None
    verification_passed: bool
    summary: str


class RemediationExecutionResponse(BaseModel):
    """Response after simulated remediation execution."""
    remediation_id: str
    status: str
    simulation_note: str
    telemetry_changes: dict[str, Any]
    verification: VerificationResult | None
    message: str
