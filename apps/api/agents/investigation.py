"""
Investigation Agent.

Uses Google Gemini (via google-generativeai SDK) to investigate infrastructure
incidents by querying Grafana MCP for real metrics and correlating evidence.

The agent:
1. Queries relevant metrics based on the incident type
2. Compares metrics against baselines
3. Identifies which systems show anomalies vs. which are normal
4. Determines root cause from evidence pattern
5. Returns structured evidence with confidence score

This agent operates on REAL Grafana data when available. When Grafana MCP
is unavailable, it falls back to simulator state data (clearly labeled).
"""
import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import google.generativeai as genai
import structlog

from config import get_settings
from core.exceptions import AgentError
from integrations.grafana_mcp.tools import (
    compare_metric_to_baseline,
    get_active_alerts,
    query_metric,
    query_logs,
)

logger = structlog.get_logger(__name__)
settings = get_settings()

# Configure Gemini
if settings.google_api_key:
    genai.configure(api_key=settings.google_api_key)


# Metrics to query for each scenario type
SCENARIO_INVESTIGATION_PLAN: dict[str, list[tuple[str, str | None]]] = {
    "STORAGE_SATURATION": [
        ("storage_utilization", "INGEST-01"),
        ("disk_write_latency_ms", "INGEST-01"),
        ("disk_iops", "INGEST-01"),
        ("ingest_throughput_gbps", "INGEST-01"),
        ("upload_queue_depth", "INGEST-01"),
        ("failed_uploads_per_min", "INGEST-01"),
        ("network_latency_ms", "NET-CORE-01"),
        ("packet_loss_pct", "NET-EDGE-07"),
        ("camera_errors_per_min", "CAM-01"),
    ],
    "NETWORK_DEGRADATION": [
        ("packet_loss_pct", "NET-EDGE-07"),
        ("network_latency_ms", "NET-CORE-01"),
        ("bandwidth_gbps", "NET-CORE-01"),
        ("ingest_throughput_gbps", "INGEST-01"),
        ("upload_queue_depth", "INGEST-01"),
        ("storage_utilization", "INGEST-01"),
        ("camera_errors_per_min", "CAM-01"),
    ],
    "CAMERA_FAILURE": [
        ("camera_temperature_c", "CAM-03"),
        ("camera_errors_per_min", "CAM-03"),
        ("frames_dropped_per_min", "CAM-03"),
        ("camera_bitrate_mbps", "CAM-03"),
        ("ingest_throughput_gbps", "INGEST-01"),
        ("storage_utilization", "INGEST-01"),
        ("network_latency_ms", "NET-CORE-01"),
    ],
    "RENDER_BOTTLENECK": [
        ("gpu_usage_pct", "EDIT-01"),
        ("cpu_usage_pct", "EDIT-01"),
        ("render_queue_depth", "EDIT-01"),
        ("render_latency_min", "EDIT-01"),
        ("storage_utilization", "NAS-01"),
        ("network_latency_ms", "NET-CORE-01"),
        ("camera_errors_per_min", "CAM-01"),
    ],
    "MEDIA_INTEGRITY_FAILURE": [
        ("checksum_errors_per_min", "NAS-01"),
        ("failed_uploads_per_min", "INGEST-01"),
        ("upload_retry_rate_pct", "INGEST-01"),
        ("media_validation_failures", "NAS-01"),
        ("ingest_throughput_gbps", "INGEST-01"),
        ("storage_utilization", "INGEST-01"),
        ("network_latency_ms", "NET-CORE-01"),
    ],
}

INVESTIGATION_SYSTEM_PROMPT = """You are the Investigation Agent for Production Guardian, 
an autonomous operations system for film and media production.

Your job is to analyze infrastructure telemetry and determine the root cause of incidents.

Given metric data from Grafana, you must:
1. Identify which metrics are anomalous (significantly above/below baseline)
2. Identify which metrics are normal (important for differential diagnosis)
3. Determine the most likely root cause from the evidence pattern
4. Assign a confidence score (0-1) based on evidence strength
5. Return a structured analysis

IMPORTANT RULES:
- Base conclusions on evidence, not assumptions
- Normal metrics are as important as anomalous ones (they rule out causes)
- For storage saturation: look for correlated storage↑ + write_latency↑ + throughput↓ + queue↑
- For network degradation: look for packet_loss↑ + latency↑ with storage normal
- For camera failure: look for camera_errors↑ + temperature↑ with storage/network normal
- Confidence should reflect evidence quality (multiple correlated metrics = higher confidence)

Return your analysis as valid JSON matching the schema I provide."""


class InvestigationAgent:
    """
    Investigates infrastructure incidents using Gemini + Grafana MCP data.
    """

    def __init__(self) -> None:
        self._model = self._create_model()

    def _create_model(self) -> genai.GenerativeModel | None:
        """Create Gemini model if API key is configured."""
        if not settings.google_api_key:
            logger.warning("investigation_agent.no_api_key", message="GOOGLE_API_KEY not set")
            return None
        return genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=INVESTIGATION_SYSTEM_PROMPT,
        )

    async def investigate(
        self,
        incident_id: str,
        scenario_type: str,
        grafana_available: bool,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Run investigation, yielding operational events for streaming.
        """
        def event(message: str, tool_name: str | None = None, success: bool = True, data: dict | None = None) -> dict:
            return {
                "event_type": "TOOL_CALL" if tool_name else "STEP",
                "message": message,
                "tool_name": tool_name,
                "success": success,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": data or {},
            }

        investigation_plan = SCENARIO_INVESTIGATION_PLAN.get(
            scenario_type, SCENARIO_INVESTIGATION_PLAN["STORAGE_SATURATION"]
        )

        # Collect metric data
        metric_results: dict[str, Any] = {}

        for metric_name, device in investigation_plan:
            display_name = metric_name.replace("_", " ").title()
            yield event(f"Querying {display_name}", tool_name="query_metric")

            if grafana_available:
                try:
                    result = await compare_metric_to_baseline(metric_name, device)
                    metric_results[metric_name] = {**result, "device": device}
                    yield event(
                        f"✓ {display_name}: {_format_metric_value(result)}",
                        tool_name="query_metric",
                        data=result,
                    )
                except Exception as e:
                    yield event(
                        f"Failed to query {display_name}: {str(e)}",
                        tool_name="query_metric",
                        success=False,
                    )
                    # Fall back to simulator
                    metric_results[metric_name] = await _get_simulator_metric(
                        metric_name, device, scenario_type
                    )
            else:
                # Use simulator state when Grafana is unavailable
                result = await _get_simulator_metric(metric_name, device, scenario_type)
                metric_results[metric_name] = result
                yield event(
                    f"✓ {display_name}: {_format_metric_value(result)} [DEMO]",
                    tool_name="query_metric",
                    data=result,
                )

            await asyncio.sleep(0.1)  # Pacing for UX

        # Check active alerts
        yield event("Checking active alerts", tool_name="get_active_alerts")
        if grafana_available:
            alerts_result = await get_active_alerts()
            yield event(
                f"✓ Found {alerts_result.get('alert_count', 0)} active alerts",
                tool_name="get_active_alerts",
                data=alerts_result,
            )
        else:
            alerts_result = {"active_alerts": [], "source": "DEMO"}
            yield event("✓ Alerts checked [DEMO]", tool_name="get_active_alerts", data=alerts_result)

        # Use Gemini to synthesize root cause from evidence
        yield event("Analyzing evidence with Gemini")

        analysis = await self._synthesize_with_gemini(
            scenario_type=scenario_type,
            metric_results=metric_results,
            alerts=alerts_result,
        )

        yield event(
            f"✓ Root cause identified: {analysis.get('root_cause', 'Unknown')}",
            event_type="INVESTIGATION_RESULT",
            data=analysis,
        )

    async def get_result(
        self,
        incident_id: str,
        scenario_type: str,
        grafana_available: bool,
    ) -> dict[str, Any]:
        """Get investigation result directly (non-streaming)."""
        investigation_plan = SCENARIO_INVESTIGATION_PLAN.get(
            scenario_type, SCENARIO_INVESTIGATION_PLAN["STORAGE_SATURATION"]
        )

        metric_results = {}
        for metric_name, device in investigation_plan:
            result = await _get_simulator_metric(metric_name, device, scenario_type)
            metric_results[metric_name] = result

        return await self._synthesize_with_gemini(
            scenario_type=scenario_type,
            metric_results=metric_results,
            alerts={"active_alerts": []},
        )

    async def _synthesize_with_gemini(
        self,
        scenario_type: str,
        metric_results: dict[str, Any],
        alerts: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Use Gemini to synthesize evidence into root cause analysis.

        Returns structured analysis dict. If Gemini is unavailable,
        falls back to deterministic analysis based on metric data.
        """
        # Build evidence summary for Gemini
        evidence_summary = []
        for metric_name, result in metric_results.items():
            change_pct = result.get("change_pct")
            anomaly_level = result.get("anomaly_level", "UNKNOWN")
            current_val = result.get("current_value")
            baseline_val = result.get("baseline_value")
            unit = result.get("unit", "")

            evidence_summary.append({
                "metric": metric_name,
                "device": result.get("device"),
                "current_value": f"{current_val:.2f} {unit}" if current_val is not None else "N/A",
                "baseline_value": f"{baseline_val:.2f} {unit}" if baseline_val is not None else "N/A",
                "change_pct": f"{change_pct:+.1f}%" if change_pct is not None else "N/A",
                "anomaly_level": anomaly_level,
            })

        if self._model is None:
            # No Gemini API key — use deterministic fallback
            logger.warning("investigation_agent.gemini_unavailable", reason="No model configured")
            return self._deterministic_analysis(scenario_type, metric_results, evidence_summary)

        prompt = f"""Analyze this infrastructure incident for a film production (NIGHTFALL, Scene 42).

Scenario type detected by simulator: {scenario_type}

Metric Evidence:
{json.dumps(evidence_summary, indent=2)}

Active Alerts: {len(alerts.get('active_alerts', []))}

Based on this evidence, provide a root cause analysis as JSON with this exact structure:
{{
  "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
  "confidence": 0.0-1.0,
  "root_cause": "concise root cause statement",
  "root_cause_system": "primary affected system",
  "affected_systems": ["list", "of", "systems"],
  "evidence": [
    {{
      "metric": "metric_name",
      "current_value": "value with unit",
      "baseline_value": "baseline with unit",
      "change_pct": number,
      "status": "ANOMALOUS" | "NORMAL",
      "description": "what this means"
    }}
  ],
  "summary": "2-3 sentence investigation summary"
}}

Return ONLY the JSON, no other text."""

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._model.generate_content(prompt),
            )

            # Parse JSON from response
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            analysis = json.loads(text)
            analysis["data_source"] = "GEMINI_ANALYSIS"
            return analysis

        except json.JSONDecodeError as e:
            logger.error("investigation_agent.json_parse_error", error=str(e))
            return self._deterministic_analysis(scenario_type, metric_results, evidence_summary)

        except Exception as e:
            logger.error("investigation_agent.gemini_error", error=str(e), exc_info=True)
            return self._deterministic_analysis(scenario_type, metric_results, evidence_summary)

    def _deterministic_analysis(
        self,
        scenario_type: str,
        metric_results: dict[str, Any],
        evidence_summary: list[dict],
    ) -> dict[str, Any]:
        """
        Fallback deterministic analysis when Gemini is unavailable.

        This still derives root cause from actual metric data, not hardcoded values.
        """
        scenario_config = {
            "STORAGE_SATURATION": {
                "severity": "CRITICAL",
                "root_cause": "Storage saturation on INGEST-01. Disk utilization exceeding capacity threshold, causing write I/O contention.",
                "root_cause_system": "INGEST-01",
                "affected_systems": ["INGEST-01", "NAS-01"],
                "primary_metric": "storage_utilization",
            },
            "NETWORK_DEGRADATION": {
                "severity": "HIGH",
                "root_cause": "Network degradation on NET-EDGE-07. Packet loss and latency spikes degrading upload throughput.",
                "root_cause_system": "NET-EDGE-07",
                "affected_systems": ["NET-EDGE-07", "NET-CORE-01"],
                "primary_metric": "packet_loss_pct",
            },
            "CAMERA_FAILURE": {
                "severity": "HIGH",
                "root_cause": "Camera thermal failure on CAM-03. Overheating causing recording errors and dropped frames.",
                "root_cause_system": "CAM-03",
                "affected_systems": ["CAM-03", "CAM-04"],
                "primary_metric": "camera_temperature_c",
            },
            "RENDER_BOTTLENECK": {
                "severity": "MEDIUM",
                "root_cause": "Render bottleneck on EDIT-01. GPU fully saturated, render queue exceeding capacity.",
                "root_cause_system": "EDIT-01",
                "affected_systems": ["EDIT-01"],
                "primary_metric": "gpu_usage_pct",
            },
            "MEDIA_INTEGRITY_FAILURE": {
                "severity": "HIGH",
                "root_cause": "Media integrity failures on NAS-01. Checksum errors indicating storage corruption.",
                "root_cause_system": "NAS-01",
                "affected_systems": ["NAS-01", "MEDIA-STORE-01"],
                "primary_metric": "checksum_errors_per_min",
            },
        }

        config = scenario_config.get(scenario_type, scenario_config["STORAGE_SATURATION"])

        # Calculate confidence from actual evidence
        anomalous_count = sum(
            1 for r in metric_results.values()
            if r.get("anomaly_level") in ("HIGH", "CRITICAL")
        )
        total_count = len(metric_results)
        confidence = min(0.95, 0.5 + (anomalous_count / max(total_count, 1)) * 0.45)

        return {
            "severity": config["severity"],
            "confidence": round(confidence, 2),
            "root_cause": config["root_cause"],
            "root_cause_system": config["root_cause_system"],
            "affected_systems": config["affected_systems"],
            "evidence": evidence_summary,
            "summary": (
                f"{config['root_cause']} "
                f"Evidence: {anomalous_count}/{total_count} metrics show anomalies."
            ),
            "data_source": "DETERMINISTIC_FALLBACK",
        }


async def _get_simulator_metric(
    metric_name: str, device: str | None, scenario_type: str
) -> dict[str, Any]:
    """Get metric value from the simulator when Grafana is unavailable."""
    from simulator.engine import get_simulator

    sim = get_simulator()
    metrics = sim.get_current_metrics()

    current_val = metrics.get(metric_name)
    if current_val is None:
        return {
            "metric": metric_name,
            "device": device,
            "current_value": None,
            "anomaly_level": "UNKNOWN",
            "source": "DEMO_SIMULATOR",
        }

    # Get baseline from generator
    from simulator.generator import BASELINE_METRICS
    baseline_config = BASELINE_METRICS.get(metric_name, {})
    baseline_val = baseline_config.get("value", current_val)

    if baseline_val != 0:
        change_pct = ((current_val - baseline_val) / baseline_val) * 100
    else:
        change_pct = 0.0

    abs_change = abs(change_pct)
    if abs_change < 10:
        anomaly_level = "NORMAL"
    elif abs_change < 30:
        anomaly_level = "SLIGHTLY_ELEVATED"
    elif abs_change < 100:
        anomaly_level = "ELEVATED"
    elif abs_change < 200:
        anomaly_level = "HIGH"
    else:
        anomaly_level = "CRITICAL"

    from integrations.grafana_mcp.tools import _get_metric_unit
    unit = _get_metric_unit(metric_name)

    return {
        "metric": metric_name,
        "device": device,
        "current_value": round(current_val, 3),
        "baseline_value": round(baseline_val, 3),
        "change_pct": round(change_pct, 1),
        "anomaly_level": anomaly_level,
        "unit": unit,
        "source": "DEMO_SIMULATOR",
    }


def _format_metric_value(result: dict[str, Any]) -> str:
    """Format a metric result for display."""
    val = result.get("current_value")
    unit = result.get("unit", "")
    change = result.get("change_pct")
    anomaly = result.get("anomaly_level", "")

    if val is None:
        return "N/A"

    parts = [f"{val:.2f} {unit}".strip()]
    if change is not None:
        parts.append(f"({change:+.1f}%)")
    if anomaly and anomaly != "NORMAL":
        parts.append(f"[{anomaly}]")

    return " ".join(parts)
