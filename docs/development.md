# Development Guide

This guide covers how to set up the development environment for Production Guardian.

## Prerequisites
- Node.js 18+
- Python 3.11+
- Docker (for PostgreSQL)
- Grafana Cloud Account
- Google AI Studio API Key

## 1. Environment Setup
Copy the example environment file and fill in your details:
```bash
cp .env.example .env
```

You will need:
- `GOOGLE_API_KEY`: From [Google AI Studio](https://aistudio.google.com/app/apikey)
- `GRAFANA_URL`: Your Grafana Cloud instance (e.g., `https://your-stack.grafana.net`)
- `GRAFANA_SERVICE_ACCOUNT_TOKEN`: A service account token with viewer/editor permissions.
- `GRAFANA_PROMETHEUS_REMOTE_WRITE_URL`: Found in Grafana Cloud under Details -> Prometheus.
- `GRAFANA_PROMETHEUS_USER_ID`: The username for Prometheus Remote Write.
- `GRAFANA_PROMETHEUS_API_KEY`: A Grafana API key (Cloud Access Policy) with metrics write permissions.

## 2. Infrastructure (PostgreSQL)
Start the local database:
```bash
docker-compose up postgres -d
```

## 3. Grafana MCP Server
We use the official Grafana MCP server. Download it from the [Grafana MCP releases](https://github.com/grafana/mcp-grafana/releases).

Run it on port 8080:
```bash
mcp-grafana --transport http --port 8080 --grafana-url $GRAFANA_URL --grafana-token $GRAFANA_SERVICE_ACCOUNT_TOKEN
```

## 4. Backend Setup
Set up the Python virtual environment and run migrations:
```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

alembic upgrade head
python ../../database/seed/seed.py

# Start the API
uvicorn main:app --reload --port 8000
```

## 5. Telemetry Simulator
In a separate terminal, start the telemetry push service:
```bash
python simulator/service.py
```
This will push metrics to your Grafana Cloud instance every 15 seconds.

## 6. Frontend Setup
Start the Next.js app:
```bash
cd apps/web
npm install
npm run dev
```

The application is now available at `http://localhost:3000`.

## Code Style
- Python: Formatted with `black` and linted with `ruff`.
- TypeScript/React: Formatted/linted with `eslint`.
