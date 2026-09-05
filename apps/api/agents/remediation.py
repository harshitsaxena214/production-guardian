"""
Remediation Agent.

Generates safe, human-reviewable remediation recommendations using Gemini.
All recommended actions are SIMULATED — no real production systems are modified.

The agent produces specific, actionable recommendations with:
- Concrete action description
- Risk assessment
- Expected benefit
- Expected recovery time
- Confidence score

Human approval is required before simulation executes.
"""
import json
from typing import Any

import structlog

from config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# Scenario-specific remediation templates (used as Gemini context)
REMEDIATION_CONTEXT: dict[str, dict[str, Any]] = {
    "STORAGE_SATURATION": {
        "immediate_action": "Free disk space on INGEST-01 by removing completed proxy files",
        "target_utilization": 61.0,
        "expected_recovery_minutes": 11,
        "risk": "LOW",
        "benefit": "HIGH",
        "actions": [
            "Free 180 GB from completed proxy files on INGEST-01",
            "Move non-critical proxy data to archive storage (NAS-01 cold tier)",
            "Prioritize Scene 42 footage in ingest queue",
            "Pause non-critical background ingest jobs",
            "Re-evaluate ingest capacity in 5 minutes",
        ],
    },
    "NETWORK_DEGRADATION": {
        "immediate_action": "Failover to backup network path via NET-CORE-01",
        "expected_recovery_minutes": 8,
        "risk": "LOW",
        "benefit": "HIGH",
        "actions": [
            "Reroute upload traffic away from NET-EDGE-07",
            "Activate backup uplink on NET-CORE-01",
            "Reduce camera bitrates by 20% temporarily",
            "Prioritize Scene 42 uploads over proxy generation",
        ],
    },
    "CAMERA_FAILURE": {
        "immediate_action": "Bring CAM-03 offline for cooling, redistribute to CAM-01 and CAM-02",
        "expected_recovery_minutes": 20,
        "risk": "MEDIUM",
        "benefit": "HIGH",
        "actions": [
            "Take CAM-03 offline for thermal cooling",
            "Redistribute Scene 42 coverage to CAM-01 and CAM-02",
            "Increase CAM-01 and CAM-02 recording bitrate",
            "Alert DIT to verify footage integrity from CAM-03",
        ],
    },
    "RENDER_BOTTLENECK": {
        "immediate_action": "Offload render jobs to EDIT-02 and deprioritize proxy renders",
        "expected_recovery_minutes": 15,
        "risk": "LOW",
        "benefit": "MEDIUM",
        "actions": [
            "Redistribute render queue to EDIT-02",
            "Suspend low-priority proxy renders",
            "Prioritize Scene 42 editorial timeline",
            "Increase GPU memory allocation for active render jobs",
        ],
    },
    "MEDIA_INTEGRITY_FAILURE": {
        "immediate_action": "Isolate affected NAS-01 volume, verify checksums, restore from backup",
        "expected_recovery_minutes": 25,
        "risk": "HIGH",
        "benefit": "HIGH",
        "actions": [
            "Quarantine affected footage from NAS-01 corrupted sector",
            "Initiate checksum verification on unaffected segments",
            "Restore verified backup copies from MEDIA-STORE-01",
            "Alert editorial team about potentially affected footage",
            "Failover ingest to healthy NAS-01 volume",
        ],
    },
}


class RemediationAgentImpl:
    """Generates remediation recommendations using Gemini + domain context."""

    async def generate_recommendations(
        self,
        incident_id: str,
        investigation_result: dict[str, Any],
        impact_result: dict[str, Any],
        scenario_type: str,
    ) -> dict[str, Any]:
        """
        Generate remediation recommendations.

        Uses Gemini when available to generate contextually relevant recommendations.
        Falls back to scenario-specific templates when Gemini is unavailable.
        """
        context = REMEDIATION_CONTEXT.get(scenario_type, REMEDIATION_CONTEXT["STORAGE_SATURATION"])

        if settings.google_api_key:
            try:
                return await self._generate_with_gemini(
                    scenario_type=scenario_type,
                    investigation_result=investigation_result,
                    impact_result=impact_result,
                    context=context,
                )
            except Exception as e:
                logger.warning(
                    "remediation_agent.gemini_failed",
                    error=str(e),
                    fallback="template",
                )

        return self._template_recommendations(scenario_type, context, impact_result)

    async def _generate_with_gemini(
        self,
        scenario_type: str,
        investigation_result: dict[str, Any],
        impact_result: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate recommendations using Gemini."""
        import asyncio
        import google.generativeai as genai

        genai.configure(api_key=settings.google_api_key)
        model = genai.GenerativeModel(model_name=settings.gemini_model)

        delay_min = impact_result.get("projected_delay_minutes", 0)
        deadline_at_risk = impact_result.get("deadline_at_risk", False)
        current_rate = impact_result.get("current_ingest_rate_gbps", 0)
        required_rate = impact_result.get("required_ingest_rate_gbps", 1.85)

        prompt = f"""You are generating remediation recommendations for a film production incident.

INCIDENT:
- Type: {scenario_type}
- Root cause: {investigation_result.get('root_cause', 'Unknown')}
- Affected systems: {investigation_result.get('affected_systems', [])}
- Confidence: {investigation_result.get('confidence', 0.85):.0%}

PRODUCTION IMPACT:
- Scene 42 (CRITICAL) — 680 GB estimated footage
- Editorial deadline: {impact_result.get('editorial_deadline', '22:00')}
- Deadline at risk: {deadline_at_risk}
- Projected delay: {delay_min:.0f} minutes
- Current ingest rate: {current_rate:.2f} GB/s (normal: {required_rate:.2f} GB/s)

IMPORTANT: All actions must be SIMULATED (this is a demo system).
Label each action clearly with its risk and expected benefit.

Provide recommendations as JSON:
{{
  "actions": [
    {{
      "id": "action-1",
      "action": "specific action description",
      "action_type": "SIMULATED",
      "risk_level": "LOW" | "MEDIUM" | "HIGH",
      "expected_benefit": "LOW" | "MEDIUM" | "HIGH",
      "expected_recovery_minutes": integer,
      "confidence": 0.0-1.0,
      "details": {{
        "space_freed_gb": number | null,
        "target_utilization_pct": number | null,
        "description": "technical explanation"
      }}
    }}
  ],
  "expected_recovery_minutes": integer,
  "summary": "remediation summary"
}}

Return ONLY valid JSON."""

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(prompt),
        )

        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        result = json.loads(text)
        result["source"] = "GEMINI_GENERATED"
        return result

    def _template_recommendations(
        self,
        scenario_type: str,
        context: dict[str, Any],
        impact_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate template-based recommendations when Gemini unavailable."""
        actions = []
        for i, action_text in enumerate(context.get("actions", []), 1):
            actions.append({
                "id": f"action-{i}",
                "action": action_text,
                "action_type": "SIMULATED",
                "risk_level": context.get("risk", "LOW"),
                "expected_benefit": context.get("benefit", "HIGH"),
                "expected_recovery_minutes": context.get("expected_recovery_minutes", 15),
                "confidence": 0.87,
                "details": {
                    "space_freed_gb": 180 if scenario_type == "STORAGE_SATURATION" else None,
                    "target_utilization_pct": context.get("target_utilization"),
                    "description": context.get("immediate_action", ""),
                },
            })

        return {
            "actions": actions,
            "expected_recovery_minutes": context.get("expected_recovery_minutes", 15),
            "summary": context.get("immediate_action", ""),
            "source": "TEMPLATE",
        }
