 # Task 7 — Containerization of MCP Services and Persistent Metrics Infrastructure

## Objective

Transform the MCP benchmarking platform into a fully containerized, reproducible, and persistent experimental system with:

- Dockerized MCP servers and Agent Host
- Persistent structured logs (JSONL)
- Persistent time-series metrics using Prometheus
- Optional visualization with Grafana

This guarantees reproducible, resumable, and auditable experiments across machines and runs.

## Why this is required

- Without containerization results depend on developer machine configuration and are noisy.
- Without persistent metrics long experiments lose data, preventing cross-run comparison and trend analysis.

Task 7 enforces reproducible execution and durable observability.

## System architecture

```
                                    Locust
                                          │
                  ┌───────▼────────┐        /metrics        ┌────────────┐
                  │   Agent Host   │──────────────────────▶│ Prometheus │
                  │    (FastAPI)   │                       └──────┬─────┘
                  └───────┬────────┘                              │
                                          │ MCP (SSE)                               ▼
                  ┌───────▼────────┐                         ┌────────────┐
                  │   Echo Tool    │                         │  Grafana   │
                  │   (FastMCP)    │                         └────────────┘
                  └────────────────┘

All logs → persistent volume `./data/logs/`
All metrics → persistent volume `./data/prometheus/`
```

## Containerized components

- `echo_tool` — MCP tool server (FastMCP)
- `agent_host` — Agent pipeline + metrics endpoint (FastAPI)
- `prometheus` — Time-series metrics storage
- `grafana` — Metrics visualization (optional)

## Docker image / container design

### Agent Host

- Base image: `python:3.11-slim`
- Runs: FastAPI agent host and Prometheus metrics exporter
- Exposes: port `8000`
- Mounts: `/data/logs` (backed by host `./data/logs`)

### Echo Tool

- Base image: `python:3.11-slim`
- Runs: FastMCP server
- Exposes: port `8001`
- Mounts: `/data/logs`

## Docker networking

Containers use Docker service names for inter-service communication. Example:

- `agent_host` → `http://echo_tool:8001`

This avoids reliance on `localhost` and makes behavior identical in CI/cloud.

## Health checks & startup ordering

- `echo_tool` should expose a health check (example: `nc -z localhost 8001`) so other services wait until it is ready.
- `agent_host` should perform a handshake with the Echo Tool at startup and refuse to begin experiments until the tool is healthy.

## Resource constraints (example)

Compose/Swarm or orchestrator resource example:

```yaml
deploy:
      resources:
            limits:
                  cpus: "0.5"
                  memory: 512M
```

Use CPU and memory limits to run controlled saturation experiments (edge vs cloud profiles).

## Persistent logging

Mount `./data/logs` into each container and write append-only JSONL logs. Example output layout:

```
data/logs/
 ├── agent_host.jsonl
 ├── tool_executor.jsonl
 └── echo_tool.jsonl
```

Properties:

- Append-only and crash-safe
- Survives container restarts
- Usable for offline analysis and audits

## Persistent metrics (Prometheus)

Store Prometheus TSDB on host volume `./data/prometheus/` so metrics survive restarts and long experiments.

Example scrape config (Prometheus):

```yaml
scrape_configs:
      - job_name: 'agent_host'
            static_configs:
                  - targets: ['agent_host:8000']
            scrape_interval: 5s
```

Prometheus should be reachable at `http://localhost:9090` (default) when running locally.

## Grafana visualization

Grafana connects to the Prometheus data source and provides dashboards such as p50/p95/p99 latency, throughput, error rate, and saturation curves.

Default local URL: `http://localhost:3000` (if enabled).

## Reproducible execution

Start the full system with:

```bash
docker-compose up
```

This ensures identical dependencies, networking, and resource constraints.

## Verification procedure

1. Start the system:

```bash
docker-compose up
```

2. Confirm services:

- Agent Host docs: `http://localhost:8000/docs`
- Prometheus UI: `http://localhost:9090`
- Grafana UI: `http://localhost:3000`

3. Send a test request to the agent pipeline and verify:

- JSONL logs appear under `./data/logs/`
- Metrics are visible in Prometheus

## Scientific benefits

- Enables long-running and resumable experiments
- Enables cross-run and cross-environment comparisons
- Facilitates regression detection and failure analysis

## Summary

Task 7 turns the MCP benchmarking system into a containerized, reproducible, and observable platform suitable for rigorous scalability analysis, long-term experiments, and cross-environment comparisons.

---

*File updated to a structured documentation format.*