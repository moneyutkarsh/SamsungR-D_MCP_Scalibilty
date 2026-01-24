# MCP Scalability Analysis

Systematic Analysis of Model Context Protocol (MCP) Scalability

This repository is a research-grade benchmarking platform for systematically analyzing the scalability of the Model Context Protocol (MCP) along multiple dimensions:

- Concurrency
- Tool count
- Workflow depth
- Payload size
- Resource limits
- Transport (SSE / stdio)
- Model backends (Mock / Real)

It provides:

- A full agent + tool MCP pipeline
- High-concurrency load generation (Locust)
- Fine-grained observability (Prometheus + Grafana)
- End-to-end tracing and structured JSONL logging
- Reproducible Docker-based experiment environment
- Aggregation scripts that produce paper-grade datasets

---

## What this measures

The system decomposes end-to-end latency into:

- Model latency
- Tool execution cost
- MCP protocol overhead
- Pipeline orchestration overhead

And measures:

- Throughput (RPS)
- p50 / p95 / p99 latency
- Saturation points
- Resource usage
- Protocol overhead percentage
- Tail latency behavior

---

## High-level architecture

```
Locust
   │
   ▼
Agent Host (FastAPI) ─── /metrics ───▶ Prometheus ───▶ Grafana
   │
   ▼
ToolExecutor (MCP Client)
   │
   ▼
MCP Tool Server (FastMCP)
```

All components are containerized, instrumented, traceable, and reproducible.

---

## Project structure

- [src/](src/)
  - [orchestrator/](src/orchestrator/) — Agent host, pipeline, tool executor
  - [model_adapters/](src/model_adapters/) — Mock / OpenAI adapters
  - [servers/](src/servers/) — MCP tool servers (Echo, etc.)
  - [metrics/](src/metrics/) — Prometheus metric definitions and exporters
  - [utils/](src/utils/) — Async JSONL logger and helpers
  - [core/](src/core/) — ContextVars (`trace_id`) and core types

- [benchmarks/](benchmarks/)
  - [workloads/](benchmarks/workloads/) — Workload JSON definitions (W1–W7)
  - [locustfiles/](benchmarks/locustfiles/) — Load test scripts

- [infrastructure/](infrastructure/)
  - [docker/](infrastructure/docker/) — Dockerfiles
  - [prometheus/](infrastructure/prometheus/) — Prometheus config
  - [grafana/](infrastructure/grafana/) — Optional dashboards

- [data/](data/)
  - [logs/](data/logs/) — JSONL logs (persistent)
  - [prometheus/](data/prometheus/) — Prometheus TSDB
  - [results/](data/results/) — Aggregated experiment outputs
  - [schemas/](data/schemas/) — Log & result schemas

- [scripts/](scripts/) — `summarize_run.py` aggregates logs into CSV

- `docker-compose.yml`
- `requirements.txt`
- `README.md` (this file)

---

## Workloads (canonical)

The canonical workload suite (located in [benchmarks/workloads/](benchmarks/workloads/)):

- W1 — Pure MCP overhead
- W2 — Light tool (~10 ms)
- W3 — Medium tool (~100 ms)
- W4 — Deep workflow (depth = 5)
- W5 — Large payload (~1 MB)
- W6 — Multi-tool workflow
- W7 — Mixed stress

Each workload is a JSON file (schema in `benchmarks/workloads/`) and is version-controlled for reproducibility.

---

## Observability

**Metrics**

Prometheus scrapes the Agent Host metrics endpoint:

```
http://agent_host:8000/metrics
```

Key metric histogram:

- `mcp_latency_ms{component=...}` (labels: `model`, `tool`, `protocol`, `pipeline`, `total`)

**Logs**

Structured JSONL logs are written to persistent storage:

```
data/logs/
 ├── agent_host.jsonl
 ├── tool_executor.jsonl
 └── echo_tool.jsonl
```

**Tracing**

Each request is assigned a `trace_id` and correlated across Agent, Executor, and Tool Server via `_meta.trace_id`.

---

## Running the system (Docker — recommended)

### Prerequisites

- Docker
- Docker Compose

### Build and start everything

```bash
docker-compose build
docker-compose up
```

### Verify services

- Agent Host: `http://localhost:8000/docs`
- Metrics: `http://localhost:8000/metrics`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

### Run a test request

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d @benchmarks/workloads/w1_pure_mcp.json
```

### Check logs

```bash
ls data/logs/
```

---

## Running load tests (Locust)

Start Locust:

```bash
locust -f benchmarks/locustfiles/locustfile.py
```

Open the Locust UI at `http://localhost:8089` and configure users/spawn rates (e.g., 10 → 100 → 500 → 1000).

---

## Aggregating & analyzing results

Aggregate logs with the provided script:

```bash
python scripts/summarize_run.py
```

Outputs (example):

```
data/results/latest/summary.csv
```

`summary.csv` contains p50/p95/p99, throughput, and derived metrics such as protocol overhead %.

---

## Scientific methodology (recommended)

- Warm-up: 60 seconds
- Run duration: 3–5 minutes (steady-state) per point
- Repeat: 3 runs; use median values
- Vary one independent variable at a time (concurrency, workload, tool count, resource limits)

---

## KPIs measured

- Latency decomposition (model / tool / protocol / pipeline)
- Throughput (RPS)
- Concurrency limit and saturation behavior
- Tool invocation cost
- Model routing overhead
- MCP protocol overhead
- Resource utilization trends (CPU/memory)

---

## Reproducibility

Everything runs via Docker and persists logs/metrics to `data/` so experiments can be resumed, repeated, and audited.

---

## Optional local (non-Docker) run

```bash
pip install -r requirements.txt

# Start echo tool (example)
python -m src.servers.echo_tool.server

# Start agent
uvicorn src.orchestrator.agent_host:app --reload
```

---

## Project status

- ✅ Infrastructure: Docker compose + Prometheus/Grafana persistence
- ✅ Workloads defined (W1–W7)
- ✅ Tracing + structured logs implemented
- ✅ Ready for large-scale experiments

---

## License & contribution

This repository is intended for research use. Add contribution guidelines or license as appropriate for your organization.

---

If you want, I can also add a short `docker-compose.override.yml` for local quick-start and a `README_RUN.md` with step-by-step quick commands. Let me know which you'd prefer next.
