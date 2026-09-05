# Grafana Integration

Production Guardian uses Grafana Cloud as the primary telemetry store and observability engine. 
This is not a mock integration — we push actual telemetry data to Prometheus and query it via the official Grafana MCP server.

## 1. Metric Push (Telemetry Simulator)
Instead of a real film set, we generate synthetic metrics and push them to Grafana Cloud via Prometheus Remote Write.
The push happens every 15 seconds.

**Key Metrics Pushed:**
- `production_guardian_storage_utilization` (gauge)
- `production_guardian_ingest_throughput_gbps` (gauge)
- `production_guardian_disk_write_latency_ms` (gauge)
- `production_guardian_upload_queue_depth` (gauge)
- `production_guardian_packet_loss_pct` (gauge)
- `production_guardian_network_latency_ms` (gauge)
- `production_guardian_camera_errors_per_min` (gauge)

All metrics include the labels: `production="nightfall"`, `device="<name>"`.

## 2. Grafana Dashboard
We provide a pre-built JSON dashboard (`grafana/dashboards/production_overview.json`) that visualizes these metrics in real time. 
To use it:
1. Go to Grafana -> Dashboards -> New -> Import
2. Upload the JSON file from this repository.
3. Select your Prometheus data source.

## 3. Grafana MCP Server
The `InvestigationAgent` queries these metrics to diagnose incidents. It connects to the official `mcp-grafana` server, which proxies requests to Grafana Cloud.

**Tools Used by Agent:**
- `search_metrics`: Discovers available Prometheus metrics.
- `query_prometheus`: Runs PromQL queries (e.g., `avg_over_time(production_guardian_storage_utilization[5m])`).
- `get_alerts`: Checks for firing alerts in Alertmanager.

**Setup Requirements:**
You must have the `mcp-grafana` binary running locally on port 8080:
```bash
mcp-grafana --transport http --port 8080 --grafana-url <url> --grafana-token <service-account-token>
```
