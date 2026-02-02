 # Task 3 — MCP Tool Server, Agent Pipeline, and Benchmarking Execution Loop

## Objective

Implement a real MCP‑compliant agent↔tool execution loop to measure MCP protocol overhead, tool execution cost, and agent pipeline overhead under scalable load.

Deliverables:

- FastMCP-based tool server (echo baseline)
- High-precision MCP client (`ToolExecutor`) with connection pooling and handshake
- Agent pipeline integrating the model adapter (Task 2) with tool execution
- Concurrency-safe Agent Host API (FastAPI)
- Locust load generator skeleton for high-concurrency benchmarking

## Why use the official MCP SDK

Ad-hoc HTTP clients skip MCP framing, handshake, and session semantics. Using the official FastMCP SDK ensures measurements include JSON‑RPC framing, transport, and handshake costs.

## System architecture

```
Locust -> Agent Host (FastAPI) -> Agent Pipeline -> Model Adapter -> ToolExecutor (MCP client) -> FastMCP Tool Server (echo)
```

This separation enables isolation of model latency, protocol overhead, tool execution cost, and pipeline orchestration overhead.

## Echo Tool (baseline)

- Tool name: `echo`
- Behavior: returns input text and reports internal processing time
- Simulated work: configurable small delay (e.g., 10 ms)
- Transports: SSE (HTTP) and stdio for local comparisons

Purpose: provide a deterministic baseline to isolate MCP overhead from tool processing cost.

## ToolExecutor — benchmarking engine

Features:

- Singleton `httpx.AsyncClient` for connection pooling
- Warm-up handshake using MCP `initialize` during FastAPI lifespan
- High-precision timing for RTT and sub-component measurements

Handshake must be performed at startup to avoid inflating steady-state request latency.

## Latency decomposition

For each tool call capture:

- Total RTT (JSON‑RPC + transport + server)
- Tool internal processing time (from server metadata)

Compute:

```
MCP protocol overhead = Total RTT - Tool processing time
```

This yields a clean decomposition of protocol vs tool cost.

## Agent pipeline integration

Pipeline steps:

1. Call model adapter with tool schemas
2. Receive `tool_calls` from model response
3. Execute tool via `ToolExecutor`
4. Aggregate and emit full-system metrics (timers, counts, errors)

The pipeline reports: model latency, tool total latency, tool processing latency, MCP protocol overhead, pipeline orchestration overhead, and end‑to‑end latency.

## FastAPI Agent Host

- Use lifespan hooks to initialize MCP connections and reuse pools
- Expose endpoint: `POST /run` — safe for thousands of concurrent clients when using async pooling

Example run endpoint (conceptual):

```http
POST /run
Content-Type: application/json
{
  "input": "...",
  "schema": { ... }
}
```

## Load generator (Locust)

Locust workload repeatedly calls `POST /run`, simulating fast agentic loops. Ramp parameters to find saturation points (users, spawn rate).

Typical experiment ramp: 50 → 100 → 200 → 500 → 1000 users

Track: p50/p95/p99 latency, throughput, error rate, CPU/memory.

## KPIs enabled by Task 3

- Latency decomposition: pipeline & model components
- Throughput: Locust RPS
- Concurrency limit: error rate + p99 latency behavior
- Tool invocation cost: tool processing time
- MCP protocol overhead: RTT − tool processing time
- Model routing overhead: model adapter timings
- Pipeline overhead: residual orchestration time

## Experimental methodology (Milestone 1)

1. Start Echo server (SSE or stdio)
2. Start Agent Host
3. Warm-up (60 seconds)
4. Run Locust with configured ramps
5. Record p50/p95/p99, throughput, error rate, CPU/memory
6. Repeat for transports (SSE vs stdio) and adapters (MockAdapter vs real adapter)

## Research-grade guarantees

- Measures the real MCP protocol and transport costs
- Avoids handshake pollution in steady-state latency
- Uses connection pooling to avoid artificial client-side bottlenecks
- Provides reproducible, comparable experiments following standard distributed-systems methodology

## Summary

Task 3 builds the instrumented, MCP-compliant agent→tool execution loop used for scalable benchmarking and precise attribution of overhead across protocol, model, tool, and pipeline layers.

---

