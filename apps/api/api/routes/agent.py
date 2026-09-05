"""
Agent investigation API routes with SSE streaming.

The investigation endpoint streams agent events in real time using
Server-Sent Events (SSE). Each event corresponds to an actual agent
operation (tool call, analysis step, result).
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.orchestrator import OrchestratorAgent
from core.database import get_db
from models.database import AgentRun, AgentRunStatus, Incident, IncidentStatus, RemediationAction
from schemas.agent import InvestigateRequest, WhatIfRequest, WhatIfResponse

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("/agent/investigate")
async def investigate_incident(
    request: InvestigateRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Start an AI investigation of an incident.

    Streams SSE events as the agent works through:
    - Connecting to Grafana MCP
    - Querying infrastructure metrics
    - Analyzing evidence with Gemini
    - Calculating production impact
    - Generating remediation recommendations

    Events format: text/event-stream with JSON data.
    """
    # Validate incident exists
    inc_result = await db.execute(
        select(Incident).where(Incident.id == request.incident_id)
    )
    incident = inc_result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {request.incident_id} not found",
        )

    # Create agent run record
    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=run_id,
        incident_id=incident.id,
        run_type="INVESTIGATION",
        status=AgentRunStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    db.add(agent_run)
    await db.commit()

    # Update incident status
    incident.status = IncidentStatus.INVESTIGATING
    await db.commit()

    async def event_stream() -> AsyncGenerator[str, None]:
        """Generate SSE events from agent investigation."""
        orchestrator = OrchestratorAgent()
        all_events = []
        final_result = None

        try:
            async for event in orchestrator.investigate(
                incident_id=incident.id,
                scenario_type=incident.scenario_type or "STORAGE_SATURATION",
                run_id=run_id,
                db_session=db,
            ):
                all_events.append(event)

                # Capture final result
                if event.get("event_type") == "INVESTIGATION_RESULT":
                    final_result = event.get("data", {}).get("result", {})

                # Stream event to client
                event_data = json.dumps(event, default=str)
                yield f"data: {event_data}\n\n"
                await asyncio.sleep(0)  # Yield control for async

            # Persist results
            if final_result:
                await _persist_investigation_result(
                    incident=incident,
                    agent_run_id=run_id,
                    result=final_result,
                    events=all_events,
                    db=db,
                )

            # Signal completion
            yield f"data: {json.dumps({'event_type': 'DONE', 'message': 'Investigation complete'})}\n\n"

        except Exception as e:
            logger.error("agent.investigation_failed", run_id=run_id, error=str(e))

            # Update agent run to failed
            try:
                run_result = await db.execute(
                    select(AgentRun).where(AgentRun.id == run_id)
                )
                run = run_result.scalar_one_or_none()
                if run:
                    run.status = AgentRunStatus.FAILED
                    run.error_message = str(e)
                    run.completed_at = datetime.now(timezone.utc)
                    await db.commit()
            except Exception:
                pass

            error_event = json.dumps({
                "event_type": "ERROR",
                "message": f"Investigation failed: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            yield f"data: {error_event}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/agent/runs/{run_id}")
async def get_agent_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the status and results of an agent run."""
    result = await db.execute(
        select(AgentRun).where(AgentRun.id == run_id)
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent run {run_id} not found",
        )

    return {
        "id": run.id,
        "incident_id": run.incident_id,
        "run_type": run.run_type,
        "status": run.status,
        "events": run.events,
        "result": run.result,
        "error_message": run.error_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


@router.post("/agent/impact", response_model=WhatIfResponse)
async def what_if_nothing(
    request: WhatIfRequest,
    db: AsyncSession = Depends(get_db),
) -> WhatIfResponse:
    """
    'What if we do nothing?' analysis.

    Projects the downstream consequences if the incident is not remediated.
    Uses current telemetry + production context.
    """
    inc_result = await db.execute(
        select(Incident).where(Incident.id == request.incident_id)
    )
    incident = inc_result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {request.incident_id} not found",
        )

    impact = incident.production_impact or {}
    delay_min = incident.estimated_delay_minutes or impact.get("projected_delay_minutes", 47)

    projections = [
        {
            "time_minutes": 18,
            "event": "Scene 42 ingestion failure risk",
            "severity": "HIGH",
            "description": "At current degraded rate, ingest will fall critically behind",
        },
        {
            "time_minutes": round(delay_min, 0),
            "event": "Editorial delivery delay",
            "severity": "CRITICAL",
            "description": f"Editorial deadline missed by ~{round(delay_min, 0):.0f} minutes",
        },
        {
            "time_minutes": round(delay_min * 1.5, 0),
            "event": "Scene 43 assembly at risk",
            "severity": "HIGH",
            "description": "Dependent scenes cannot begin assembly without Scene 42 footage",
        },
        {
            "time_minutes": round(delay_min * 2.5, 0),
            "event": "Daily delivery package failure",
            "severity": "CRITICAL",
            "description": "End-of-day delivery to post-production will be missed",
        },
    ]

    return WhatIfResponse(
        incident_id=request.incident_id,
        projections=projections,
        immediate_risk="Scene 42 footage ingestion at risk within 18 minutes",
        downstream_risks=[
            "Scene 43 and 44 dependent on Scene 42 completion",
            "Editorial team blocked from timeline assembly",
            "Daily delivery package at risk",
            "Post-production schedule disruption",
        ],
        probability_of_production_failure=0.87,
        analysis=(
            f"Without intervention, the current ingest degradation will result in a "
            f"~{round(delay_min, 0):.0f}-minute editorial delay. "
            "Scene 43 and 44 (dependent on Scene 42) will be blocked from assembly. "
            "The daily delivery package is unlikely to be completed on time."
        ),
    )


async def _persist_investigation_result(
    incident: Incident,
    agent_run_id: str,
    result: dict,
    events: list,
    db: AsyncSession,
) -> None:
    """Persist agent investigation results to database."""
    try:
        # Update agent run
        run_result = await db.execute(
            select(AgentRun).where(AgentRun.id == agent_run_id)
        )
        run = run_result.scalar_one_or_none()
        if run:
            run.status = AgentRunStatus.COMPLETED
            run.result = result
            run.events = events
            run.completed_at = datetime.now(timezone.utc)

        # Update incident with investigation findings
        incident.status = IncidentStatus.INVESTIGATING
        incident.root_cause = result.get("root_cause")
        incident.confidence = result.get("confidence")
        incident.evidence = result.get("evidence", [])
        incident.affected_systems = result.get("affected_systems", [])
        incident.affected_scene_numbers = result.get("affected_scene_numbers", [])
        incident.production_impact = result.get("production_impact", {})
        incident.estimated_delay_minutes = result.get("estimated_delay_minutes")
        incident.deadline_at_risk = result.get("deadline_at_risk", False)
        incident.investigated_at = datetime.now(timezone.utc)

        # Create remediation actions
        for action_data in result.get("recommended_actions", []):
            action = RemediationAction(
                id=str(uuid.uuid4()),
                incident_id=incident.id,
                action=action_data.get("action", ""),
                action_type=action_data.get("action_type", "SIMULATED"),
                risk_level=action_data.get("risk_level", "LOW"),
                expected_benefit=action_data.get("expected_benefit", "HIGH"),
                expected_recovery_minutes=action_data.get("expected_recovery_minutes", 15),
                confidence=action_data.get("confidence", 0.85),
                details=action_data.get("details", {}),
            )
            db.add(action)

        await db.commit()

    except Exception as e:
        logger.error("agent.persist_failed", error=str(e), exc_info=True)
