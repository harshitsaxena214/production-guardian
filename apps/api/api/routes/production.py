"""Production and scene API routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.database import Production, Scene
from schemas.production import OverviewSchema, ProductionSchema, ProductionSummarySchema, SceneSchema, SystemHealthSchema
from simulator.engine import get_simulator

router = APIRouter()


@router.get("/production", response_model=ProductionSummarySchema)
async def get_production(db: AsyncSession = Depends(get_db)) -> ProductionSummarySchema:
    """Get the current production (NIGHTFALL)."""
    result = await db.execute(select(Production).limit(1))
    production = result.scalar_one_or_none()

    if not production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No production found. Run the seed script first.",
        )

    return ProductionSummarySchema.model_validate(production)


@router.get("/production/scenes", response_model=list[SceneSchema])
async def get_scenes(db: AsyncSession = Depends(get_db)) -> list[SceneSchema]:
    """Get all scenes for the current production."""
    result = await db.execute(
        select(Production).limit(1)
    )
    production = result.scalar_one_or_none()

    if not production:
        return []

    scenes_result = await db.execute(
        select(Scene)
        .where(Scene.production_id == production.id)
        .order_by(Scene.scene_number)
    )
    scenes = scenes_result.scalars().all()
    return [SceneSchema.model_validate(s) for s in scenes]


@router.get("/production/scenes/{scene_number}", response_model=SceneSchema)
async def get_scene(
    scene_number: int,
    db: AsyncSession = Depends(get_db),
) -> SceneSchema:
    """Get a specific scene by number."""
    result = await db.execute(
        select(Scene).where(Scene.scene_number == scene_number)
    )
    scene = result.scalar_one_or_none()

    if not scene:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scene {scene_number} not found",
        )

    return SceneSchema.model_validate(scene)


@router.get("/production/overview", response_model=OverviewSchema)
async def get_overview(db: AsyncSession = Depends(get_db)) -> OverviewSchema:
    """Get production overview with system health."""
    result = await db.execute(select(Production).limit(1))
    production = result.scalar_one_or_none()

    if not production:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Production data not available. Run the seed script.",
        )

    # Get current scene
    current_scene = None
    if production.current_scene_number:
        scene_result = await db.execute(
            select(Scene).where(
                Scene.production_id == production.id,
                Scene.scene_number == production.current_scene_number,
            )
        )
        current_scene = scene_result.scalar_one_or_none()

    # Get system health from simulator
    sim = get_simulator()
    metrics = sim.get_current_metrics()

    from simulator.generator import MetricGenerator
    gen = MetricGenerator()
    health_scores = gen.calculate_system_health(metrics)

    overall_health = sum(health_scores.values()) / len(health_scores)

    # Count active incidents
    from models.database import Incident, IncidentStatus
    incident_count_result = await db.execute(
        select(Incident).where(
            Incident.production_id == production.id,
            Incident.status == IncidentStatus.ACTIVE,
        )
    )
    active_incidents = incident_count_result.scalars().all()

    system_health = SystemHealthSchema(
        cameras=health_scores.get("cameras", 100.0),
        ingest=health_scores.get("ingest", 100.0),
        storage=health_scores.get("storage", 100.0),
        network=health_scores.get("network", 100.0),
        editing=health_scores.get("editing", 100.0),
        overall=round(overall_health, 1),
        incident_active=sim.is_incident_active,
        scenario_type=sim.active_scenario_name,
    )

    return OverviewSchema(
        production=ProductionSummarySchema.model_validate(production),
        system_health=system_health,
        active_incident_count=len(active_incidents),
        current_scene=SceneSchema.model_validate(current_scene) if current_scene else None,
    )
