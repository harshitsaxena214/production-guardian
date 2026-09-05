# Production Guardian

> **Turn production telemetry into production decisions.**

Production Guardian is an AI-powered autonomous operations system for film and media production. It monitors synthetic production infrastructure telemetry, investigates incidents through **Grafana Cloud MCP**, uses **Google Gemini + Google ADK** to reason over technical and production data, predicts the impact on film production, recommends remediation, waits for human approval, and verifies recovery.

---

## 🎬 The Problem

Traditional infrastructure monitoring tells engineers:

> *"Disk utilization is 96%."*

But a film producer needs to know:

> *"Will this prevent today's footage from reaching editorial?"*

**Production Guardian connects technical telemetry to production context.**

---

## ✨ What It Does

For a film production called **NIGHTFALL** on **Production Day 47**, with **Scene 42** as the critical workflow:

1. **Detects** infrastructure incidents from telemetry
2. **Investigates** via Grafana Cloud MCP (real tool calls, no fakes)
3. **Correlates** evidence across storage, network, camera, and editing systems
4. **Diagnoses** root cause using Google Gemini
5. **Predicts** impact on Scene 42 editorial deadline
6. **Recommends** specific remediation actions
7. **Waits** for human approval
8. **Simulates** safe remediation
9. **Verifies** recovery via Grafana

---

## 🏗️ Architecture

```mermaid
flowchart TD
    Producer["👤 Producer / DIT"] --> Web["🖥️ Production Guardian UI\n(Next.js 14)"]
    Web --> API["⚡ FastAPI Backend\n(Python)"]
    API --> Orchestrator["🤖 Orchestrator Agent\n(Google ADK + Gemini)"]
    
    Orchestrator --> InvAgent["🔍 Investigation Agent\n(Gemini + Grafana Tools)"]
    Orchestrator --> ImpactAgent["🎬 Production Impact Agent\n(Gemini + PostgreSQL)"]
    Orchestrator --> RemAgent["🛠️ Remediation Agent\n(Gemini)"]
    
    InvAgent --> GrafanaMCP["🔌 Grafana MCP Client\n(Official MCP Integration)"]
    GrafanaMCP --> GrafanaCloud["☁️ Grafana Cloud\n(Prometheus + Loki)"]
    
    Simulator["⚙️ Telemetry Simulator\n(5 incident scenarios)"] --> GrafanaCloud
    
    ImpactAgent --> PostgreSQL[("🗄️ PostgreSQL\nProduction data")]
    API --> PostgreSQL
    
    RemAgent --> SimulatedRem["✅ Simulated Remediation\n(Labeled as simulation)"]
    SimulatedRem --> Simulator
```

---

## 🤖 Agent Architecture

```
OrchestratorAgent (Google ADK LlmAgent)
├── InvestigationAgent
│   ├── query_metric()        → Grafana MCP → Grafana Cloud
│   ├── compare_baseline()    → Grafana MCP → 24h comparison
│   ├── query_logs()          → Grafana MCP → Loki
│   └── get_active_alerts()   → Grafana MCP → Alertmanager
│
├── ProductionImpactAgent
│   ├── get_production_context()   → PostgreSQL
│   ├── get_scene_context()        → PostgreSQL
│   └── calculate_impact()         → Deterministic math
│
└── RemediationAgent
    ├── generate_recommendations() → Gemini
    ├── simulate_remediation()     → Simulator state
    └── verify_recovery()          → Grafana MCP
```

---

## 🛠️ Technology Stack

| Layer | Technology |
|-------|-----------|
| AI | Google Gemini 1.5 Pro + Google ADK |
| Observability | Grafana Cloud (Prometheus + Loki) |
| MCP Integration | Official `mcp-grafana` binary |
| Backend | Python 3.11+ / FastAPI / Pydantic |
| Frontend | Next.js 14 App Router / TypeScript / Tailwind CSS |
| Charts | Recharts |
| Database | PostgreSQL + SQLAlchemy + Alembic |
| Telemetry | Prometheus Remote Write |
| Deployment | Google Cloud Run (documented) |

---

## 📦 Project Structure

```
production-guardian/
├── apps/
│   ├── api/                    # FastAPI backend
│   │   ├── main.py             # Entry point
│   │   ├── config.py           # Pydantic Settings
│   │   ├── agents/             # Gemini/ADK agents
│   │   ├── integrations/
│   │   │   └── grafana_mcp/    # Official MCP integration
│   │   ├── api/routes/         # FastAPI endpoints
│   │   ├── models/             # SQLAlchemy models
│   │   └── schemas/            # Pydantic schemas
│   │
│   └── web/                    # Next.js 14 frontend
│       ├── app/                # App Router pages
│       └── components/         # React components
│
├── simulator/                  # Telemetry simulator
│   ├── engine.py               # State machine
│   ├── generator.py            # Metric generation
│   ├── pusher.py               # Prometheus remote write
│   └── scenarios/              # 5 incident scenarios
│
├── database/
│   ├── migrations/             # Alembic migrations
│   └── seed/                   # Demo data seeder
│
├── grafana/
│   └── dashboards/             # Dashboard JSON
│
├── tests/                      # Unit + integration tests
├── docs/                       # Documentation
├── .env.example                # Configuration template
└── docker-compose.yml
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (or Docker)
- Google AI Studio API key
- Grafana Cloud account

### 1. Clone and Configure

```bash
git clone https://github.com/your-org/production-guardian
cd production-guardian
cp .env.example .env
# Edit .env with your credentials
```

### 2. Start PostgreSQL

```bash
docker-compose up postgres -d
```

### 3. Backend Setup

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 4. Run Migrations

```bash
cd apps/api
alembic upgrade head
```

### 5. Seed Database

```bash
python ../../database/seed/seed.py
```

### 6. Start Grafana MCP

```bash
# Install mcp-grafana: https://github.com/grafana/mcp-grafana/releases
mcp-grafana --transport http --port 8080 \
  --grafana-url $GRAFANA_URL \
  --grafana-token $GRAFANA_SERVICE_ACCOUNT_TOKEN
```

### 7. Start Backend

```bash
cd apps/api
uvicorn main:app --reload --port 8000
```

### 8. Start Simulator

```bash
# In a new terminal
cd production-guardian
python simulator/service.py
```

### 9. Start Frontend

```bash
cd apps/web
npm install
npm run dev
```

### 10. Open Application

```
http://localhost:3000
```

---

## 🔑 Environment Variables

See [.env.example](.env.example) for all required variables with documentation.

Key variables:

| Variable | Purpose |
|----------|---------|
| `GOOGLE_API_KEY` | Google AI Studio API key for Gemini |
| `GEMINI_MODEL` | Gemini model (default: `gemini-1.5-pro`) |
| `GRAFANA_URL` | Your Grafana Cloud stack URL |
| `GRAFANA_SERVICE_ACCOUNT_TOKEN` | Grafana service account token |
| `GRAFANA_MCP_URL` | Grafana MCP server URL |
| `GRAFANA_PROMETHEUS_REMOTE_WRITE_URL` | Prometheus remote write endpoint |
| `DATABASE_URL` | PostgreSQL async connection string |

---

## 🎭 Incident Scenarios

| Scenario | Primary Signal | Counter-indicators |
|----------|---------------|-------------------|
| **Storage Saturation** | `storage_utilization` ↑ → `write_latency` ↑ → `ingest_throughput` ↓ | Network, cameras normal |
| **Network Degradation** | `packet_loss` ↑, `latency` ↑, `bandwidth` ↓ | Storage, cameras normal |
| **Camera Failure** | `camera_temperature` ↑ → `recording_errors` ↑ → `dropped_frames` ↑ | Storage, network normal |
| **Render Bottleneck** | `gpu_usage` ↑ → `render_queue` ↑ → `render_latency` ↑ | Storage, network, cameras normal |
| **Media Integrity** | `checksum_errors` ↑ → `failed_uploads` ↑ → `retry_rate` ↑ | Network, cameras normal |

---

## 🎬 Demo Flow

See [docs/demo.md](docs/demo.md) for the complete demo walkthrough.

**Summary:**
1. Open Production Guardian → See NIGHTFALL dashboard
2. Select "Storage Saturation" → Click "Simulate Incident"
3. Watch metrics degrade in real time (pushed to Grafana)
4. Click "Investigate with Agent" → Watch Gemini investigate via Grafana MCP
5. See root cause: "Storage saturation on INGEST-01 (94% confidence)"
6. See production impact: "47-minute editorial delay for Scene 42"
7. Click "What if we do nothing?" → See downstream cascade
8. Review and approve remediation
9. Watch telemetry recover
10. Gemini verifies recovery: "CRITICAL → LOW"

---

## 🧪 Testing

```bash
# Unit tests
cd production-guardian
python -m pytest tests/unit/ -v

# Integration tests (requires running PostgreSQL)
python -m pytest tests/integration/ -v

# Frontend type check
cd apps/web
npx tsc --noEmit

# Frontend lint
npx eslint . --max-warnings 0
```

---

## 🔒 Security

- All Grafana and Gemini credentials remain **server-side only**
- Frontend never sees API keys or tokens
- All remediation operations are **simulated** — no real systems modified
- Parameterized database queries throughout
- Input validation on all API endpoints

---

## ⚠️ Limitations

- This is a hackathon demo using **synthetic telemetry** for NIGHTFALL
- Remediation is **simulated** — labeled clearly in the UI
- Production impact calculations use **demo-calibrated parameters**
- The MCP integration requires the `mcp-grafana` binary to be running

---

## 🔮 Future Work

- Real production system integrations (media servers, camera systems)
- Multi-production support
- Historical incident analysis
- Predictive alerting before incidents occur
- Integration with post-production workflow systems

---

## 📄 License

MIT License — see [LICENSE](LICENSE)

---

*Built for the Agentic Cinema Hackathon — Grafana Labs Track*
