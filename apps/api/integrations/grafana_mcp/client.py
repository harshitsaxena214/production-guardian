"""
Grafana MCP Client.

This module provides a clean Python interface to the Grafana MCP server.
The MCP server (github.com/grafana/mcp-grafana) must be running separately.

Authentication is handled by the MCP server itself — it uses the
GRAFANA_URL and GRAFANA_SERVICE_ACCOUNT_TOKEN configured in the environment.

Transport: HTTP (streamable-http) — the MCP server is started with:
  mcp-grafana --transport http --port 8080

This client makes real HTTP calls to the actual MCP server.
No telemetry is fabricated here.
"""
import asyncio
import json
import time
from typing import Any

import httpx
import structlog

from config import get_settings
from core.exceptions import GrafanaMCPError, GrafanaMCPUnavailableError

logger = structlog.get_logger(__name__)
settings = get_settings()


class GrafanaMCPClient:
    """
    HTTP client for the Grafana MCP server.

    The Grafana MCP server implements the Model Context Protocol over HTTP.
    We call it using JSON-RPC style requests to the /mcp endpoint.

    This client is intentionally kept thin — it translates application-level
    queries into MCP tool calls and returns typed results.
    """

    def __init__(self, mcp_url: str | None = None) -> None:
        self._mcp_url = (mcp_url or settings.grafana_mcp_url).rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._session_id: str | None = None
        self._available: bool | None = None  # None = not yet checked

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def check_health(self) -> dict[str, Any]:
        """
        Check if the Grafana MCP server is available.

        Returns a status dict with 'available' bool and optional error message.
        """
        try:
            client = await self._get_client()
            # Try to initialize an MCP session
            response = await client.post(
                f"{self._mcp_url}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "production-guardian",
                            "version": "1.0.0",
                        },
                    },
                },
            )

            if response.status_code == 200:
                self._available = True
                result = response.json()
                return {
                    "available": True,
                    "server_info": result.get("result", {}).get("serverInfo", {}),
                    "grafana_url": settings.grafana_url,
                }
            else:
                self._available = False
                return {
                    "available": False,
                    "message": f"MCP server returned HTTP {response.status_code}",
                }

        except httpx.ConnectError:
            self._available = False
            return {
                "available": False,
                "message": f"Cannot connect to Grafana MCP at {self._mcp_url}. "
                           "Is mcp-grafana running? See docs/grafana.md for setup.",
            }
        except Exception as e:
            self._available = False
            return {"available": False, "message": str(e)}

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        request_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Call a Grafana MCP tool by name with given arguments.

        This is the core method — all other methods delegate here.
        Raises GrafanaMCPUnavailableError if the server is not reachable.
        Raises GrafanaMCPError on tool call errors.
        """
        start_time = time.monotonic()
        client = await self._get_client()

        payload = {
            "jsonrpc": "2.0",
            "id": request_id or int(time.time() * 1000),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        logger.debug(
            "grafana_mcp.tool_call",
            tool=tool_name,
            mcp_url=self._mcp_url,
        )

        try:
            response = await client.post(f"{self._mcp_url}/mcp", json=payload)
            duration_ms = int((time.monotonic() - start_time) * 1000)

            if response.status_code == 404:
                raise GrafanaMCPUnavailableError(
                    f"Grafana MCP server not found at {self._mcp_url}. "
                    "Please ensure mcp-grafana is running."
                )

            response.raise_for_status()
            result = response.json()

            if "error" in result:
                error = result["error"]
                raise GrafanaMCPError(
                    f"MCP tool error for {tool_name}: {error.get('message', 'Unknown error')}",
                    details={"code": error.get("code"), "tool": tool_name},
                )

            logger.info(
                "grafana_mcp.tool_success",
                tool=tool_name,
                duration_ms=duration_ms,
            )

            return result.get("result", {})

        except httpx.ConnectError as e:
            self._available = False
            raise GrafanaMCPUnavailableError(
                f"Cannot connect to Grafana MCP at {self._mcp_url}. "
                "The mcp-grafana server must be running. See docs/grafana.md.",
                details={"url": self._mcp_url, "original_error": str(e)},
            ) from e

        except httpx.TimeoutException as e:
            raise GrafanaMCPError(
                f"Grafana MCP tool call timed out: {tool_name}",
                details={"tool": tool_name},
            ) from e

    # -------------------------------------------------------------------------
    # High-level query methods
    # -------------------------------------------------------------------------

    async def query_prometheus_metric(
        self,
        query: str,
        start: str,
        end: str,
        step: str = "60s",
        datasource_uid: str = "grafanacloud-prom",
    ) -> dict[str, Any]:
        """
        Query a Prometheus metric via Grafana MCP.

        Args:
            query: PromQL expression (e.g., 'production_guardian_storage_utilization')
            start: ISO timestamp or relative (e.g., 'now-1h')
            end: ISO timestamp or 'now'
            step: Query resolution step
            datasource_uid: Grafana datasource UID

        Returns:
            MCP tool result containing metric data.

        Note: This is a REAL call to the actual Grafana MCP server.
        No data is fabricated.
        """
        return await self.call_tool(
            tool_name="query_prometheus",
            arguments={
                "datasourceUID": datasource_uid,
                "expr": query,
                "start": start,
                "end": end,
                "step": step,
            },
        )

    async def query_loki_logs(
        self,
        query: str,
        start: str,
        end: str,
        limit: int = 100,
        datasource_uid: str = "grafanacloud-logs",
    ) -> dict[str, Any]:
        """Query Loki logs via Grafana MCP."""
        return await self.call_tool(
            tool_name="query_loki",
            arguments={
                "datasourceUID": datasource_uid,
                "query": query,
                "start": start,
                "end": end,
                "limit": limit,
            },
        )

    async def list_datasources(self) -> list[dict[str, Any]]:
        """List available Grafana datasources."""
        result = await self.call_tool("list_datasources", {})
        content = result.get("content", [])
        if content and isinstance(content[0], dict):
            return content
        return []

    async def get_dashboard(self, uid: str) -> dict[str, Any]:
        """Get a Grafana dashboard by UID."""
        return await self.call_tool(
            "get_dashboard_by_uid",
            {"uid": uid},
        )

    async def search_dashboards(self, query: str = "") -> list[dict[str, Any]]:
        """Search Grafana dashboards."""
        result = await self.call_tool(
            "search_dashboards",
            {"query": query},
        )
        content = result.get("content", [])
        if content and isinstance(content[0], dict):
            return content
        return []

    async def get_alerts(self, state: str | None = None) -> list[dict[str, Any]]:
        """Get Grafana alert rules, optionally filtered by state."""
        args: dict[str, Any] = {}
        if state:
            args["state"] = state
        result = await self.call_tool("list_alert_rules", args)
        content = result.get("content", [])
        if isinstance(content, list):
            return content
        return []

    async def list_tools(self) -> list[dict[str, Any]]:
        """List all available MCP tools from the server."""
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self._mcp_url}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {},
                },
            )
            response.raise_for_status()
            result = response.json()
            return result.get("result", {}).get("tools", [])
        except Exception as e:
            logger.warning("grafana_mcp.list_tools_failed", error=str(e))
            return []


# ---------------------------------------------------------------------------
# Module-level singleton for dependency injection
# ---------------------------------------------------------------------------

_client: GrafanaMCPClient | None = None


def get_grafana_mcp_client() -> GrafanaMCPClient:
    """Get the global Grafana MCP client singleton."""
    global _client
    if _client is None:
        _client = GrafanaMCPClient()
    return _client
