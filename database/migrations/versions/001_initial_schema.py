"""Initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Productions table
    op.create_table(
        'productions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('genre', sa.String(100), nullable=False, server_default=''),
        sa.Column('production_day', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(50), nullable=False, server_default='ACTIVE'),
        sa.Column('shoot_window_start', sa.String(10), nullable=False, server_default='08:00'),
        sa.Column('shoot_window_end', sa.String(10), nullable=False, server_default='18:00'),
        sa.Column('current_scene_number', sa.Integer(), nullable=True),
        sa.Column('primary_location', sa.String(255), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # Scenes table
    op.create_table(
        'scenes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('production_id', sa.String(), nullable=False),
        sa.Column('scene_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(500), nullable=False, server_default=''),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('location', sa.String(255), nullable=False, server_default=''),
        sa.Column('priority', sa.String(50), nullable=False, server_default='MEDIUM'),
        sa.Column('status', sa.String(50), nullable=False, server_default='SCHEDULED'),
        sa.Column('estimated_footage_gb', sa.Float(), nullable=False, server_default='0'),
        sa.Column('editorial_deadline', sa.String(10), nullable=True),
        sa.Column('dependent_scene_numbers', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('shoot_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('estimated_duration_hours', sa.Float(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['production_id'], ['productions.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Incidents table
    op.create_table(
        'incidents',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('production_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('severity', sa.String(50), nullable=False, server_default='MEDIUM'),
        sa.Column('status', sa.String(50), nullable=False, server_default='ACTIVE'),
        sa.Column('scenario_type', sa.String(100), nullable=True),
        sa.Column('root_cause', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('affected_systems', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('affected_scene_numbers', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('production_impact', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('estimated_delay_minutes', sa.Float(), nullable=True),
        sa.Column('deadline_at_risk', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('investigated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['production_id'], ['productions.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Remediation actions table
    op.create_table(
        'remediation_actions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('incident_id', sa.String(), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('action_type', sa.String(100), nullable=False, server_default='SIMULATED'),
        sa.Column('risk_level', sa.String(50), nullable=False, server_default='LOW'),
        sa.Column('expected_benefit', sa.String(50), nullable=False, server_default='HIGH'),
        sa.Column('expected_recovery_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0'),
        sa.Column('details', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(50), nullable=False, server_default='PENDING'),
        sa.Column('approved_by', sa.String(255), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verification_result', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Agent runs table
    op.create_table(
        'agent_runs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('incident_id', sa.String(), nullable=True),
        sa.Column('run_type', sa.String(100), nullable=False, server_default='INVESTIGATION'),
        sa.Column('status', sa.String(50), nullable=False, server_default='RUNNING'),
        sa.Column('events', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('result', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('tool_calls', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Telemetry snapshots table
    op.create_table(
        'telemetry_snapshots',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('scenario_type', sa.String(100), nullable=True),
        sa.Column('metrics', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('is_incident_active', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )

    # Indexes for common queries
    op.create_index('ix_incidents_production_id', 'incidents', ['production_id'])
    op.create_index('ix_incidents_status', 'incidents', ['status'])
    op.create_index('ix_scenes_production_id', 'scenes', ['production_id'])
    op.create_index('ix_scenes_scene_number', 'scenes', ['scene_number'])
    op.create_index('ix_agent_runs_incident_id', 'agent_runs', ['incident_id'])
    op.create_index('ix_remediation_incident_id', 'remediation_actions', ['incident_id'])


def downgrade() -> None:
    op.drop_table('telemetry_snapshots')
    op.drop_table('agent_runs')
    op.drop_table('remediation_actions')
    op.drop_table('incidents')
    op.drop_table('scenes')
    op.drop_table('productions')
