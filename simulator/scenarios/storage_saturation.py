"""
Storage Saturation Scenario (Primary Demo).

Root cause: INGEST-01 disk fills up due to accumulating proxy files.

Causal chain:
  storage_utilization ↑
      → disk_write_latency ↑ (I/O contention at high utilization)
      → ingest_throughput ↓ (can't write fast enough)
      → upload_queue ↑ (frames piling up)
      → failed_uploads ↑ (queue overflow)
      → editorial deadline threatened

Counter-indicators (NOT affected — agent should recognize this):
  - network_latency: NORMAL
  - packet_loss: NORMAL
  - camera errors: NORMAL (cameras are fine, problem is ingest-side)

This asymmetry is what makes the diagnosis non-trivial.
"""
from simulator.base import BaseScenario, MetricProfile


class StorageSaturationScenario(BaseScenario):

    @property
    def name(self) -> str:
        return "STORAGE_SATURATION"

    @property
    def description(self) -> str:
        return (
            "Storage saturation on INGEST-01. "
            "Disk utilization approaching capacity due to accumulated proxy files, "
            "causing write latency to spike and ingest throughput to collapse."
        )

    @property
    def affected_systems(self) -> list[str]:
        return ["INGEST-01", "NAS-01", "MEDIA-STORE-01"]

    @property
    def primary_metric(self) -> str:
        return "storage_utilization"

    @property
    def metric_profiles(self) -> dict[str, MetricProfile]:
        return {
            # PRIMARY: Storage fills up
            # 72% → 75% → 79% → 84% → 88% → 94% → 96%
            "storage_utilization": MetricProfile(
                baseline=68.0,
                incident_peak=96.5,
                recovery_target=61.0,
                unit="%",
                higher_is_worse=True,
                noise_std=0.005,
            ),

            # CAUSAL: Write latency spikes as disk saturates (I/O contention)
            # Normal: ~40ms. During incident: up to +240% → ~136ms
            "disk_write_latency_ms": MetricProfile(
                baseline=40.0,
                incident_peak=136.0,
                recovery_target=38.0,
                unit="ms",
                higher_is_worse=True,
                noise_std=0.08,
            ),

            # Read latency also increases but less dramatically
            "disk_read_latency_ms": MetricProfile(
                baseline=12.0,
                incident_peak=28.0,
                recovery_target=11.0,
                unit="ms",
                higher_is_worse=True,
                noise_std=0.06,
            ),

            # IOPS degrade at high utilization
            "disk_iops": MetricProfile(
                baseline=12000.0,
                incident_peak=4800.0,
                recovery_target=11500.0,
                unit="IOPS",
                higher_is_worse=False,
                noise_std=0.04,
            ),

            # CAUSAL: Ingest throughput drops (can't write)
            # 1.8 GB/s → 1.5 → 1.2 → 0.9 → 0.7 GB/s
            "ingest_throughput_gbps": MetricProfile(
                baseline=1.85,
                incident_peak=0.68,
                recovery_target=1.92,
                unit="GB/s",
                higher_is_worse=False,
                noise_std=0.05,
            ),

            # CAUSAL: Upload queue grows (frames pile up)
            # 20 → 50 → 120 → 300 → 700 → 1200+
            "upload_queue_depth": MetricProfile(
                baseline=18.0,
                incident_peak=1240.0,
                recovery_target=22.0,
                unit="frames",
                higher_is_worse=True,
                noise_std=0.10,
            ),

            # CAUSAL: Failed uploads (queue overflow)
            "failed_uploads_per_min": MetricProfile(
                baseline=0.2,
                incident_peak=28.0,
                recovery_target=0.3,
                unit="per min",
                higher_is_worse=True,
                noise_std=0.15,
            ),

            # Ingest latency increases
            "ingest_latency_ms": MetricProfile(
                baseline=85.0,
                incident_peak=380.0,
                recovery_target=90.0,
                unit="ms",
                higher_is_worse=True,
                noise_std=0.08,
            ),

            # COUNTER-INDICATOR: Network is normal
            "network_latency_ms": MetricProfile(
                baseline=2.4,
                incident_peak=2.6,  # Barely changes
                recovery_target=2.4,
                unit="ms",
                higher_is_worse=True,
                noise_std=0.05,
            ),

            # COUNTER-INDICATOR: Packet loss is normal
            "packet_loss_pct": MetricProfile(
                baseline=0.01,
                incident_peak=0.02,  # Normal noise variation
                recovery_target=0.01,
                unit="%",
                higher_is_worse=True,
                noise_std=0.20,
            ),

            # COUNTER-INDICATOR: Camera errors are normal
            "camera_errors_per_min": MetricProfile(
                baseline=0.05,
                incident_peak=0.08,  # Normal noise
                recovery_target=0.05,
                unit="per min",
                higher_is_worse=True,
                noise_std=0.25,
            ),

            # Bandwidth normal
            "bandwidth_gbps": MetricProfile(
                baseline=8.5,
                incident_peak=8.3,  # Essentially unchanged
                recovery_target=8.5,
                unit="Gbps",
                higher_is_worse=False,
                noise_std=0.03,
            ),
        }
