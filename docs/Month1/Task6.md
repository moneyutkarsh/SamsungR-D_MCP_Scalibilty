 # Task 6 — Structured Logging, Trace Correlation, and Result Schema

## Objective

Transform the MCP benchmarking system from a metrics-only setup into a traceable, dataset-producing experimental platform where every request yields structured, correlated, machine-readable traces.

Deliverables:

- End-to-end trace correlation using `trace_id`
- Non-blocking JSONL logs (per-component)
- Formal log schemas and aggregation scripts
- Reproducible CSV/Parquet experiment artifacts

## Why metrics alone are insufficient

Prometheus shows trends and saturation but cannot identify which single request or tool caused an outlier. Per-request traces are required for root-cause and tail-latency analysis.

## Data flow

```
Client/Locust -> Agent Host (/run) [trace_id created]
      -> agent_host.jsonl
      -> Agent Pipeline -> tool_executor.jsonl
      -> FastMCP Tool Server -> echo_tool.jsonl
      -> Prometheus (time-series)
```

All logs are correlated using a single `trace_id` propagated via metadata.

## Trace propagation strategy

- Use `contextvars` to store `trace_id` per async request (clean signatures, concurrency-safe).
- Create the trace in the Agent Host and make it implicitly available to Pipeline, ToolExecutor, Model Adapter, and FastMCP tools (via `_meta`).

## Non-blocking logging

- Synchronous disk I/O blocks the event loop and perturbs measurements.
- Offload JSONL writes with `asyncio.to_thread(...)` (or a small thread pool) so logging is non-blocking and crash-safe.

## Log format: JSON Lines (JSONL)

- Append-only, one JSON object per line
- Stream-processable and Pandas-compatible
- Example files:

```
data/logs/
 ├── agent_host.jsonl
 ├── tool_executor.jsonl
 └── echo_tool.jsonl
```

## Log schemas (examples)

### Request (agent_host) log

```json
{
      "trace_id": "...",
      "timestamp": "...",
      "environment": "docker|local|cloud",
      "workload": "w4_deep_workflow",
      "metrics": {
            "total_pipeline_ms": 123.4,
            "model_latency_ms": 5.2,
            "tool_total_ms": 110.1,
            "tool_processing_ms": 100.0,
            "mcp_protocol_overhead_ms": 10.1,
            "pipeline_overhead_ms": 8.1
      }
}
```

### Tool call log (tool_executor)

```json
{
      "trace_id": "...",
      "tool_name": "echo",
      "timestamp": "...",
      "total_latency_ms": 23.4,
      "tool_processing_ms": 10.0,
      "mcp_protocol_overhead_ms": 13.4
}
```

### Tool server log (echo_tool)

```json
{
      "trace_id": "...",
      "tool_name": "echo",
      "timestamp": "...",
      "tool_processing_ms": 10.0,
      "payload_bytes": 1024
}
```

## MCP metadata propagation

Pass `trace_id` to tools using the `_meta` field to avoid API surface changes:

```json
"_meta": { "trace_id": "..." }
```

This preserves protocol correctness and keeps tool APIs clean.

## Cross-environment comparability

Include an `environment` field (`local|docker|cloud`) in each request log to enable side-by-side comparisons of deployment profiles and hardware effects.

## Result aggregation pipeline

- Aggregation script: `python scripts/summarize_run.py`
- Produces `summary.csv` with mean, p50, p95, p99, and derived metrics (protocol overhead %, tool dominance ratio).

Example derived metric (p95 protocol impact %):

```python
proto_percent = (mcp_protocol_overhead_ms / total_pipeline_ms) * 100
```

## Scientific benefits

- Root-cause analysis of outliers and tail latencies
- Per-request forensic debugging and failure attribution
- Separation of model, tool, protocol, and orchestration costs
- Paper-quality datasets for reproducible research

## Experimental workflow

1. Run experiments and collect JSONL logs and Prometheus metrics
2. Run `python scripts/summarize_run.py` to produce CSV/Parquet artifacts
3. Analyze results in Grafana and with the produced CSVs (or load into a notebook)

## Research-grade guarantees

- Logging is non-intrusive (non-blocking)
- Data is structured, correlated, and reproducible
- System supports cross-run and cross-environment analysis

## Summary

Task 6 upgrades the MCP benchmarking system into a reproducible data pipeline that emits correlated JSONL traces and aggregation-ready artifacts suitable for rigorous scalability research.

---

*File updated to a structured documentation format.*