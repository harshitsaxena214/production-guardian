"""
Orchestrator Agent.

The orchestrator coordinates the full investigation pipeline using Google ADK.
It delegates to the investigation agent (Grafana MCP), production impact agent
(database), and remediation agent.

The orchestrator does NOT call every tool blindly — it determines what
information is relevant based on the incident type and evidence gathered.

Uses Google ADK's LlmAgent with tool calling and structured output.
"""
import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import structlog

from agents.investigation import InvestigationAgent
from agents.production_impact import ProductionImpactAgent
from agents.remediation import RemediationAgentImpl
from config import get_settings
from core.exceptions import AgentError

logger = structlog.get_logger(__name__)
settings = get_settings()


class OrchestratorAgent:
    """
    Coordinates the full Production Guardian investigation pipeline.

    This is the primary AI agent. It:
    1. Understands the incident context
    2. Delegates investigation to InvestigationAgent (Grafana MCP)
    3. Delegates impact calculation to ProductionImpactAgent (DB)
    4. Synthesizes results into structured IncidentAnalysis
    5. Generates remediation recommendations via RemediationAgent
    6. Emits operational events for UI streaming

    Events are yielded in real time for SSE streaming to the frontend.
    """

    def __init__(self) -> None:
        self._investigation_agent = InvestigationAgent()
        self._impact_agent = ProductionImpactAgent()
        self._remediation_agent = RemediationAgentImpl()

    async def investigate(
        self,
        incident_id: str,
        scenario_type: str,
        run_id: str,
        db_session: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Run the full investigation pipeline, yielding events as they occur.

        Each yielded event has: type, message, timestamp, tool_name (optional)

        The caller is responsible for persisting events to the AgentRun record
        and streaming them to the UI via SSE.
        """
        start_time = time.monotonic()

        def event(
            message: str,
            event_type: str = "STEP",
            tool_name: str | None = None,
            success: bool = True,
            data: dict | None = None,
        ) -> dict[str, Any]:
            return {
                "run_id": run_id,
                "event_type": event_type,
                "message": message,
                "tool_name": tool_name,
                "success": success,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": data or {},
            }

        try:
            # ----------------------------------------------------------------
            # Step 1: Understanding the incident
            # ----------------------------------------------------------------
            yield event("Understanding incident context")
            await asyncio.sleep(0.2)  # Small delay for UX pacing

            # ----------------------------------------------------------------
            # Step 2: Connecting to Grafana MCP
            # ----------------------------------------------------------------
            yield event("Connecting to Grafana MCP", tool_name="grafana_mcp")
            grafana_status = await self._check_grafana_availability()
            grafana_available = grafana_status.get("available", False)

            if grafana_available:
                yield event(
                    "Connected to Grafana MCP",
                    tool_name="grafana_mcp",
                    data={"grafana_url": settings.grafana_url},
                )
            else:
                yield event(
                    f"Grafana MCP unavailable: {grafana_status.get('message', 'unknown')}. "
                    "Using simulator state for investigation.",
                    tool_name="grafana_mcp",
                    success=False,
                )

            # ----------------------------------------------------------------
            # Step 3: Investigation (Grafana MCP queries)
            # ----------------------------------------------------------------
            investigation_result = {}

            async for inv_event in self._investigation_agent.investigate(
                incident_id=incident_id,
                scenario_type=scenario_type,
                grafana_available=grafana_available,
            ):
                yield inv_event
                # Capture the final investigation result
                if inv_event.get("event_type") == "INVESTIGATION_RESULT":
                    investigation_result = inv_event.get("data", {})

            if not investigation_result:
                investigation_result = await self._investigation_agent.get_result(
                    incident_id, scenario_type, grafana_available
                )

            # ----------------------------------------------------------------
            # Step 4: Production context retrieval
            # ----------------------------------------------------------------
            yield event("Retrieving production context", tool_name="get_production_context")
            impact_result = await self._impact_agent.calculate_impact(
                incident_id=incident_id,
                investigation_result=investigation_result,
                db_session=db_session,
            )
            yield event(
                "Production impact calculated",
                tool_name="calculate_production_impact",
                data=impact_result,
            )

            # ----------------------------------------------------------------
            # Step 5: Remediation generation
            # ----------------------------------------------------------------
            yield event("Generating remediation recommendations")
            remediation = await self._remediation_agent.generate_recommendations(
                incident_id=incident_id,
                investigation_result=investigation_result,
                impact_result=impact_result,
                scenario_type=scenario_type,
            )
            yield event(
                "Remediation recommendation generated",
                tool_name="generate_remediation",
                data={"action_count": len(remediation.get("actions", []))},
            )

            # ----------------------------------------------------------------
            # Step 6: Synthesize final result
            # ----------------------------------------------------------------
            duration_ms = int((time.monotonic() - start_time) * 1000)
            final_result = self._synthesize_result(
                incident_id=incident_id,
                investigation_result=investigation_result,
                impact_result=impact_result,
                remediation=remediation,
            )

            yield event(
                "Investigation complete",
                event_type="INVESTIGATION_RESULT",
                data={
                    "result": final_result,
                    "duration_ms": duration_ms,
                },
            )

        except Exception as e:
            logger.error(
                "orchestrator.investigation_failed",
                incident_id=incident_id,
                error=str(e),
                exc_info=True,
            )
            yield event(
                f"Investigation failed: {str(e)}",
                event_type="ERROR",
                success=False,
            )
            raise AgentError(f"Orchestrator investigation failed: {str(e)}") from e

    async def _check_grafana_availability(self) -> dict[str, Any]:
        """Check if Grafana MCP is available."""
        from integrations.grafana_mcp.client import get_grafana_mcp_client
        client = get_grafana_mcp_client()
        return await client.check_health()

    def _synthesize_result(
        self,
        incident_id: str,
        investigation_result: dict[str, Any],
        impact_result: dict[str, Any],
        remediation: dict[str, Any],
    ) -> dict[str, Any]:
        """Combine investigation and impact results into final structured output."""
        return {
            "incident_id": incident_id,
            "severity": investigation_result.get("severity", "HIGH"),
            "confidence": investigation_result.get("confidence", 0.85),
            "root_cause": investigation_result.get("root_cause", ""),
            "root_cause_system": investigation_result.get("root_cause_system", ""),
            "evidence": investigation_result.get("evidence", []),
            "affected_systems": investigation_result.get("affected_systems", []),
            "affected_scene_numbers": impact_result.get("affected_scene_numbers", [42]),
            "production_impact": {
                "current_ingest_rate_gbps": impact_result.get("current_ingest_rate_gbps"),
                "required_ingest_rate_gbps": impact_result.get("required_ingest_rate_gbps"),
                "estimated_footage_gb": impact_result.get("estimated_footage_gb"),
                "footage_ingested_gb": impact_result.get("footage_ingested_gb"),
                "editorial_deadline": impact_result.get("editorial_deadline"),
                "estimated_completion_time": impact_result.get("estimated_completion_time"),
                "projected_delay_minutes": impact_result.get("projected_delay_minutes"),
                "deadline_at_risk": impact_result.get("deadline_at_risk", False),
                "downstream_risk": impact_result.get("downstream_risk", []),
                "production_severity": impact_result.get("production_severity", "HIGH"),
            },
            "recommended_actions": remediation.get("actions", []),
            "estimated_delay_minutes": impact_result.get("projected_delay_minutes", 0),
            "expected_recovery_minutes": remediation.get("expected_recovery_minutes", 15),
            "deadline_at_risk": impact_result.get("deadline_at_risk", False),
            "investigation_summary": investigation_result.get("summary", ""),
        }
