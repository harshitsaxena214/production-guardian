# Architecture

Production Guardian uses a modern, modular architecture designed to bridge the gap between infrastructure observability (Grafana) and physical production operations (cameras, storage, rendering, editing).

## System Components

### 1. Telemetry Simulator (`/simulator`)
Since we don't have a real film set running for the hackathon, we built a deterministic telemetry engine.
- **State Machine**: Normal, Incident Active, Remediating, Recovered
- **Metric Generator**: Uses baseline noise (Gaussian) with causal relationships (e.g., storage filling up causes latency spikes, which causes throughput drops, which causes queue buildups).
- **Pusher**: Sends the generated metrics to Grafana Cloud via Prometheus Remote Write (protobuf + snappy).

### 2. FastAPI Backend (`/apps/api`)
The core orchestrator.
- **PostgreSQL Database**: Holds physical production context (e.g., "NIGHTFALL is shooting Scene 42, which requires 680GB of ingest before the 22:00 editorial deadline").
- **FastAPI Routes**: Provides REST endpoints for the frontend.
- **SSE Streaming**: Streams agent reasoning to the UI in real-time.

### 3. Agent Architecture (`/apps/api/agents`)
We use the **Google Agent Development Kit (ADK)** and **Gemini 1.5 Pro** to orchestrate four agents:

1. **Orchestrator Agent**: Manages state, streams UI events, and delegates tasks.
2. **Investigation Agent**: The diagnostic specialist. Uses the Grafana MCP integration to query live Prometheus metrics, evaluate thresholds, and deduce root causes.
3. **Production Impact Agent**: Bridges the IT/Production gap. It uses deterministic math to calculate exactly how much the current ingest rate degradation will delay the editorial pipeline.
4. **Remediation Agent**: Proposes safe, actionable remediation steps.

### 4. Grafana MCP Integration
Instead of fake mock tools, we use the official `mcp-grafana` Go binary.
- Our FastAPI backend implements an MCP client that speaks JSON-RPC over stdio/HTTP.
- The Investigation Agent uses these exact MCP tools to query Grafana Cloud.

### 5. Next.js Frontend (`/apps/web`)
A modern App Router (React 18, Tailwind CSS v4, Lucide Icons) dashboard for the producer or DIT (Digital Imaging Technician). It visualizes the current production state, active incidents, and agent reasoning.

## The Data Pipeline

```
[Simulator] -> (Prometheus Remote Write) -> [Grafana Cloud]
                                                  |
                                             (MCP JSON-RPC)
                                                  |
                                            [FastAPI Backend]
                                                  |
                                          (Server-Sent Events)
                                                  |
                                          [Next.js Frontend]
```
