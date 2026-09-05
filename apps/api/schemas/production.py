"""Pydantic schemas for Production and Scene API responses."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SceneSchema(BaseModel):
    """Scene data for API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    production_id: str
    scene_number: int
    title: str
    description: str
    location: str
    priority: str
    status: str
    estimated_footage_gb: float
    editorial_deadline: str | None
    dependent_scene_numbers: list[int]
    shoot_date: datetime | None
    estimated_duration_hours: float
    created_at: datetime
    updated_at: datetime


class ProductionSchema(BaseModel):
    """Production data for API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    display_name: str
    genre: str
    production_day: int
    status: str
    shoot_window_start: str
    shoot_window_end: str
    current_scene_number: int | None
    primary_location: str
    scenes: list[SceneSchema] = []
    created_at: datetime
    updated_at: datetime


class ProductionSummarySchema(BaseModel):
    """Minimal production info for overview displays."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    display_name: str
    genre: str
    production_day: int
    status: str
    shoot_window_start: str
    shoot_window_end: str
    current_scene_number: int | None
    primary_location: str


class SystemHealthSchema(BaseModel):
    """System health summary across all infrastructure categories."""
    cameras: float = Field(ge=0, le=100, description="Camera system health percentage")
    ingest: float = Field(ge=0, le=100, description="Ingest system health percentage")
    storage: float = Field(ge=0, le=100, description="Storage system health percentage")
    network: float = Field(ge=0, le=100, description="Network health percentage")
    editing: float = Field(ge=0, le=100, description="Editing system health percentage")
    overall: float = Field(ge=0, le=100, description="Overall system health percentage")
    incident_active: bool = False
    scenario_type: str | None = None


class OverviewSchema(BaseModel):
    """Combined overview for the dashboard."""
    production: ProductionSummarySchema
    system_health: SystemHealthSchema
    active_incident_count: int
    current_scene: SceneSchema | None
