"""Render Bottleneck Scenario."""
from simulator.base import BaseScenario, MetricProfile


class RenderBottleneckScenario(BaseScenario):
    @property
    def name(self) -> str:
        return "RENDER_BOTTLENECK"

    @property
    def description(self) -> str:
        return (
            "Render bottleneck on EDIT-01. "
            "GPU fully saturated, render queue growing, "
            "threatening editorial deadline."
        )

    @property
    def affected_systems(self) -> list[str]:
        return ["EDIT-01", "EDIT-02"]

    @property
    def primary_metric(self) -> str:
        return "gpu_usage_pct"

    @property
    def metric_profiles(self) -> dict[str, MetricProfile]:
        return {
            "gpu_usage_pct": MetricProfile(
                baseline=45.0, incident_peak=98.5, recovery_target=48.0,
                unit="%", higher_is_worse=True, noise_std=0.02,
            ),
            "cpu_usage_pct": MetricProfile(
                baseline=32.0, incident_peak=91.0, recovery_target=35.0,
                unit="%", higher_is_worse=True, noise_std=0.03,
            ),
            "render_queue_depth": MetricProfile(
                baseline=3.0, incident_peak=142.0, recovery_target=4.0,
                unit="jobs", higher_is_worse=True, noise_std=0.08,
            ),
            "render_latency_min": MetricProfile(
                baseline=12.0, incident_peak=78.0, recovery_target=13.0,
                unit="min", higher_is_worse=True, noise_std=0.06,
            ),
            # Counter-indicators
            "storage_utilization": MetricProfile(
                baseline=68.0, incident_peak=70.0, recovery_target=68.0,
                unit="%", higher_is_worse=True, noise_std=0.005,
            ),
            "network_latency_ms": MetricProfile(
                baseline=2.4, incident_peak=2.5, recovery_target=2.4,
                unit="ms", higher_is_worse=True, noise_std=0.05,
            ),
            "camera_errors_per_min": MetricProfile(
                baseline=0.05, incident_peak=0.07, recovery_target=0.05,
                unit="per min", higher_is_worse=True, noise_std=0.25,
            ),
        }
