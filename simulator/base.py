"""
Base classes for simulator scenarios.

Each scenario defines:
- Which metrics are affected
- How they behave during the incident (via parameter profiles)
- The causal chain (e.g., storage↑ causes write_latency↑ causes throughput↓)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SimulatorState(str, Enum):
    NORMAL = "NORMAL"
    INCIDENT_ACTIVE = "INCIDENT_ACTIVE"
    REMEDIATING = "REMEDIATING"
    RECOVERED = "RECOVERED"


@dataclass
class MetricProfile:
    """
    Defines how a metric behaves during an incident.

    baseline: Normal value
    incident_peak: Value at full incident severity
    recovery_target: Value after successful remediation
    unit: Unit label for display
    higher_is_worse: If True, higher values are bad (e.g., latency, errors)
    """
    baseline: float
    incident_peak: float
    recovery_target: float
    unit: str
    higher_is_worse: bool = True
    noise_std: float = 0.02  # Relative noise (fraction of current value)


class BaseScenario(ABC):
    """Abstract base for all incident scenarios."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Scenario identifier."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        ...

    @property
    @abstractmethod
    def affected_systems(self) -> list[str]:
        """List of affected infrastructure components."""
        ...

    @property
    @abstractmethod
    def primary_metric(self) -> str:
        """The key metric that drives the incident."""
        ...

    @property
    @abstractmethod
    def metric_profiles(self) -> dict[str, MetricProfile]:
        """
        Maps metric names to their behavioral profiles.

        Metric names should match what is pushed to Prometheus/Grafana.
        """
        ...

    def get_metric_value(
        self,
        metric_name: str,
        incident_progress: float,
        noise: float = 0.0,
    ) -> float | None:
        """
        Calculate the current value of a metric given incident progress (0.0–1.0).

        Returns None if this scenario doesn't affect the metric.
        """
        profile = self.metric_profiles.get(metric_name)
        if profile is None:
            return None

        # Interpolate between baseline and incident peak
        current = profile.baseline + (profile.incident_peak - profile.baseline) * incident_progress

        # Apply noise (relative to current value)
        import random
        noise_amount = current * profile.noise_std
        current += random.gauss(0, noise_amount)

        return max(0.0, current)

    def get_recovery_value(
        self,
        metric_name: str,
        remediation_progress: float,
        incident_progress: float = 1.0,
        noise: float = 0.0,
    ) -> float | None:
        """
        Calculate metric value during recovery (0.0–1.0 remediation_progress).
        """
        profile = self.metric_profiles.get(metric_name)
        if profile is None:
            return None

        # Start from incident peak, recover to target
        peak = profile.baseline + (profile.incident_peak - profile.baseline) * incident_progress
        current = peak + (profile.recovery_target - peak) * remediation_progress

        import random
        noise_amount = abs(current) * profile.noise_std
        current += random.gauss(0, noise_amount)

        return max(0.0, current)
