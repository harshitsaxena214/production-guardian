# Production Guardian — Demo Guide

> **For hackathon judges: this document explains how to run the complete demo.**

---

## Prerequisites

Before the demo, ensure you have:

- [ ] Google AI Studio API key (from [aistudio.google.com](https://aistudio.google.com/app/apikey))
- [ ] Grafana Cloud account with a stack
- [ ] `mcp-grafana` binary installed
- [ ] `.env` configured (copy from `.env.example`)
- [ ] PostgreSQL running (via Docker Compose)
- [ ] All services started (see [docs/development.md](development.md))

---

## Starting Services

```bash
# Terminal 1: PostgreSQL
docker-compose up postgres -d

# Terminal 2: Grafana MCP
mcp-grafana --transport http --port 8080 \
  --grafana-url $GRAFANA_URL \
  --grafana-token $GRAFANA_SERVICE_ACCOUNT_TOKEN

# Terminal 3: Backend API
cd apps/api
uvicorn main:app --reload --port 8000

# Terminal 4: Simulator
python simulator/service.py

# Terminal 5: Frontend
cd apps/web
npm run dev
```

Open: `http://localhost:3000`

---

## Demo Steps (Exact Click Sequence)

### Step 1: Overview

**What judges see:**

```
PRODUCTION GUARDIAN    ● DEMO MODE

NIGHTFALL
● LIVE  Production Day 47  Scene 42  Stage 7

SYSTEM HEALTH
Cameras  98%  ✓ HEALTHY
Ingest   97%  ✓ HEALTHY
Storage  71%  ✓ HEALTHY
Network  99%  ✓ HEALTHY
Editing  92%  ✓ HEALTHY
```

**All systems healthy.** No active incidents.

---

### Step 2: Simulate Incident

1. Navigate to **Telemetry** tab
2. Under **Incident Simulator**, select: `Storage Saturation`
3. Click: **[ SIMULATE INCIDENT ]**

**What happens:**
- Simulator state changes to INCIDENT_ACTIVE
- Telemetry begins degrading (pushed to Grafana every 15 seconds)
- An incident record is created in the database

**Expected response:**

```json
{
  "incident_id": "uuid",
  "scenario": "STORAGE_SATURATION",
  "message": "Incident scenario activated. Telemetry is being pushed to Grafana Cloud.",
  "status": "ACTIVE"
}
```

---

### Step 3: Watch Telemetry Degrade

Navigate to **Telemetry** tab. Watch over the next 60-90 seconds:

| Metric | Before | After (full) |
|--------|--------|-----|
| Storage Utilization | ~68% | ~96% |
| Write Latency | ~40ms | ~136ms |
| Ingest Throughput | ~1.85 GB/s | ~0.68 GB/s |
| Upload Queue | ~18 frames | ~1,240 frames |
| Packet Loss | ~0.01% | ~0.01% (NORMAL) |
| Camera Errors | ~0.05/min | ~0.08/min (NORMAL) |

**The asymmetry is intentional**: network and cameras are fine. Storage and ingest are degraded.

Also check **Grafana Cloud** — metrics should be appearing in real time.

---

### Step 4: Active Incident Appears

Navigate back to **Overview**. An incident card should appear:

```
🚨 SCENE 42 INGESTION AT RISK

Storage Saturation on INGEST-01
Severity: CRITICAL
Started: [timestamp]

[ INVESTIGATE WITH AGENT ]
```

---

### Step 5: Agent Investigation

Click: **[ INVESTIGATE WITH AGENT ]**

**Watch the agent activity panel stream in real time:**

```
✓ Understanding incident context
✓ Connecting to Grafana MCP
✓ Connected to Grafana MCP
✓ Querying Storage Utilization      → 96.2% (+41.5%) [CRITICAL]
✓ Querying Disk Write Latency Ms    → 134ms (+235%) [CRITICAL]
✓ Querying Disk Iops                → 4,812 (-59.9%) [HIGH]
✓ Querying Ingest Throughput Gbps   → 0.68 GB/s (-63.2%) [CRITICAL]
✓ Querying Upload Queue Depth       → 1,204 (+6589%) [CRITICAL]
✓ Querying Failed Uploads Per Min   → 27.3 (+13550%) [CRITICAL]
✓ Querying Network Latency Ms       → 2.5ms (+4.2%) [NORMAL]
✓ Querying Packet Loss Pct          → 0.012% (+20%) [NORMAL]
✓ Querying Camera Errors Per Min    → 0.06/min (+20%) [NORMAL]
✓ Checking active alerts
✓ Analyzing evidence with Gemini
✓ Root cause identified: Storage saturation on INGEST-01
✓ Retrieving production context
✓ Production impact calculated
✓ Remediation recommendation generated
✓ Investigation complete
```

**These events are REAL** — each ✓ corresponds to an actual tool call to Grafana MCP or Gemini.

---

### Step 6: Review Investigation Results

The Investigation page shows:

```
ROOT CAUSE
Storage saturation on INGEST-01. Disk utilization exceeding capacity
threshold, causing write I/O contention.

CONFIDENCE: 94%

EVIDENCE
Storage Utilization:    96.2%    Baseline: 68.0%    ANOMALOUS (+41.5%)
Write Latency:          134ms    Baseline: 40ms     ANOMALOUS (+235%)
Ingest Throughput:      0.68GB/s Baseline: 1.85GB/s ANOMALOUS (-63.2%)
Upload Queue:           1,204    Baseline: 18       ANOMALOUS (+6,589%)
Network Packet Loss:    0.012%   Baseline: 0.01%    NORMAL
Camera Errors:          0.06/min Baseline: 0.05/min NORMAL
```

**Gemini correctly identified the storage cause and eliminated network/camera as root causes.**

---

### Step 7: Production Impact

Navigate to **Production Impact** tab:

```
SCENE 42 — POINT OF NO RETURN (CRITICAL)

Current Ingest Rate:   0.68 GB/s
Required Rate:         1.85 GB/s
Estimated Footage:     680 GB
Footage Ingested:      136 GB (20%)
Footage Remaining:     544 GB

Editorial Deadline:    22:00
Projected Completion:  ~23:12  ⚠️
Projected Delay:       ~72 minutes
```

**Dependency flow:**

```
INGEST-01
    ↓ ⚠️
SCENE 42 FOOTAGE (delayed)
    ↓
EDITORIAL INGEST
    ↓
SCENE 42 EDIT
    ↓ ⚠️ blocked
SCENE 43 ASSEMBLY
    ↓
DAILY DELIVERY ⚠️ at risk
```

---

### Step 8: What If We Do Nothing?

Click: **[ WHAT IF WE DO NOTHING? ]**

```
PROJECTED CONSEQUENCES

18 min    Scene 42 ingestion failure risk
          HIGH — At current degraded rate, ingest will fall critically behind

72 min    Editorial delivery delay
          CRITICAL — Editorial deadline missed by ~72 minutes

108 min   Scene 43 assembly at risk
          HIGH — Dependent scenes cannot begin assembly

~3 hours  Daily delivery package failure
          CRITICAL — End-of-day delivery will be missed

Probability of production failure: 87%
```

---

### Step 9: Review Remediation

The Remediation panel shows:

```
⚠️ SIMULATED REMEDIATION (Demo)

RECOMMENDED ACTIONS

1. Free 180 GB from completed proxy files on INGEST-01
   Risk: LOW  |  Expected Benefit: HIGH  |  Recovery: ~11 min

2. Move non-critical proxy data to archive storage (NAS-01 cold tier)
   Risk: LOW  |  Expected Benefit: HIGH

3. Prioritize Scene 42 footage in ingest queue
   Risk: LOW  |  Expected Benefit: HIGH

4. Pause non-critical background ingest jobs
   Risk: LOW  |  Expected Benefit: MEDIUM

5. Re-evaluate ingest capacity in 5 minutes
   Risk: LOW  |  Expected Benefit: LOW

[ APPROVE REMEDIATION ]    [ REJECT ]
```

---

### Step 10: Approve and Simulate

Click: **[ APPROVE REMEDIATION ]**

Then: **[ SIMULATE ]** (or automatic after approval)

**What happens:**
- Simulator transitions to REMEDIATING
- Telemetry begins recovering (Grafana shows recovery curve)
- UI shows progress

---

### Step 11: Verification

After ~2 minutes (simulated recovery):

```
✅ RECOVERY VERIFIED

Production Risk:     CRITICAL → LOW
Scene 42:            ON TRACK

Storage Utilization: 96% → 61%
Write Latency:       136ms → 38ms
Ingest Throughput:   0.68 → 1.92 GB/s
Upload Queue:        1,204 → 22 frames

Editorial Delay Avoided: ~72 minutes
```

---

## Resetting the Demo

Click **[ RESET DEMO ]** in the Telemetry tab.

Or via API:
```bash
curl -X POST http://localhost:8000/api/incidents/reset
```

This:
- Resets simulator to normal
- Closes all active incidents
- Returns system to healthy baseline

---

## Troubleshooting

### Grafana MCP unavailable
```
✓ Grafana MCP unavailable: Cannot connect at http://localhost:8080
  Using simulator state for investigation [DEMO]
```
The investigation still works — uses simulator data instead of live Grafana.
To fix: ensure `mcp-grafana` is running on port 8080.

### Gemini not responding
Check `GOOGLE_API_KEY` in `.env`. The investigation falls back to deterministic analysis.

### Database empty
Run: `python database/seed/seed.py`

### Metrics not in Grafana
Check `GRAFANA_PROMETHEUS_REMOTE_WRITE_URL`, `GRAFANA_PROMETHEUS_USER_ID`, `GRAFANA_PROMETHEUS_API_KEY` in `.env`.

---

*Production Guardian — Agentic Cinema Hackathon / Grafana Labs Track*
