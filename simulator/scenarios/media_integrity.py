"""Media Integrity Failure Scenario."""
from simulator.base import BaseScenario, MetricProfile


class MediaIntegrityScenario(BaseScenario):
    @property
    def name(self) -> str:
        return "MEDIA_INTEGRITY_FAILURE"

    @property
    def description(self) -> str:
        return (
            "Media integrity failures on NAS-01. "
            "Checksum errors indicate corrupted footage, "
            "causing failed uploads and retry storms."
        )

    @property
    def affected_systems(self) -> list[str]:
        return ["NAS-01", "MEDIA-STORE-01", "INGEST-01"]

    @property
    def primary_metric(self) -> str:
        return "checksum_errors_per_min"

    @property
    def metric_profiles(self) -> dict[str, MetricProfile]:
        return {
            "checksum_errors_per_min": MetricProfile(
                baseline=0.0, incident_peak=48.0, recovery_target=0.0,
                unit="per min", higher_is_worse=True, noise_std=0.15,
            ),
            "failed_uploads_per_min": MetricProfile(
                baseline=0.2, incident_peak=52.0, recovery_target=0.2,
                unit="per min", higher_is_worse=True, noise_std=0.12,
            ),
            "upload_retry_rate_pct": MetricProfile(
                baseline=0.5, incident_peak=38.0, recovery_target=0.5,
                unit="%", higher_is_worse=True, noise_std=0.10,
            ),
            "media_validation_failures": MetricProfile(
                baseline=0.0, incident_peak=36.0, recovery_target=0.0,
                unit="per min", higher_is_worse=True, noise_std=0.15,
            ),
            "ingest_throughput_gbps": MetricProfile(
                baseline=1.85, incident_peak=0.88, recovery_target=1.82,
                unit="GB/s", higher_is_worse=False, noise_std=0.06,
            ),
            # Counter-indicators
            "storage_utilization": MetricProfile(
                baseline=68.0, incident_peak=71.0, recovery_target=68.0,
                unit="%", higher_is_worse=True, noise_std=0.005,
            ),
            "network_latency_ms": MetricProfile(
                baseline=2.4, incident_peak=2.6, recovery_target=2.4,
                unit="ms", higher_is_worse=True, noise_std=0.05,
            ),
        }
