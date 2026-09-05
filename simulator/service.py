"""
Simulator background service.

This module provides a background task runner that periodically pushes
telemetry to Grafana Cloud. Can be run as a standalone process or
integrated with the FastAPI backend.
"""
import asyncio
import os
import sys
import time

import structlog

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from dotenv import load_dotenv
load_dotenv()

from config import get_settings
from core.logging import configure_logging
from simulator.engine import get_simulator
from simulator.pusher import TelemetryPusher

configure_logging()
logger = structlog.get_logger(__name__)
settings = get_settings()

PUSH_INTERVAL = settings.simulator_push_interval_seconds


async def run_simulator() -> None:
    """Run the simulator push loop indefinitely."""
    pusher = TelemetryPusher()
    sim = get_simulator()

    logger.info(
        "simulator.service_started",
        push_interval_seconds=PUSH_INTERVAL,
        grafana_configured=bool(settings.grafana_prometheus_remote_write_url),
    )

    while True:
        try:
            metrics = sim.get_current_metrics()
            success = pusher.push(metrics)

            if success:
                logger.debug(
                    "simulator.push_success",
                    state=sim.state.value,
                    scenario=sim.active_scenario_name,
                    metric_count=len(metrics),
                )
            else:
                logger.debug(
                    "simulator.push_skipped",
                    reason="Grafana not configured or unavailable",
                )

        except Exception as e:
            logger.error("simulator.push_error", error=str(e))

        await asyncio.sleep(PUSH_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run_simulator())
