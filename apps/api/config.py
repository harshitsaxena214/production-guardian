"""
Application configuration using Pydantic Settings.

All configuration is read from environment variables. See .env.example for
documentation on each variable.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------------------------------------------------------------------
    # Application
    # ---------------------------------------------------------------------------
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    frontend_url: str = "http://localhost:3000"
    secret_key: str = "change-me-in-production"

    # ---------------------------------------------------------------------------
    # Database
    # ---------------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://guardian:guardian@localhost:5432/production_guardian"
    )
    database_sync_url: str = Field(
        default="postgresql://guardian:guardian@localhost:5432/production_guardian"
    )

    # ---------------------------------------------------------------------------
    # Google AI / Gemini
    # ---------------------------------------------------------------------------
    google_api_key: str = ""
    gemini_model: str = "gemini-1.5-pro"
    google_genai_use_vertexai: bool = False
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"

    # ---------------------------------------------------------------------------
    # Grafana Cloud
    # ---------------------------------------------------------------------------
    grafana_url: str = ""
    grafana_service_account_token: str = ""
    grafana_prometheus_remote_write_url: str = ""
    grafana_prometheus_user_id: str = ""
    grafana_prometheus_api_key: str = ""
    grafana_loki_url: str = ""
    grafana_loki_user_id: str = ""

    # ---------------------------------------------------------------------------
    # Grafana MCP
    # ---------------------------------------------------------------------------
    grafana_mcp_url: str = "http://localhost:8080"
    grafana_mcp_transport: Literal["http", "stdio"] = "http"

    # ---------------------------------------------------------------------------
    # Simulator
    # ---------------------------------------------------------------------------
    simulator_push_interval_seconds: int = 15
    simulator_auto_start: bool = False
    simulator_default_scenario: str = "STORAGE_SATURATION"

    # ---------------------------------------------------------------------------
    # Telemetry Labels
    # ---------------------------------------------------------------------------
    production_name: str = "nightfall"
    production_environment: str = "stage-7"

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"log_level must be one of {valid}")
        return upper


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
