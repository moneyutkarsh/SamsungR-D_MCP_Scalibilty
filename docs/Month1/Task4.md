 # Task 4 — Containerization, Observability, and Reproducible Experiment Infrastructure

## Objective

Transform the MCP benchmarking system into a reproducible, containerized, and fully observable experimental platform suitable for scientific scalability evaluation.

Deliverables:

- Dockerized deployment of Agent Host and MCP Tool Servers
- Prometheus-based metrics pipeline and Grafana dashboards
- Single `docker-compose` experiment stack
- Fine-grained, labeled latency metrics for component-level attribution

This ensures repeatable, comparable, and diagnosable experiments.

## Why containerization matters

- Ensures identical runtime environments across runs and machines
- Makes resource usage (CPU/memory) consistent and measurable
- Enables audited, reproducible experiments suitable for publication

## Observability architecture

```
[Locust]
   ↓
[Agent Host] ── /metrics ──▶ Prometheus ──▶ Grafana
   ↓
[ToolExecutor]
   ↓
[FastMCP Tool Server]
```

Collected signals:

- HTTP request rates and latencies
- MCP pipeline internal latencies
- MCP protocol overhead
- Tool execution time
- End-to-end request latency
- Container CPU and memory usage

## Metric design (research-grade)

### Single labeled histogram

Use one histogram with a `component` label instead of many separate metrics:

- `mcp_latency_ms{component="model"}`
- `mcp_latency_ms{component="tool"}`
- `mcp_latency_ms{component="protocol"}`
- `mcp_latency_ms{component="pipeline"}`
- `mcp_latency_ms{component="total"}`

### Fine-grained buckets

Example buckets (ms): `[5, 10, 25, 50, 100, 250, 500, 750, 1000, 2500, 5000, 10000]`

This gives high resolution for fast tools and coverage for long-tail LLM latencies.

## Instrumentation strategy

### HTTP-level metrics

Use `prometheus-fastapi-instrumentator` to capture request counts, latency distributions, and error rates automatically.

### Internal MCP metrics

Manually instrument:

- Model latency
- Tool total latency
- MCP protocol overhead
- Pipeline orchestration overhead
- End-to-end latency

Keep instrumentation minimal to avoid double-counting and metric pollution.

## Docker networking and reproducibility

- Services communicate via Docker service names (e.g., `http://echo_tool:8001`) to ensure portability.
- Set `PYTHONPATH=/app` inside containers to stabilize imports.

## Health checks and startup ordering

- Add Docker `HEALTHCHECK` to MCP tool servers.
- Use `depends_on: condition: service_healthy` (or equivalent) so the Agent Host waits until tools are ready.

## Warm MCP handshake

Perform MCP `initialize` once at startup (ToolExecutor) using FastAPI lifespan hooks so handshake cost is excluded from steady-state latency.

## Deployed services

- `agent_host` — Agent pipeline + model adapter + tool executor
- `echo_tool` — FastMCP baseline tool
- `prometheus` — Time-series metrics storage
- `grafana` — Dashboards and visualization

Start the stack with:

```bash
docker-compose up
```

## KPIs enabled by Task 4

- Latency decomposition: labeled histogram in Prometheus
- Throughput: HTTP request counters
- Concurrency limit: error rate + p99 latency
- Tool invocation cost: tool processing time reported by tool
- Protocol overhead: RTT − tool time
- Pipeline overhead: residual orchestration time
- Resource utilization: Docker / node exporter

## Experimental procedure

1. Start the stack (`docker-compose up`) and wait for healthchecks
2. Warm up for 60 seconds
3. Run Locust and ramp users/request rate
4. Observe p50/p95/p99, throughput, error rate, CPU/memory in Grafana
5. Stop when p99 latency explodes or error rate increases

Compare runs across transports (SSE vs stdio), adapters (MockAdapter vs real), and resource limits.

---

