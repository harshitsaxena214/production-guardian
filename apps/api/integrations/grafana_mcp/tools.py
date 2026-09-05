"""
Grafana MCP Tool Wrappers for Gemini/ADK.

These functions wrap the raw Grafana MCP calls into structured operations
that the Gemini agent can use as tools.

Each function:
- Has a descriptive docstring (used as tool description by ADK)
- Returns a clean typed result
- Handles errors gracefully (returns error dict instead of raising)
- Logs the tool call for operational transparency

The agent will choose which tools to call based on the investigation context.
These are NOT called blindly — the agent decides based on the incident type.
"""
import time
from typing import Any

import structlog

from core.exceptions import GrafanaMCPError, GrafanaMCPUnavailableError
from integrations.grafana_mcp.client import GrafanaMCPClient, get_grafana_mcp_client

logger = structlog.get_logger(__name__)

# Time window for metric queries during investigation
INVESTIGATION_WINDOW_MINUTES = 60
BASELINE_WINDOW_HOURS = 24


async def query_metric(
    metric_name: str,
    device: str | None = None,
    window_minutes: int = INVESTIGATION_WINDOW_MINUTES,
    client: GrafanaMCPClient | None = None,
) -> dict[str, Any]:
    """
    Query a production infrastructure metric from Grafana via MCP.

    Use this to retrieve current and recent values for storage, ingest,
    network, camera, or editing metrics. Always check a metric before
    drawing conclusions about root cause.

    Args:
        metric_name: The metric to query (e.g., 'storage_utilization',
                     'disk_write_latency_ms', 'ingest_throughput_gbps',
                     'packet_loss_pct', 'camera_errors_per_min')
        device: Specific device to query (e.g., 'INGEST-01'). If None, queries aggregate.
        window_minutes: How far back to look (default 60 minutes)

    Returns:
        dict with:
          - metric: metric name
          - device: device queried
          - current_value: most recent value
          - avg_value: average over window
          - max_value: peak over window
          - unit: measurement unit
          - data_points: list of (timestamp, value) tuples
          - source: "GRAFANA_LIVE" or "GRAFANA_UNAVAILABLE"
    """
    mcp = client or get_grafana_mcp_client()
    start_time = time.monotonic()
    prom_metric = f"production_guardian_{metric_name}"

    # Build PromQL query with optional device filter
    if device:
        query = f'{prom_metric}{{device="{device}"}}'
    else:
        query = f'{prom_metric}{{production="nightfall"}}'

    logger.info(
        "grafana_tool.query_metric",
        metric=metric_name,
        device=device,
        query=query,
    )

    try:
        result = await mcp.query_prometheus_metric(
            query=query,
            start=f"now-{window_minutes}m",
            end="now",
            step="60s",
        )

        duration_ms = int((time.monotonic() - start_time) * 1000)
        data_points = _extract_prometheus_data_points(result)

        if not data_points:
            return {
                "metric": metric_name,
                "device": device,
                "current_value": None,
                "avg_value": None,
                "max_value": None,
                "unit": "",
                "data_points": [],
                "source": "GRAFANA_LIVE",
                "note": "No data points returned. Is telemetry being pushed?",
                "duration_ms": duration_ms,
            }

        values = [dp["value"] for dp in data_points if dp["value"] is not None]
        current_value = data_points[-1]["value"] if data_points else None

        return {
            "metric": metric_name,
            "device": device or "aggregate",
            "current_value": current_value,
            "avg_value": round(sum(values) / len(values), 3) if values else None,
            "max_value": round(max(values), 3) if values else None,
            "min_value": round(min(values), 3) if values else None,
            "unit": _get_metric_unit(metric_name),
            "data_points": data_points[-20:],  # Last 20 points for context
            "source": "GRAFANA_LIVE",
            "duration_ms": duration_ms,
        }

    except GrafanaMCPUnavailableError as e:
        logger.warning(
            "grafana_tool.mcp_unavailable",
            metric=metric_name,
            error=str(e),
        )
        return {
            "metric": metric_name,
            "device": device,
            "current_value": None,
            "source": "GRAFANA_UNAVAILABLE",
            "message": str(e),
            "status": "unavailable",
        }

    except GrafanaMCPError as e:
        logger.error(
            "grafana_tool.query_error",
            metric=metric_name,
            error=str(e),
        )
        return {
            "metric": metric_name,
            "device": device,
            "current_value": None,
            "source": "GRAFANA_ERROR",
            "message": str(e),
            "status": "error",
        }


async def query_logs(
    system: str,
    time_window_minutes: int = 30,
    search_terms: list[str] | None = None,
    client: GrafanaMCPClient | None = None,
) -> dict[str, Any]:
    """
    Query system logs from Grafana Loki via MCP.

    Use this to find error messages, warnings, and operational events
    that correlate with the incident timeline.

    Args:
        system: System to query logs for (e.g., 'INGEST-01', 'NAS-01', 'NET-EDGE-07')
        time_window_minutes: How far back to look
        search_terms: Optional list of terms to filter by (e.g., ['error', 'failed'])

    Returns:
        dict with log entries and summary
    """
    mcp = client or get_grafana_mcp_client()

    log_query = f'{{device="{system}",production="nightfall"}}'
    if search_terms:
        filter_parts = " |= ".join(f'"{term}"' for term in search_terms)
        log_query += f" |= {filter_parts}"

    logger.info("grafana_tool.query_logs", system=system, query=log_query)

    try:
        result = await mcp.query_loki_logs(
            query=log_query,
            start=f"now-{time_window_minutes}m",
            end="now",
            limit=50,
        )

        content = result.get("content", [])
        if isinstance(content, list) and content:
            entries = content[0].get("text", "") if isinstance(content[0], dict) else str(content)
        else:
            entries = str(result)

        return {
            "system": system,
            "source": "GRAFANA_LIVE",
            "log_entries": entries,
            "entry_count": len(entries.split("\n")) if isinstance(entries, str) else 0,
            "time_window_minutes": time_window_minutes,
        }

    except GrafanaMCPUnavailableError as e:
        return {
            "system": system,
            "source": "GRAFANA_UNAVAILABLE",
            "message": str(e),
            "status": "unavailable",
        }
    except Exception as e:
        return {
            "system": system,
            "source": "GRAFANA_ERROR",
            "message": str(e),
            "status": "error",
        }


async def get_active_alerts(
    client: GrafanaMCPClient | None = None,
) -> dict[str, Any]:
    """
    Get currently active Grafana alerts via MCP.

    Use this to see which alerting rules have been triggered. Active alerts
    provide important corroboration for the investigation.

    Returns:
        dict with list of active alerts and their details.
    """
    mcp = client or get_grafana_mcp_client()
    logger.info("grafana_tool.get_alerts")

    try:
        alerts = await mcp.get_alerts(state="alerting")
        return {
            "source": "GRAFANA_LIVE",
            "active_alerts": alerts,
            "alert_count": len(alerts),
        }
    except GrafanaMCPUnavailableError as e:
        return {
            "source": "GRAFANA_UNAVAILABLE",
            "message": str(e),
            "status": "unavailable",
            "active_alerts": [],
        }
    except Exception as e:
        return {
            "source": "GRAFANA_ERROR",
            "message": str(e),
            "status": "error",
            "active_alerts": [],
        }


async def compare_metric_to_baseline(
    metric_name: str,
    device: str | None = None,
    client: GrafanaMCPClient | None = None,
) -> dict[str, Any]:
    """
    Compare a metric's current value against its 24-hour baseline.

    Use this to quantify how anomalous a metric is. Returns the percentage
    change from baseline and an anomaly assessment.

    Args:
        metric_name: The metric to compare
        device: Specific device

    Returns:
        dict with current value, baseline, change percentage, and anomaly classification
    """
    mcp = client or get_grafana_mcp_client()

    # Get current (last 15 min) and baseline (24h ago)
    current_task = query_metric(metric_name, device, 15, mcp)
    baseline_task = query_metric(metric_name, device, 60 * 24, mcp)

    current_result, baseline_result = await _gather_safely(current_task, baseline_task)

    current_val = current_result.get("current_value")
    baseline_avg = baseline_result.get("avg_value")

    if current_val is None or baseline_avg is None or baseline_avg == 0:
        return {
            "metric": metric_name,
            "device": device,
            "current_value": current_val,
            "baseline_value": baseline_avg,
            "change_pct": None,
            "anomaly_level": "UNKNOWN",
            "source": "GRAFANA_LIVE" if current_result.get("source") == "GRAFANA_LIVE" else "GRAFANA_UNAVAILABLE",
        }

    change_pct = ((current_val - baseline_avg) / baseline_avg) * 100
    abs_change = abs(change_pct)

    # Classify anomaly
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

    return {
        "metric": metric_name,
        "device": device,
        "current_value": round(current_val, 3),
        "baseline_value": round(baseline_avg, 3),
        "change_pct": round(change_pct, 1),
        "anomaly_level": anomaly_level,
        "unit": _get_metric_unit(metric_name),
        "source": "GRAFANA_LIVE",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_prometheus_data_points(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract data points from a Prometheus MCP tool response."""
    content = result.get("content", [])
    data_points = []

    try:
        # MCP responses vary — try to parse the content
        if isinstance(content, list) and content:
            text_content = content[0].get("text", "") if isinstance(content[0], dict) else ""
            # The MCP server may return JSON-embedded in the text content
            import json
            if text_content.startswith("{") or text_content.startswith("["):
                parsed = json.loads(text_content)
                if "data" in parsed:
                    for series in parsed["data"].get("result", []):
                        for ts, val in series.get("values", []):
                            try:
                                data_points.append({
                                    "timestamp": float(ts),
                                    "value": float(val),
                                })
                            except (ValueError, TypeError):
                                pass

    except (json.JSONDecodeError, KeyError, TypeError, IndexError):
        pass

    return data_points


def _get_metric_unit(metric_name: str) -> str:
    """Get the unit for a metric name."""
    unit_map = {
        "storage_utilization": "%",
        "disk_read_latency_ms": "ms",
        "disk_write_latency_ms": "ms",
        "disk_iops": "IOPS",
        "ingest_throughput_gbps": "GB/s",
        "ingest_latency_ms": "ms",
        "upload_queue_depth": "frames",
        "failed_uploads_per_min": "/min",
        "frames_dropped_per_min": "/min",
        "network_latency_ms": "ms",
        "packet_loss_pct": "%",
        "bandwidth_gbps": "Gbps",
        "camera_temperature_c": "°C",
        "camera_errors_per_min": "/min",
        "camera_bitrate_mbps": "Mbps",
        "gpu_usage_pct": "%",
        "cpu_usage_pct": "%",
        "render_queue_depth": "jobs",
        "render_latency_min": "min",
        "checksum_errors_per_min": "/min",
        "media_validation_failures": "/min",
    }
    return unit_map.get(metric_name, "")


async def _gather_safely(*coros):
    """Run coroutines concurrently, returning None on error."""
    import asyncio
    results = await asyncio.gather(*coros, return_exceptions=True)
    return [
        r if not isinstance(r, Exception) else {"error": str(r)}
        for r in results
    ]
