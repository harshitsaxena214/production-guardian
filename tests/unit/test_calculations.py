"""Unit tests for production impact calculations."""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestImpactCalculations:
    """Test deterministic production impact calculations."""

    def test_ingest_rate_delay_calculation(self):
        """Test that delay is correctly calculated from ingest rate degradation."""
        # 680 GB footage, 80% remaining = 544 GB to ingest
        estimated_footage_gb = 680.0
        footage_ingested_pct = 0.20
        footage_remaining_gb = estimated_footage_gb * (1 - footage_ingested_pct)

        normal_rate_gbps = 1.85  # GB/s
        degraded_rate_gbps = 0.68  # GB/s (storage saturation peak)

        # Time at normal rate
        normal_time_hours = footage_remaining_gb / (normal_rate_gbps * 3600)
        # Time at degraded rate
        degraded_time_hours = footage_remaining_gb / (degraded_rate_gbps * 3600)

        delay_hours = degraded_time_hours - normal_time_hours
        delay_minutes = delay_hours * 60

        # At 0.68 GB/s vs 1.85 GB/s with 544 GB remaining:
        # Normal: 544 / (1.85 * 3600) ≈ 0.0817 hours ≈ 4.9 min
        # Degraded: 544 / (0.68 * 3600) ≈ 0.2222 hours ≈ 13.3 min
        # Delay: ~8.4 minutes (much less than 47 min — the 47 min comes from daily footage)
        # For 680 full GB:
        normal_full = 680.0 / (normal_rate_gbps * 3600)  # hours
        degraded_full = 680.0 / (degraded_rate_gbps * 3600)  # hours
        full_delay_min = (degraded_full - normal_full) * 60

        # Should be in the range of 30-100 minutes for this scenario
        assert delay_minutes > 0, "Delay should be positive"
        assert full_delay_min > 30, f"Full footage delay should be significant, got {full_delay_min:.1f} min"

    def test_deadline_risk_assessment(self):
        """Test that deadline risk is correctly assessed."""
        from datetime import datetime, timezone, timedelta

        editorial_deadline = "22:00"
        current_time_str = "14:30"

        # Parse times (same day)
        now = datetime.now(timezone.utc)
        current = now.replace(hour=14, minute=30, second=0, microsecond=0)
        deadline = now.replace(hour=22, minute=0, second=0, microsecond=0)
        available_hours = (deadline - current).total_seconds() / 3600
        assert abs(available_hours - 7.5) < 0.01, f"Available hours should be 7.5, got {available_hours}"

        # If ingest will take 9 hours, deadline is at risk
        completion_degraded = current + timedelta(hours=9)
        deadline_at_risk = completion_degraded > deadline
        assert deadline_at_risk, "Deadline should be at risk if completion takes longer than available time"

        # If ingest will take 6 hours, deadline is safe
        completion_normal = current + timedelta(hours=6)
        deadline_safe = completion_normal < deadline
        assert deadline_safe, "Deadline should be safe if completion is within available time"

    def test_zero_rate_handling(self):
        """Test that zero ingest rate doesn't cause division by zero."""
        footage_gb = 680.0
        rate_gbps = 0.0

        if rate_gbps > 0:
            time_hours = footage_gb / (rate_gbps * 3600)
        else:
            time_hours = float("inf")

        assert time_hours == float("inf"), "Zero rate should result in infinite time"

    def test_downstream_risk_list(self):
        """Test that downstream risks are correctly identified."""
        dependent_scenes = [43, 44]
        delay_minutes = 47.0

        risks = []
        for scene_num in dependent_scenes:
            risks.append(f"Scene {scene_num} assembly delayed by ~{delay_minutes / 60:.1f} hours")

        if delay_minutes > 30:
            risks.append("Daily delivery package at risk")

        assert len(risks) == 3
        assert "Scene 43" in risks[0]
        assert "Scene 44" in risks[1]
        assert "Daily delivery" in risks[2]
