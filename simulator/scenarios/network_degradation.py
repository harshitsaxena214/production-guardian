"""Network Degradation Scenario."""
from simulator.base import BaseScenario, MetricProfile


class NetworkDegradationScenario(BaseScenario):
    @property
    def name(self) -> str:
        return "NETWORK_DEGRADATION"

    @property
    def description(self) -> str:
        return (
            "Network degradation on NET-EDGE-07. "
            "Packet loss and latency spike, impacting upload throughput "
            "from cameras to ingest servers."
        )

    @property
    def affected_systems(self) -> list[str]:
        return ["NET-CORE-01", "NET-EDGE-07", "INGEST-01", "INGEST-02"]

    @property
    def primary_metric(self) -> str:
        return "packet_loss_pct"

    @property
    def metric_profiles(self) -> dict[str, MetricProfile]:
        return {
            "packet_loss_pct": MetricProfile(
                baseline=0.01, incident_peak=8.5, recovery_target=0.02,
                unit="%", higher_is_worse=True, noise_std=0.10,
            ),
            "network_latency_ms": MetricProfile(
                baseline=2.4, incident_peak=145.0, recovery_target=2.5,
                unit="ms", higher_is_worse=True, noise_std=0.08,
            ),
            "bandwidth_gbps": MetricProfile(
                baseline=8.5, incident_peak=2.1, recovery_target=8.4,
                unit="Gbps", higher_is_worse=False, noise_std=0.06,
            ),
            "ingest_throughput_gbps": MetricProfile(
                baseline=1.85, incident_peak=0.52, recovery_target=1.80,
                unit="GB/s", higher_is_worse=False, noise_std=0.07,
            ),
            "upload_queue_depth": MetricProfile(
                baseline=18.0, incident_peak=890.0, recovery_target=20.0,
                unit="frames", higher_is_worse=True, noise_std=0.10,
            ),
            "failed_uploads_per_min": MetricProfile(
                baseline=0.2, incident_peak=42.0, recovery_target=0.3,
                unit="per min", higher_is_worse=True, noise_std=0.12,
            ),
            # Counter-indicators: storage is fine
            "storage_utilization": MetricProfile(
                baseline=68.0, incident_peak=70.0, recovery_target=68.0,
                unit="%", higher_is_worse=True, noise_std=0.005,
            ),
            "disk_write_latency_ms": MetricProfile(
                baseline=40.0, incident_peak=42.0, recovery_target=40.0,
                unit="ms", higher_is_worse=True, noise_std=0.05,
            ),
        }
