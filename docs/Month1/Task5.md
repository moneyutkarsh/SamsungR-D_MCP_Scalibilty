 # Task 5 — Baseline Workloads and Systematic Experiment Matrix

## Objective

Define a minimal, orthogonal, and reproducible set of workloads and an experiment matrix to enable controlled scientific analysis of MCP scalability.

Deliverables:

- Workload taxonomy and canonical suite (W1–W7)
- Parameterized workload JSON schema
- Systematic experiment matrix and reproducible protocol
- Example output artifact layout

## Why workload design matters

- Avoid ad-hoc tests that mix variables
- Achieve orthogonality: each workload targets one dominant subsystem
- Keep the set minimal but broadly representative
- Make workloads version-controlled and reproducible

## Workload taxonomy

We classify workloads across four axes:

- Tool cost — how expensive each tool invocation is
- Workflow depth — number of tool calls per request
- Tool diversity — number of distinct tools
- Payload size — serialization/transport cost

Each canonical workload stresses one axis while holding others constant.

## Canonical workload suite

- W1 — Pure MCP Overhead
  - Tool delay: 0 ms, depth: 1, payload: tiny
  - Purpose: measure maximum theoretical MCP throughput (protocol + orchestration)

- W2 — Light Tool
  - Tool delay: 10 ms, depth: 1, payload: small
  - Purpose: detect transition where tool cost begins to matter

- W3 — Medium Tool
  - Tool delay: 100 ms, depth: 1, payload: small
  - Purpose: tool-dominated regime

- W4 — Deep Workflow (Depth Scaling)
  - Tool delay: 10 ms, depth: 5 (same tool), payload: small
  - Purpose: measure pipeline and context propagation overhead

- W5 — Large Payload (Serialization Bound)
  - Tool delay: 10 ms, depth: 1, payload: ~1 MB
  - Purpose: stress JSON serialization, SSE buffering, and CPU

- W6 — Multi-Tool Workflow (Breadth Scaling)
  - Tool count: 5+, depth: 5 (different tools), tool delay: 10 ms
  - Purpose: stress routing and registry lookup overhead

- W7 — Mixed Stress
  - Randomized depth (1–5), payload small→large, tool delay 10–100 ms
  - Purpose: approximate realistic production traffic and mixed regimes

## Workload specification format

Workloads live under `benchmarks/workloads/` as JSON files using a unified schema, e.g.:

```json
{
  "name": "W2_light_tool",
  "description": "Light tool delay, small payload",
  "model": "mock",
  "workflow": ["echo"],
  "tool_params": { "delay_ms": 10, "payload_size_kb": 1 },
  "payload": { "text": "hello" }
}
```

This enables programmatic loading and version-controlled experiment definitions.

## Execution model

- Agent Host accepts a workload JSON and executes the workflow step-by-step
- Measures: model latency, tool execution time, MCP protocol overhead, pipeline overhead
- Returns: final output, full metric breakdown, trace ID

## Performance-sensitive choices

- Use `orjson` for serialization/deserialization in W5 to avoid Python `json` CPU limits
- Track token usage and tokens/sec as secondary KPIs (important for W5/W6)

## Experiment matrix

Independent variables:

- Workload: W1–W7
- Concurrency: 1, 10, 50, 100, 200, 500, 1000
- Transport: SSE, stdio
- Model: Mock, Real
- CPU limit: 0.5, 1, 2 cores
- Tool count: 1, 5, 20, 100

Dependent measurements:

- p50 / p95 / p99 latencies
- Throughput (RPS)
- Error rate
- CPU / memory usage
- Token usage (for real models)

## Experimental methodology

For each experiment point:

1. Start the stack
2. Warm-up for 60 seconds
3. Run test for 3–5 minutes
4. Collect steady-state metrics
5. Repeat 3 times and use the median result

## Example experimental slice

Fixed: Workload=W2, Model=Mock, Transport=SSE, CPU=0.5 core

Vary concurrency: 1 → 10 → 50 → 100 → 200 → 500

Plot throughput vs concurrency and p99 latency vs concurrency to reveal saturation points and collapse behavior.

## Output artifacts

Each experiment writes results to a directory like:

```
data/results/<workload>/<config>/
 ├── summary.csv
 ├── latency_timeseries.csv
 ├── cpu_timeseries.csv
 ├── memory_timeseries.csv
 └── notes.md
```

## Why this is systematic analysis

- Only one dimension changes at a time; others are held constant
- Enables clear attribution: cause → effect, bottleneck → regime shift
- Matches standard distributed-systems benchmarking methodology

## Summary

Task 5 defines a minimal, orthogonal, and reproducible workload suite and experiment matrix for rigorous MCP scalability characterization across protocol, tool, orchestration, and resource dimensions.

---

