"""
SQLAlchemy database models for Production Guardian.

These models represent the production database schema. Each table has
a corresponding Pydantic schema in the schemas/ directory for API I/O.
"""
import uuid
from datetime import datetime, time
from enum import Enum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ProductionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    WRAP = "WRAP"
    HIATUS = "HIATUS"


class ScenePriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SceneStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    AT_RISK = "AT_RISK"
    BLOCKED = "BLOCKED"


class IncidentSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class IncidentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INVESTIGATING = "INVESTIGATING"
    REMEDIATING = "REMEDIATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class RemediationStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentRunStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


class ScenarioType(str, Enum):
    STORAGE_SATURATION = "STORAGE_SATURATION"
    NETWORK_DEGRADATION = "NETWORK_DEGRADATION"
    CAMERA_FAILURE = "CAMERA_FAILURE"
    RENDER_BOTTLENECK = "RENDER_BOTTLENECK"
    MEDIA_INTEGRITY_FAILURE = "MEDIA_INTEGRITY_FAILURE"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Production(Base):
    """Represents a film production (e.g., NIGHTFALL)."""
    __tablename__ = "productions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    genre: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    production_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ProductionStatus.ACTIVE
    )
    shoot_window_start: Mapped[str] = mapped_column(String(10), nullable=False, default="08:00")
    shoot_window_end: Mapped[str] = mapped_column(String(10), nullable=False, default="18:00")
    current_scene_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    primary_location: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    scenes: Mapped[list["Scene"]] = relationship("Scene", back_populates="production")
    incidents: Mapped[list["Incident"]] = relationship("Incident", back_populates="production")


class Scene(Base):
    """Represents a scene in the production schedule."""
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    production_id: Mapped[str] = mapped_column(
        String, ForeignKey("productions.id"), nullable=False
    )
    scene_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    location: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    priority: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ScenePriority.MEDIUM
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=SceneStatus.SCHEDULED
    )
    estimated_footage_gb: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    editorial_deadline: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Dependent scene numbers (JSON array of scene numbers)
    dependent_scene_numbers: Mapped[list[int]] = mapped_column(
        JSON, nullable=False, default=list
    )
    shoot_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_duration_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    production: Mapped["Production"] = relationship("Production", back_populates="scenes")


class Incident(Base):
    """Represents an infrastructure incident affecting production."""
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    production_id: Mapped[str] = mapped_column(
        String, ForeignKey("productions.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    severity: Mapped[str] = mapped_column(
        String(50), nullable=False, default=IncidentSeverity.MEDIUM
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=IncidentStatus.ACTIVE
    )
    scenario_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Analysis results (populated by agent)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    affected_systems: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    affected_scene_numbers: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)

    # Production impact
    production_impact: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    estimated_delay_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    deadline_at_risk: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    investigated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    production: Mapped["Production"] = relationship("Production", back_populates="incidents")
    remediation_actions: Mapped[list["RemediationAction"]] = relationship(
        "RemediationAction", back_populates="incident"
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship("AgentRun", back_populates="incident")


class RemediationAction(Base):
    """Represents a recommended remediation action for an incident."""
    __tablename__ = "remediation_actions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    incident_id: Mapped[str] = mapped_column(
        String, ForeignKey("incidents.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False, default="SIMULATED")
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, default="LOW")
    expected_benefit: Mapped[str] = mapped_column(String(50), nullable=False, default="HIGH")
    expected_recovery_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=RemediationStatus.PENDING
    )
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verification_result: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident", back_populates="remediation_actions")


class AgentRun(Base):
    """Tracks a Gemini agent investigation run."""
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    incident_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("incidents.id"), nullable=True
    )
    run_type: Mapped[str] = mapped_column(
        String(100), nullable=False, default="INVESTIGATION"
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=AgentRunStatus.RUNNING
    )

    # Events are appended as the run progresses (list of event dicts)
    events: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)

    # Final structured result
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Tool call log for transparency
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    incident: Mapped["Incident | None"] = relationship("Incident", back_populates="agent_runs")


class TelemetrySnapshot(Base):
    """Periodic telemetry snapshots for trending and audit."""
    __tablename__ = "telemetry_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    scenario_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_incident_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
