"""
Telemetry Simulator Engine.

Manages the current simulation state and provides access to the scenario registry.
The engine is a singleton that maintains state across API requests.
"""
import asyncio
import time
from enum import Enum
from threading import Lock
from typing import Any

import structlog

from simulator.scenarios.storage_saturation import StorageSaturationScenario
from simulator.scenarios.network_degradation import NetworkDegradationScenario
from simulator.scenarios.camera_failure import CameraFailureScenario
from simulator.scenarios.render_bottleneck import RenderBottleneckScenario
from simulator.scenarios.media_integrity import MediaIntegrityScenario
from simulator.generator import MetricGenerator
from simulator.base import BaseScenario, SimulatorState

logger = structlog.get_logger(__name__)


SCENARIO_REGISTRY: dict[str, type[BaseScenario]] = {
    "STORAGE_SATURATION": StorageSaturationScenario,
    "NETWORK_DEGRADATION": NetworkDegradationScenario,
    "CAMERA_FAILURE": CameraFailureScenario,
    "RENDER_BOTTLENECK": RenderBottleneckScenario,
    "MEDIA_INTEGRITY_FAILURE": MediaIntegrityScenario,
}


class SimulatorEngine:
    """
    Central state machine for the telemetry simulator.

    States: NORMAL → INCIDENT_ACTIVE → REMEDIATING → RECOVERED → NORMAL

    Thread-safe via a lock; async-safe by running sync operations in executor.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._state = SimulatorState.NORMAL
        self._active_scenario: BaseScenario | None = None
        self._scenario_name: str | None = None
        self._scenario_start_time: float | None = None
        self._remediation_start_time: float | None = None
        self._generator = MetricGenerator()
        self._incident_step = 0  # Progress counter for gradual degradation

    @property
    def state(self) -> SimulatorState:
        return self._state

    @property
    def active_scenario_name(self) -> str | None:
        return self._scenario_name

    @property
    def is_incident_active(self) -> bool:
        return self._state in (SimulatorState.INCIDENT_ACTIVE, SimulatorState.REMEDIATING)

    def activate_scenario(self, scenario_name: str) -> dict[str, Any]:
        """Activate an incident scenario. Returns scenario metadata."""
        with self._lock:
            if scenario_name not in SCENARIO_REGISTRY:
                raise ValueError(
                    f"Unknown scenario: {scenario_name}. "
                    f"Available: {list(SCENARIO_REGISTRY.keys())}"
                )

            scenario_class = SCENARIO_REGISTRY[scenario_name]
            self._active_scenario = scenario_class()
            self._scenario_name = scenario_name
            self._state = SimulatorState.INCIDENT_ACTIVE
            self._scenario_start_time = time.time()
            self._incident_step = 0

            logger.info(
                "simulator.scenario_activated",
                scenario=scenario_name,
                description=self._active_scenario.description,
            )

            return {
                "scenario": scenario_name,
                "description": self._active_scenario.description,
                "affected_systems": self._active_scenario.affected_systems,
                "primary_metric": self._active_scenario.primary_metric,
            }

    def begin_remediation(self) -> None:
        """Transition to REMEDIATING state."""
        with self._lock:
            if self._state != SimulatorState.INCIDENT_ACTIVE:
                logger.warning(
                    "simulator.remediation_skipped",
                    reason="Not in INCIDENT_ACTIVE state",
                    current_state=self._state.value,
                )
                return
            self._state = SimulatorState.REMEDIATING
            self._remediation_start_time = time.time()
            logger.info("simulator.remediation_started")

    def complete_remediation(self) -> None:
        """Transition to RECOVERED state."""
        with self._lock:
            self._state = SimulatorState.RECOVERED
            logger.info("simulator.remediation_completed")

    def reset(self) -> None:
        """Reset simulator to normal baseline state."""
        with self._lock:
            self._state = SimulatorState.NORMAL
            self._active_scenario = None
            self._scenario_name = None
            self._scenario_start_time = None
            self._remediation_start_time = None
            self._incident_step = 0
            logger.info("simulator.reset")

    def get_current_metrics(self) -> dict[str, Any]:
        """
        Generate current metric values based on simulator state.

        Returns a dict of all metric values for all infrastructure components.
        These values are used both for Prometheus push and for the UI telemetry endpoint.
        """
        with self._lock:
            incident_progress = self._calculate_incident_progress()
            remediation_progress = self._calculate_remediation_progress()

            metrics = self._generator.generate_all_metrics(
                state=self._state,
                scenario=self._active_scenario,
                incident_progress=incident_progress,
                remediation_progress=remediation_progress,
            )

            # Advance the incident step for next call
            if self._state == SimulatorState.INCIDENT_ACTIVE:
                self._incident_step = min(self._incident_step + 1, 10)

            return metrics

    def _calculate_incident_progress(self) -> float:
        """
        Calculate how far into the incident we are (0.0 → 1.0).

        The degradation is progressive over ~5 minutes to allow the demo to
        show gradual deterioration.
        """
        if (
            self._state != SimulatorState.INCIDENT_ACTIVE
            or self._scenario_start_time is None
        ):
            return 0.0

        elapsed = time.time() - self._scenario_start_time
        # Full degradation reached after 5 minutes (300 seconds)
        return min(elapsed / 300.0, 1.0)

    def _calculate_remediation_progress(self) -> float:
        """
        Calculate remediation recovery progress (0.0 → 1.0).

        Recovery happens over ~2 minutes.
        """
        if (
            self._state != SimulatorState.REMEDIATING
            or self._remediation_start_time is None
        ):
            return 0.0 if self._state != SimulatorState.RECOVERED else 1.0

        elapsed = time.time() - self._remediation_start_time
        return min(elapsed / 120.0, 1.0)

    def get_status(self) -> dict[str, Any]:
        """Get current simulator status for API response."""
        return {
            "state": self._state.value,
            "scenario": self._scenario_name,
            "incident_active": self.is_incident_active,
            "scenario_start_time": self._scenario_start_time,
            "incident_progress": self._calculate_incident_progress(),
        }


# Global singleton
_engine: SimulatorEngine | None = None


def get_simulator() -> SimulatorEngine:
    """Get the global simulator engine singleton."""
    global _engine
    if _engine is None:
        _engine = SimulatorEngine()
    return _engine
