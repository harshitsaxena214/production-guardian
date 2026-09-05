"""Custom exceptions for Production Guardian."""
from typing import Any


class ProductionGuardianError(Exception):
    """Base exception for all application errors."""
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(ProductionGuardianError):
    """Resource not found."""
    pass


class ConflictError(ProductionGuardianError):
    """Resource conflict (e.g., incident already active)."""
    pass


class AgentError(ProductionGuardianError):
    """Gemini agent execution error."""
    pass


class GrafanaMCPError(ProductionGuardianError):
    """Grafana MCP integration error."""
    pass


class GrafanaMCPUnavailableError(GrafanaMCPError):
    """Grafana MCP server is unavailable."""
    pass


class SimulatorError(ProductionGuardianError):
    """Telemetry simulator error."""
    pass


class RemediationError(ProductionGuardianError):
    """Remediation action error."""
    pass


class ValidationError(ProductionGuardianError):
    """Input validation error."""
    pass
