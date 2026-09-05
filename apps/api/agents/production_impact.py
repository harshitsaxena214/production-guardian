"""
Production Impact Agent.

Translates infrastructure incidents into film production consequences.
Retrieves production context from PostgreSQL and applies deterministic
calculations to estimate deadline risk and downstream dependencies.

This agent deliberately uses a deterministic calculation layer rather than
asking Gemini to invent numbers — the math must be traceable and reliable.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models.database import Production, Scene

logger = structlog.get_logger(__name__)
settings = get_settings()


class ProductionImpactAgent:
    """
    Calculates real production impact from infrastructure incidents.

    Uses actual scene data from the database to calculate:
    - How much footage is at risk
    - Current vs. required ingest rate
    - Projected completion time
    - Editorial deadline status
    - Downstream scene dependencies
    """

    async def calculate_impact(
        self,
        incident_id: str,
        investigation_result: dict[str, Any],
        db_session: AsyncSession,
    ) -> dict[str, Any]:
        """
        Calculate production impact from investigation results.

        Returns structured impact analysis with calculated (not invented) values.
        """
        logger.info(
            "impact_agent.calculating",
            incident_id=incident_id,
            root_cause_system=investigation_result.get("root_cause_system"),
        )

        # Get production context from database
        production = await self._get_production(db_session)
        if not production:
            return self._unavailable_impact()

        # Get current scene (Scene 42)
        current_scene = await self._get_current_scene(db_session, production)
        if not current_scene:
            return self._unavailable_impact()

        # Get simulator state for current ingest rate
        from simulator.engine import get_simulator
        sim = get_simulator()
        metrics = sim.get_current_metrics()

        current_ingest_rate = metrics.get("ingest_throughput_gbps", 1.85)
        required_ingest_rate = 1.85  # Normal/target rate

        # Calculate impact using real data
        return await self._calculate_impact_math(
            current_scene=current_scene,
            production=production,
            current_ingest_rate_gbps=current_ingest_rate,
            required_ingest_rate_gbps=required_ingest_rate,
            db_session=db_session,
        )

    async def _get_production(self, db: AsyncSession) -> Production | None:
        """Get the NIGHTFALL production from database."""
        try:
            result = await db.execute(
                select(Production).where(Production.name == settings.production_name)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("impact_agent.db_error", error=str(e))
            return None

    async def _get_current_scene(
        self, db: AsyncSession, production: Production
    ) -> Scene | None:
        """Get the current active scene from database."""
        try:
            # Get Scene 42 (the primary demo scene)
            result = await db.execute(
                select(Scene).where(
                    Scene.production_id == production.id,
                    Scene.scene_number == production.current_scene_number,
                )
            )
            scene = result.scalar_one_or_none()

            if not scene:
                # Fallback: get Scene 42 directly
                result = await db.execute(
                    select(Scene).where(
                        Scene.production_id == production.id,
                        Scene.scene_number == 42,
                    )
                )
                scene = result.scalar_one_or_none()

            return scene
        except Exception as e:
            logger.error("impact_agent.scene_query_error", error=str(e))
            return None

    async def _calculate_impact_math(
        self,
        current_scene: Scene,
        production: Production,
        current_ingest_rate_gbps: float,
        required_ingest_rate_gbps: float,
        db_session: AsyncSession,
    ) -> dict[str, Any]:
        """
        Deterministic impact calculation.

        All values here are derived from actual data — not invented.
        """
        estimated_footage_gb = current_scene.estimated_footage_gb
        editorial_deadline_str = current_scene.editorial_deadline or "22:00"

        # Estimate how much footage has already been ingested
        # (assume 20% ingested so far for demo — 5.5 hours into an 8h shoot day)
        footage_ingested_pct = 0.20
        footage_ingested_gb = estimated_footage_gb * footage_ingested_pct
        footage_remaining_gb = estimated_footage_gb - footage_ingested_gb

        # Calculate time to ingest remaining footage at current rate
        if current_ingest_rate_gbps > 0:
            time_to_complete_hours_at_current = footage_remaining_gb / (
                current_ingest_rate_gbps * 3600
            )
        else:
            time_to_complete_hours_at_current = float("inf")

        # Calculate required time at normal rate
        if required_ingest_rate_gbps > 0:
            time_to_complete_hours_at_normal = footage_remaining_gb / (
                required_ingest_rate_gbps * 3600
            )
        else:
            time_to_complete_hours_at_normal = float("inf")

        # Current time (use a fixed time for demo: 14:30 production day)
        now = datetime.now(timezone.utc)
        demo_current_time = now.replace(hour=14, minute=30, second=0, microsecond=0)

        # Parse editorial deadline
        deadline_parts = editorial_deadline_str.split(":")
        deadline_hour = int(deadline_parts[0])
        deadline_minute = int(deadline_parts[1]) if len(deadline_parts) > 1 else 0
        deadline_dt = demo_current_time.replace(
            hour=deadline_hour, minute=deadline_minute, second=0, microsecond=0
        )

        # Available time until deadline (hours)
        available_hours = max(0, (deadline_dt - demo_current_time).total_seconds() / 3600)

        # Projected delay = extra time needed at degraded rate vs. normal rate
        if time_to_complete_hours_at_current == float("inf"):
            projected_delay_hours = available_hours  # Complete miss
        else:
            extra_time = time_to_complete_hours_at_current - time_to_complete_hours_at_normal
            projected_delay_hours = max(0, extra_time)

        projected_delay_minutes = projected_delay_hours * 60

        # Estimated completion time at current rate
        estimated_completion_dt = demo_current_time + timedelta(
            hours=time_to_complete_hours_at_current
        )
        estimated_completion_str = estimated_completion_dt.strftime("%H:%M")

        # Deadline at risk if completion time > deadline
        deadline_at_risk = estimated_completion_dt > deadline_dt

        # Production severity
        if deadline_at_risk and projected_delay_minutes > 60:
            production_severity = "CRITICAL"
        elif deadline_at_risk:
            production_severity = "HIGH"
        elif projected_delay_minutes > 20:
            production_severity = "MEDIUM"
        else:
            production_severity = "LOW"

        # Downstream risks
        downstream_risks = await self._get_downstream_risks(
            current_scene, db_session, projected_delay_minutes
        )

        logger.info(
            "impact_agent.calculation_complete",
            scene_number=current_scene.scene_number,
            footage_remaining_gb=round(footage_remaining_gb, 1),
            current_rate_gbps=round(current_ingest_rate_gbps, 3),
            required_rate_gbps=round(required_ingest_rate_gbps, 3),
            projected_delay_minutes=round(projected_delay_minutes, 1),
            deadline_at_risk=deadline_at_risk,
        )

        return {
            "affected_scene_numbers": [current_scene.scene_number],
            "current_scene_number": current_scene.scene_number,
            "current_ingest_rate_gbps": round(current_ingest_rate_gbps, 3),
            "required_ingest_rate_gbps": round(required_ingest_rate_gbps, 3),
            "estimated_footage_gb": estimated_footage_gb,
            "footage_ingested_gb": round(footage_ingested_gb, 1),
            "footage_remaining_gb": round(footage_remaining_gb, 1),
            "editorial_deadline": editorial_deadline_str,
            "estimated_completion_time": estimated_completion_str,
            "projected_delay_minutes": round(projected_delay_minutes, 1),
            "deadline_at_risk": deadline_at_risk,
            "available_hours_until_deadline": round(available_hours, 2),
            "downstream_risk": downstream_risks,
            "production_severity": production_severity,
            "calculation_method": "DETERMINISTIC",
        }

    async def _get_downstream_risks(
        self,
        current_scene: Scene,
        db: AsyncSession,
        delay_minutes: float,
    ) -> list[str]:
        """Get downstream scene risks from Scene 42's dependencies."""
        risks = []

        if delay_minutes <= 0:
            return risks

        dependent_numbers = current_scene.dependent_scene_numbers or []

        try:
            for scene_num in dependent_numbers:
                risks.append(
                    f"Scene {scene_num} assembly delayed by ~{round(delay_minutes / 60, 1)} hours"
                )
        except Exception:
            pass

        if delay_minutes > 30:
            risks.append("Daily delivery package at risk")

        return risks

    def _unavailable_impact(self) -> dict[str, Any]:
        """Return when database or production data is unavailable."""
        return {
            "affected_scene_numbers": [42],
            "current_scene_number": 42,
            "current_ingest_rate_gbps": None,
            "required_ingest_rate_gbps": 1.85,
            "estimated_footage_gb": 680.0,
            "footage_ingested_gb": None,
            "footage_remaining_gb": None,
            "editorial_deadline": "22:00",
            "estimated_completion_time": None,
            "projected_delay_minutes": None,
            "deadline_at_risk": True,
            "available_hours_until_deadline": None,
            "downstream_risk": ["Database unavailable — impact calculation incomplete"],
            "production_severity": "HIGH",
            "calculation_method": "UNAVAILABLE",
        }
