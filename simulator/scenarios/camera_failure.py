"""Camera Failure Scenario."""
from simulator.base import BaseScenario, MetricProfile


class CameraFailureScenario(BaseScenario):
    @property
    def name(self) -> str:
        return "CAMERA_FAILURE"

    @property
    def description(self) -> str:
        return (
            "CAM-03 overheating causing recording errors and dropped frames. "
            "Temperature spike → bitrate instability → dropped frames → missing footage."
        )

    @property
    def affected_systems(self) -> list[str]:
        return ["CAM-03", "CAM-04"]

    @property
    def primary_metric(self) -> str:
        return "camera_temperature_c"

    @property
    def metric_profiles(self) -> dict[str, MetricProfile]:
        return {
            "camera_temperature_c": MetricProfile(
                baseline=38.0, incident_peak=78.0, recovery_target=40.0,
                unit="°C", higher_is_worse=True, noise_std=0.02,
            ),
            "camera_errors_per_min": MetricProfile(
                baseline=0.05, incident_peak=24.0, recovery_target=0.1,
                unit="per min", higher_is_worse=True, noise_std=0.15,
            ),
            "frames_dropped_per_min": MetricProfile(
                baseline=0.1, incident_peak=180.0, recovery_target=0.2,
                unit="per min", higher_is_worse=True, noise_std=0.12,
            ),
            "camera_bitrate_mbps": MetricProfile(
                baseline=3200.0, incident_peak=1400.0, recovery_target=3100.0,
                unit="Mbps", higher_is_worse=False, noise_std=0.08,
            ),
            "ingest_throughput_gbps": MetricProfile(
                baseline=1.85, incident_peak=0.95, recovery_target=1.80,
                unit="GB/s", higher_is_worse=False, noise_std=0.06,
            ),
            # Counter-indicators
            "storage_utilization": MetricProfile(
                baseline=68.0, incident_peak=69.0, recovery_target=68.0,
                unit="%", higher_is_worse=True, noise_std=0.005,
            ),
            "network_latency_ms": MetricProfile(
                baseline=2.4, incident_peak=2.5, recovery_target=2.4,
                unit="ms", higher_is_worse=True, noise_std=0.05,
            ),
            "packet_loss_pct": MetricProfile(
                baseline=0.01, incident_peak=0.02, recovery_target=0.01,
                unit="%", higher_is_worse=True, noise_std=0.20,
            ),
        }
