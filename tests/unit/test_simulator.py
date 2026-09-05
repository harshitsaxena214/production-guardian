"""Unit tests for the telemetry simulator."""
import sys
import os
import pytest

# Add apps/api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from simulator.base import SimulatorState
from simulator.engine import SimulatorEngine, SCENARIO_REGISTRY
from simulator.generator import MetricGenerator, BASELINE_METRICS
from simulator.scenarios.storage_saturation import StorageSaturationScenario
from simulator.scenarios.network_degradation import NetworkDegradationScenario


class TestScenarioRegistry:
    """Test that all scenarios are registered."""

    def test_all_scenarios_present(self):
        expected = {
            "STORAGE_SATURATION",
            "NETWORK_DEGRADATION",
            "CAMERA_FAILURE",
            "RENDER_BOTTLENECK",
            "MEDIA_INTEGRITY_FAILURE",
        }
        assert set(SCENARIO_REGISTRY.keys()) == expected

    def test_each_scenario_has_required_attrs(self):
        for name, scenario_class in SCENARIO_REGISTRY.items():
            scenario = scenario_class()
            assert scenario.name == name
            assert len(scenario.description) > 10
            assert len(scenario.affected_systems) > 0
            assert len(scenario.primary_metric) > 0
            assert len(scenario.metric_profiles) > 0


class TestSimulatorEngine:
    """Test the simulator state machine."""

    def test_initial_state_is_normal(self):
        engine = SimulatorEngine()
        assert engine.state == SimulatorState.NORMAL
        assert not engine.is_incident_active
        assert engine.active_scenario_name is None

    def test_activate_scenario(self):
        engine = SimulatorEngine()
        info = engine.activate_scenario("STORAGE_SATURATION")
        assert engine.state == SimulatorState.INCIDENT_ACTIVE
        assert engine.is_incident_active
        assert engine.active_scenario_name == "STORAGE_SATURATION"
        assert "description" in info
        assert "affected_systems" in info

    def test_invalid_scenario_raises(self):
        engine = SimulatorEngine()
        with pytest.raises(ValueError, match="Unknown scenario"):
            engine.activate_scenario("NONEXISTENT_SCENARIO")

    def test_reset_clears_state(self):
        engine = SimulatorEngine()
        engine.activate_scenario("NETWORK_DEGRADATION")
        assert engine.is_incident_active
        engine.reset()
        assert engine.state == SimulatorState.NORMAL
        assert engine.active_scenario_name is None
        assert not engine.is_incident_active

    def test_remediation_state_transition(self):
        engine = SimulatorEngine()
        engine.activate_scenario("STORAGE_SATURATION")
        engine.begin_remediation()
        assert engine.state == SimulatorState.REMEDIATING
        engine.complete_remediation()
        assert engine.state == SimulatorState.RECOVERED


class TestMetricGenerator:
    """Test metric generation."""

    def test_normal_state_returns_baseline_values(self):
        gen = MetricGenerator()
        metrics = gen.generate_all_metrics(
            state=SimulatorState.NORMAL,
            scenario=None,
            incident_progress=0.0,
            remediation_progress=0.0,
        )
        assert "storage_utilization" in metrics
        assert "ingest_throughput_gbps" in metrics
        assert "network_latency_ms" in metrics
        assert "camera_errors_per_min" in metrics

        # Normal storage should be near baseline (68%)
        assert 50.0 < metrics["storage_utilization"] < 85.0

    def test_incident_state_degrades_primary_metric(self):
        gen = MetricGenerator()
        scenario = StorageSaturationScenario()

        # Full incident (progress=1.0) should be near incident_peak
        metrics = gen.generate_all_metrics(
            state=SimulatorState.INCIDENT_ACTIVE,
            scenario=scenario,
            incident_progress=1.0,
            remediation_progress=0.0,
        )

        # Storage should be near 96% at full incident
        assert metrics["storage_utilization"] > 85.0, \
            f"Storage at full incident should be >85%, got {metrics['storage_utilization']}"

        # Ingest throughput should be degraded
        assert metrics["ingest_throughput_gbps"] < 1.5, \
            f"Ingest throughput should be degraded, got {metrics['ingest_throughput_gbps']}"

    def test_incident_counter_indicators_stay_normal(self):
        """For storage saturation, network and camera should stay normal."""
        gen = MetricGenerator()
        scenario = StorageSaturationScenario()

        metrics = gen.generate_all_metrics(
            state=SimulatorState.INCIDENT_ACTIVE,
            scenario=scenario,
            incident_progress=1.0,
            remediation_progress=0.0,
        )

        # Network should NOT be significantly degraded in storage saturation
        assert metrics["packet_loss_pct"] < 0.5, \
            f"Packet loss should remain normal in storage saturation, got {metrics['packet_loss_pct']}"

        assert metrics["camera_errors_per_min"] < 2.0, \
            f"Camera errors should remain normal in storage saturation, got {metrics['camera_errors_per_min']}"

    def test_recovery_restores_metrics(self):
        """After remediation, metrics should recover toward baseline."""
        gen = MetricGenerator()
        scenario = StorageSaturationScenario()

        recovered_metrics = gen.generate_all_metrics(
            state=SimulatorState.RECOVERED,
            scenario=scenario,
            incident_progress=1.0,
            remediation_progress=1.0,
        )

        # Storage should recover to ~61%
        assert recovered_metrics["storage_utilization"] < 75.0, \
            f"Storage should recover, got {recovered_metrics['storage_utilization']}"

        # Ingest should recover
        assert recovered_metrics["ingest_throughput_gbps"] > 1.5, \
            f"Ingest should recover, got {recovered_metrics['ingest_throughput_gbps']}"

    def test_health_scores_calculated(self):
        gen = MetricGenerator()
        metrics = gen.generate_all_metrics(
            state=SimulatorState.NORMAL,
            scenario=None,
            incident_progress=0.0,
            remediation_progress=0.0,
        )
        health = gen.calculate_system_health(metrics)

        assert "storage" in health
        assert "ingest" in health
        assert "network" in health
        assert "cameras" in health
        assert "editing" in health

        # All normal health scores should be high
        for system, score in health.items():
            assert 50.0 < score <= 100.0, f"{system} health should be high in normal state, got {score}"

    def test_incident_degrades_health_scores(self):
        gen = MetricGenerator()
        scenario = StorageSaturationScenario()
        incident_metrics = gen.generate_all_metrics(
            state=SimulatorState.INCIDENT_ACTIVE,
            scenario=scenario,
            incident_progress=1.0,
            remediation_progress=0.0,
        )
        health = gen.calculate_system_health(incident_metrics)

        # Storage health should be degraded
        assert health["storage"] < 50.0, \
            f"Storage health should be degraded, got {health['storage']}"


class TestCausalChain:
    """Test that scenarios implement proper causal relationships."""

    def test_storage_saturation_causal_chain(self):
        """storage↑ causes write_latency↑ causes throughput↓ causes queue↑"""
        scenario = StorageSaturationScenario()
        profiles = scenario.metric_profiles

        assert profiles["storage_utilization"].incident_peak > profiles["storage_utilization"].baseline
        assert profiles["disk_write_latency_ms"].incident_peak > profiles["disk_write_latency_ms"].baseline
        assert profiles["ingest_throughput_gbps"].incident_peak < profiles["ingest_throughput_gbps"].baseline
        assert profiles["upload_queue_depth"].incident_peak > profiles["upload_queue_depth"].baseline

    def test_storage_saturation_counter_indicators_unchanged(self):
        """Network and cameras should remain essentially unchanged."""
        scenario = StorageSaturationScenario()
        profiles = scenario.metric_profiles

        # Network latency shouldn't spike much
        latency_ratio = profiles["network_latency_ms"].incident_peak / profiles["network_latency_ms"].baseline
        assert latency_ratio < 1.5, f"Network latency shouldn't spike in storage saturation"

        # Packet loss shouldn't spike
        loss_ratio = profiles["packet_loss_pct"].incident_peak / profiles["packet_loss_pct"].baseline
        assert loss_ratio < 5.0, f"Packet loss shouldn't spike significantly in storage saturation"
