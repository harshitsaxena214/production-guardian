"""
Database seed script for Production Guardian.

Seeds:
- NIGHTFALL production
- Scenes 40-45 with realistic film production data
- Scene 42 as the critical demo scene

Run from the apps/api directory:
  python ../../database/seed/seed.py
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

# Add apps/api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, delete

from models.database import Production, Scene, ScenePriority, SceneStatus, ProductionStatus
from core.database import Base


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://guardian:guardian@localhost:5432/production_guardian",
)


async def seed(db: AsyncSession) -> None:
    """Seed all production data."""
    print("🎬 Seeding Production Guardian database...")

    # Clear existing data
    await db.execute(delete(Scene))
    await db.execute(delete(Production))
    await db.commit()
    print("  ✓ Cleared existing data")

    # Create NIGHTFALL production
    production = Production(
        id=str(uuid.uuid4()),
        name="nightfall",
        display_name="NIGHTFALL",
        genre="Sci-Fi Thriller",
        production_day=47,
        status=ProductionStatus.ACTIVE,
        shoot_window_start="08:00",
        shoot_window_end="18:00",
        current_scene_number=42,
        primary_location="Stage 7 — Silverline Studios",
    )
    db.add(production)
    await db.flush()
    print(f"  ✓ Created production: NIGHTFALL (id: {production.id[:8]}...)")

    # Scene data
    scenes_data = [
        {
            "scene_number": 40,
            "title": "The Signal",
            "description": "Commander Reyes discovers the anomalous signal from deep space. INT. COMMAND DECK.",
            "location": "Stage 5 — Command Deck",
            "priority": ScenePriority.MEDIUM,
            "status": SceneStatus.COMPLETED,
            "estimated_footage_gb": 420.0,
            "editorial_deadline": "18:00",
            "dependent_scene_numbers": [41],
            "estimated_duration_hours": 6.0,
        },
        {
            "scene_number": 41,
            "title": "The Briefing",
            "description": "Senior crew reviews anomaly data. INT. BRIEFING ROOM. Night.",
            "location": "Stage 5 — Briefing Room",
            "priority": ScenePriority.MEDIUM,
            "status": SceneStatus.COMPLETED,
            "estimated_footage_gb": 310.0,
            "editorial_deadline": "18:00",
            "dependent_scene_numbers": [42],
            "estimated_duration_hours": 4.5,
        },
        {
            "scene_number": 42,
            "title": "Point of No Return",
            "description": (
                "Crew enters the anomaly zone. Critical action sequence. "
                "EXT. SPACE / INT. SHIP. High-intensity visual effects work."
            ),
            "location": "Stage 7 — Main Stage",
            "priority": ScenePriority.CRITICAL,
            "status": SceneStatus.IN_PROGRESS,
            "estimated_footage_gb": 680.0,
            "editorial_deadline": "22:00",
            "dependent_scene_numbers": [43, 44],
            "estimated_duration_hours": 10.0,
        },
        {
            "scene_number": 43,
            "title": "Inside the Anomaly",
            "description": "The crew's first encounter with the anomaly interior. VFX-heavy sequence.",
            "location": "Stage 7 — VFX Stage",
            "priority": ScenePriority.HIGH,
            "status": SceneStatus.SCHEDULED,
            "estimated_footage_gb": 540.0,
            "editorial_deadline": "23:00",
            "dependent_scene_numbers": [44],
            "estimated_duration_hours": 8.0,
        },
        {
            "scene_number": 44,
            "title": "Contact",
            "description": "First contact sequence. Emotionally pivotal scene. INT. ANOMALY CORE.",
            "location": "Stage 7 — VFX Stage",
            "priority": ScenePriority.HIGH,
            "status": SceneStatus.SCHEDULED,
            "estimated_footage_gb": 380.0,
            "editorial_deadline": "23:59",
            "dependent_scene_numbers": [45],
            "estimated_duration_hours": 6.0,
        },
        {
            "scene_number": 45,
            "title": "The Return",
            "description": "Resolution sequence. Crew emerges changed. EXT. SPACE.",
            "location": "Stage 3 — Exterior",
            "priority": ScenePriority.MEDIUM,
            "status": SceneStatus.SCHEDULED,
            "estimated_footage_gb": 290.0,
            "editorial_deadline": None,
            "dependent_scene_numbers": [],
            "estimated_duration_hours": 4.5,
        },
    ]

    for scene_data in scenes_data:
        scene = Scene(
            id=str(uuid.uuid4()),
            production_id=production.id,
            **scene_data,
        )
        db.add(scene)

    await db.commit()
    print(f"  ✓ Created {len(scenes_data)} scenes (40-45)")
    print("  ✓ Scene 42 'Point of No Return' marked as CRITICAL, IN_PROGRESS")
    print("  ✓ Scene 42: 680 GB footage, 22:00 editorial deadline")
    print("  ✓ Scene 42 dependents: [43, 44]")
    print("\n✅ Seed complete!")
    print("\nProduction context:")
    print(f"  Production: NIGHTFALL (Day {production.production_day})")
    print(f"  Location: {production.primary_location}")
    print(f"  Current Scene: {production.current_scene_number}")
    print(f"  Shoot Window: {production.shoot_window_start}–{production.shoot_window_end}")


async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  ✓ Tables created/verified")

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await seed(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
