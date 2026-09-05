"""
Metric Generator.

Generates all infrastructure metric values for all devices based on current
simulator state. Handles normal baselines, incident degradation, and recovery.
"""
import math
import random
import time
from typing import Any

from simulator.base import BaseScenario, SimulatorState


# Normal baseline values for all metrics (when no incident is active)
BASELINE_METRICS: dict[str, dict[str, Any]] = {
    # Storage metrics (INGEST-01, INGEST-02, NAS-01, MEDIA-STORE-01)
    "storage_utilization": {"value": 68.0, "noise": 0.3, "unit": "%"},
    "disk_read_latency_ms": {"value": 12.0, "noise": 0.8, "unit": "ms"},
    "disk_write_latency_ms": {"value": 40.0, "noise": 2.0, "unit": "ms"},
    "disk_iops": {"value": 12000.0, "noise": 300.0, "unit": "IOPS"},
    "disk_errors": {"value": 0.0, "noise": 0.1, "unit": "count"},

    # Ingest metrics
    "ingest_throughput_gbps": {"value": 1.85, "noise": 0.04, "unit": "GB/s"},
    "ingest_latency_ms": {"value": 85.0, "noise": 5.0, "unit": "ms"},
    "upload_queue_depth": {"value": 18.0, "noise": 3.0, "unit": "frames"},
    "failed_uploads_per_min": {"value": 0.2, "noise": 0.1, "unit": "per min"},
    "frames_dropped_per_min": {"value": 0.1, "noise": 0.05, "unit": "per min"},
    "upload_retry_rate_pct": {"value": 0.5, "noise": 0.1, "unit": "%"},

    # Network metrics
    "network_latency_ms": {"value": 2.4, "noise": 0.2, "unit": "ms"},
    "packet_loss_pct": {"value": 0.01, "noise": 0.005, "unit": "%"},
    "bandwidth_gbps": {"value": 8.5, "noise": 0.2, "unit": "Gbps"},
    "connections": {"value": 124.0, "noise": 8.0, "unit": "count"},

    # Camera metrics (aggregate of CAM-01 through CAM-04)
    "camera_temperature_c": {"value": 38.0, "noise": 1.0, "unit": "°C"},
    "camera_errors_per_min": {"value": 0.05, "noise": 0.03, "unit": "per min"},
    "camera_bitrate_mbps": {"value": 3200.0, "noise": 50.0, "unit": "Mbps"},

    # Editing metrics
    "gpu_usage_pct": {"value": 45.0, "noise": 3.0, "unit": "%"},
    "cpu_usage_pct": {"value": 32.0, "noise": 4.0, "unit": "%"},
    "render_queue_depth": {"value": 3.0, "noise": 1.0, "unit": "jobs"},
    "render_latency_min": {"value": 12.0, "noise": 1.0, "unit": "min"},

    # Media integrity
    "checksum_errors_per_min": {"value": 0.0, "noise": 0.0, "unit": "per min"},
    "media_validation_failures": {"value": 0.0, "noise": 0.0, "unit": "per min"},
}


class MetricGenerator:
    """Generates realistic metric values for all infrastructure components."""

    def generate_all_metrics(
        self,
        state: SimulatorState,
        scenario: BaseScenario | None,
        incident_progress: float,
        remediation_progress: float,
    ) -> dict[str, Any]:
        """
        Generate all metric values based on current state.

        Returns a flat dict of metric_name → value.
        """
        metrics = {}

        for metric_name, config in BASELINE_METRICS.items():
            value = self._get_metric_value(
                metric_name=metric_name,
                baseline=config["value"],
                noise=config["noise"],
                state=state,
                scenario=scenario,
                incident_progress=incident_progress,
                remediation_progress=remediation_progress,
            )
            metrics[metric_name] = round(max(0.0, value), 3)

        return metrics

    def _get_metric_value(
        self,
        metric_name: str,
        baseline: float,
        noise: float,
        state: SimulatorState,
        scenario: BaseScenario | None,
        incident_progress: float,
        remediation_progress: float,
    ) -> float:
        """Get the current value for a single metric."""
        if state == SimulatorState.NORMAL or scenario is None:
            return self._apply_noise(baseline, noise)

        if state == SimulatorState.INCIDENT_ACTIVE:
            scenario_value = scenario.get_metric_value(metric_name, incident_progress)
            if scenario_value is not None:
                return scenario_value
            return self._apply_noise(baseline, noise)

        if state == SimulatorState.REMEDIATING:
            scenario_value = scenario.get_recovery_value(
                metric_name, remediation_progress, incident_progress=1.0
            )
            if scenario_value is not None:
                return scenario_value
            return self._apply_noise(baseline, noise)

        if state == SimulatorState.RECOVERED:
            # Slightly better than baseline (freshly cleaned up)
            profile = scenario.metric_profiles.get(metric_name) if scenario else None
            if profile is not None:
                return self._apply_noise(profile.recovery_target, noise * 0.5)
            return self._apply_noise(baseline, noise)

        return self._apply_noise(baseline, noise)

    def _apply_noise(self, value: float, noise: float) -> float:
        """Apply Gaussian noise to a value."""
        return value + random.gauss(0, noise)

    def calculate_system_health(self, metrics: dict[str, Any]) -> dict[str, float]:
        """
        Calculate health percentage for each system category (0–100).

        100 = perfect, 0 = completely failed.
        """
        def _health_from_metric(
            current: float, baseline: float, bad_value: float, higher_is_worse: bool
        ) -> float:
            """Calculate 0–100 health score for a single metric."""
            if higher_is_worse:
                # 100% when at baseline, 0% when at bad_value
                if bad_value <= baseline:
                    return 100.0
                normalized = (current - baseline) / (bad_value - baseline)
            else:
                # 100% when at baseline, 0% when at bad_value
                if bad_value >= baseline:
                    return 100.0
                normalized = (baseline - current) / (baseline - bad_value)
            return max(0.0, min(100.0, (1.0 - normalized) * 100.0))

        # Storage health
        storage_score = _health_from_metric(
            metrics.get("storage_utilization", 68), 68, 96, higher_is_worse=True
        )
        write_latency_score = _health_from_metric(
            metrics.get("disk_write_latency_ms", 40), 40, 136, higher_is_worse=True
        )
        storage_health = (storage_score * 0.6 + write_latency_score * 0.4)

        # Ingest health
        throughput_score = _health_from_metric(
            metrics.get("ingest_throughput_gbps", 1.85), 1.85, 0.68, higher_is_worse=False
        )
        queue_score = _health_from_metric(
            metrics.get("upload_queue_depth", 18), 18, 1240, higher_is_worse=True
        )
        ingest_health = throughput_score * 0.6 + queue_score * 0.4

        # Network health
        packet_loss_score = _health_from_metric(
            metrics.get("packet_loss_pct", 0.01), 0.01, 8.5, higher_is_worse=True
        )
        latency_score = _health_from_metric(
            metrics.get("network_latency_ms", 2.4), 2.4, 145, higher_is_worse=True
        )
        network_health = packet_loss_score * 0.5 + latency_score * 0.5

        # Camera health
        cam_error_score = _health_from_metric(
            metrics.get("camera_errors_per_min", 0.05), 0.05, 24, higher_is_worse=True
        )
        cam_temp_score = _health_from_metric(
            metrics.get("camera_temperature_c", 38), 38, 78, higher_is_worse=True
        )
        camera_health = cam_error_score * 0.5 + cam_temp_score * 0.5

        # Editing health
        gpu_score = _health_from_metric(
            metrics.get("gpu_usage_pct", 45), 45, 98.5, higher_is_worse=True
        )
        render_queue_score = _health_from_metric(
            metrics.get("render_queue_depth", 3), 3, 142, higher_is_worse=True
        )
        editing_health = gpu_score * 0.6 + render_queue_score * 0.4

        return {
            "storage": round(max(0.0, min(100.0, storage_health)), 1),
            "ingest": round(max(0.0, min(100.0, ingest_health)), 1),
            "network": round(max(0.0, min(100.0, network_health)), 1),
            "cameras": round(max(0.0, min(100.0, camera_health)), 1),
            "editing": round(max(0.0, min(100.0, editing_health)), 1),
        }
