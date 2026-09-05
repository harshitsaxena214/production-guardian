"""Remediation approval and simulation routes."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from core.database import get_db
from models.database import Incident, IncidentStatus, RemediationAction, RemediationStatus
from schemas.remediation import (
    ApproveRemediationRequest,
    RejectRemediationRequest,
    RemediationExecutionResponse,
    RemediationSchema,
    SimulateRemediationRequest,
    VerificationResult,
)
from simulator.engine import get_simulator

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("/remediation/{incident_id}", response_model=list[RemediationSchema])
async def get_remediation_actions(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[RemediationSchema]:
    """Get remediation actions for an incident."""
    result = await db.execute(
        select(RemediationAction)
        .where(RemediationAction.incident_id == incident_id)
        .order_by(RemediationAction.created_at)
    )
    actions = result.scalars().all()
    return [RemediationSchema.model_validate(a) for a in actions]


@router.post("/remediation/approve", response_model=RemediationSchema)
async def approve_remediation(
    request: ApproveRemediationRequest,
    db: AsyncSession = Depends(get_db),
) -> RemediationSchema:
    """
    Approve a remediation action for execution.

    This records human approval. The simulated execution must be
    triggered separately via POST /remediation/simulate.
    """
    result = await db.execute(
        select(RemediationAction).where(RemediationAction.id == request.remediation_id)
    )
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation action {request.remediation_id} not found",
        )

    if action.status != RemediationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Action is in state {action.status}, cannot approve",
        )

    action.status = RemediationStatus.APPROVED
    action.approved_by = request.approved_by
    action.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(action)

    logger.info(
        "remediation.approved",
        action_id=action.id,
        approved_by=request.approved_by,
    )

    return RemediationSchema.model_validate(action)


@router.post("/remediation/reject", response_model=RemediationSchema)
async def reject_remediation(
    request: RejectRemediationRequest,
    db: AsyncSession = Depends(get_db),
) -> RemediationSchema:
    """Reject a remediation action."""
    result = await db.execute(
        select(RemediationAction).where(RemediationAction.id == request.remediation_id)
    )
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation action {request.remediation_id} not found",
        )

    action.status = RemediationStatus.REJECTED
    details = dict(action.details or {})
    details["rejection_reason"] = request.reason
    action.details = details
    await db.commit()
    await db.refresh(action)

    return RemediationSchema.model_validate(action)


@router.post("/remediation/simulate", response_model=RemediationExecutionResponse)
async def simulate_remediation(
    request: SimulateRemediationRequest,
    db: AsyncSession = Depends(get_db),
) -> RemediationExecutionResponse:
    """
    Execute simulated remediation.

    IMPORTANT: This is a simulated operation for the demo.
    No real production systems are modified.

    When approved remediation is simulated:
    1. Simulator transitions to REMEDIATING state
    2. Telemetry begins recovering (pushed to Grafana)
    3. Verification agent checks recovery metrics
    4. Incident status updated to RESOLVED
    """
    result = await db.execute(
        select(RemediationAction).where(RemediationAction.id == request.remediation_id)
    )
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation action {request.remediation_id} not found",
        )

    if action.status != RemediationStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Action must be APPROVED before simulation. Current status: {action.status}",
        )

    # Get the incident
    incident_result = await db.execute(
        select(Incident).where(Incident.id == action.incident_id)
    )
    incident = incident_result.scalar_one_or_none()

    # Start simulated remediation
    sim = get_simulator()
    sim.begin_remediation()

    action.status = RemediationStatus.EXECUTING
    action.executed_at = datetime.now(timezone.utc)
    await db.commit()

    # Simulate a brief delay then complete
    # In a real system this would be async and poll for completion
    # For demo: complete immediately (telemetry recovers over time via simulator)
    sim.complete_remediation()

    # Get post-remediation metrics
    recovered_metrics = sim.get_current_metrics()

    # Verify recovery
    verification = _verify_recovery(
        incident=incident,
        action=action,
        recovered_metrics=recovered_metrics,
    )

    # Update records
    action.status = RemediationStatus.COMPLETED
    action.verification_result = verification.model_dump()
    await db.commit()

    if incident:
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.now(timezone.utc)
        await db.commit()

    telemetry_changes = {
        "storage_utilization": {
            "before": "96.5%",
            "after": f"{recovered_metrics.get('storage_utilization', 61.0):.1f}%",
        },
        "disk_write_latency_ms": {
            "before": "136ms",
            "after": f"{recovered_metrics.get('disk_write_latency_ms', 38.0):.1f}ms",
        },
        "ingest_throughput_gbps": {
            "before": "0.68 GB/s",
            "after": f"{recovered_metrics.get('ingest_throughput_gbps', 1.92):.2f} GB/s",
        },
        "upload_queue_depth": {
            "before": "1240 frames",
            "after": f"{recovered_metrics.get('upload_queue_depth', 22.0):.0f} frames",
        },
    }

    logger.info(
        "remediation.simulation_complete",
        action_id=action.id,
        verification_passed=verification.verification_passed,
    )

    return RemediationExecutionResponse(
        remediation_id=action.id,
        status="COMPLETED",
        simulation_note=(
            "⚠️ SIMULATED REMEDIATION: This is a demonstration of what the remediation "
            "would accomplish. No real production systems were modified. "
            "Telemetry recovery is reflected in Grafana."
        ),
        telemetry_changes=telemetry_changes,
        verification=verification,
        message="Simulated remediation complete. Production risk reduced from CRITICAL to LOW.",
    )


def _verify_recovery(
    incident: Incident | None,
    action: RemediationAction,
    recovered_metrics: dict,
) -> VerificationResult:
    """Verify that recovery metrics meet expectations."""
    storage_after = recovered_metrics.get("storage_utilization", 61.0)
    latency_after = recovered_metrics.get("disk_write_latency_ms", 38.0)
    throughput_after = recovered_metrics.get("ingest_throughput_gbps", 1.92)
    queue_after = recovered_metrics.get("upload_queue_depth", 22.0)

    # Check if recovery targets are met
    storage_ok = storage_after < 75.0
    latency_ok = latency_after < 80.0
    throughput_ok = throughput_after > 1.5
    queue_ok = queue_after < 200

    verification_passed = all([storage_ok, latency_ok, throughput_ok, queue_ok])

    delay_before = incident.estimated_delay_minutes if incident else 47.0
    delay_avoided = delay_before if verification_passed else 0

    return VerificationResult(
        storage_utilization_after=round(storage_after, 1),
        write_latency_after_ms=round(latency_after, 1),
        ingest_throughput_after_gbps=round(throughput_after, 3),
        transfer_queue_after=int(queue_after),
        production_risk_before="CRITICAL",
        production_risk_after="LOW" if verification_passed else "MEDIUM",
        scene_status="ON TRACK" if verification_passed else "AT RISK",
        delay_avoided_minutes=round(delay_avoided, 1) if delay_avoided else None,
        verification_passed=verification_passed,
        summary=(
            "Recovery verified. Ingest throughput restored to above target rate. "
            "Storage utilization reduced below critical threshold. "
            "Scene 42 editorial deadline is back on track."
            if verification_passed
            else "Partial recovery. Some metrics still elevated. Continue monitoring."
        ),
    )
