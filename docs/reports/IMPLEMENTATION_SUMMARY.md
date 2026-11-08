# MCP Scalability Project: Implementation Summary

This document summarizes the complete implementation of the MCP Scalability Analysis architecture, highlighting the specific features, services, and structural choices developed to conduct high-rigor latency and throughput tests.

## 1. High-Level Architecture
The project employs an **async-first multi-layer microservice** architecture that separates load generation, orchestration, model integration, tool execution, and observability into distinct decoupled components.

* **Load Generation:** Locust and custom Python dataset scripts.
* **Orchestration / Host:** An `AgentHost` handling incoming API requests and an `AgentPipeline` managing the request lifecycle.
* **Model Adapters:** Implementations of `IMCPAdapter` to translate generic requests into model-specific API calls.
* **Tool Servers:** Isolated `FastMCP` processes simulating tool work (e.g., Echo Tool).
* **Observability:** Distributed tracing, async JSONL logging, and Prometheus metrics gathering.

## 2. Core Components Implemented

### Orchestrator & Pipeline (`src/orchestrator/`)
- **`AgentHost`**: The central entrypoint API serving `/run`. Validates incoming payload semantics to ensure they align with the expected W1-W7 canonical JSON schemas.
- **`AgentPipeline`**: Executes workloads. It parses intent, determines if a workload is sequential or parallel, bypasses live model calls for deterministic workflow execution when explicitly declared, and aggregates model and tool performance into standard response metrics.
- **`ToolExecutor`**: Dispatches calls to tool servers using HTTP/SSE. It implements a connection pool (`httpx.AsyncClient`) with a max connection count of 500, performs an initial MCP handshake warmup to eliminate initialization costs during steady-state runs, and explicitly propagates `trace_id` headers to enable end-to-end trace correlation. Uses `orjson` for fast serialization of large (up to 1MB) payloads.

### Model Adapters (`src/model_adapters/`)
A pluggable adapter framework using the base class `IMCPAdapter` ensures model-agnostic execution.
- **MockAdapter**: A deterministic, zero-cost adapter meant for baseline protocol overhead benchmarking.
- **OllamaAdapter**: Async adapter for localized LLMs.
- **OpenAIAdapter**: Async adapter interfacing with the OpenAI API.
- **AnthropicAdapter**: Fully async adapter natively mapping Anthropic's response schema to the standard `ModelResponse` interface.

### Tool Servers (`src/servers/`)
- **Echo Tool Server (`echo_tool/server.py`)**: Built with `FastMCP`, this server features an `echo` tool capable of simulating processing delays (`delay_ms`) and expanding payloads to specific sizes (`payload_size_kb`). It captures the propagated `trace_id` and logs exact step execution timing, while also exposing a custom `/metrics` endpoint for Prometheus scraping.

### Observability & Metrics (`src/metrics/` & `src/utils/`)
- **Context Tracing (`core/context.py`)**: Uses Python `contextvars` to maintain async-safe tracing without needing to pass IDs explicitly through every function call.
- **Async JSONL Logging (`utils/jsonl_logger.py`)**: Critical path logging (request logs and tool logs) is offloaded to background threads using `asyncio.to_thread()` to prevent disk I/O from stalling the event loop.
- **Prometheus Labeled Histograms**: Latency is cleanly decomposed into `model_latency_ms`, `tool_processing_ms`, `mcp_protocol_overhead_ms`, and `pipeline_overhead_ms`.

## 3. Benchmarking & Workloads

### Workload Definitions (`benchmarks/workloads/`)
Seven strictly schema-validated workloads have been configured to isolate and measure specific system stressors:
- **W1 (Pure MCP):** Base protocol overhead.
- **W2 (Light Tool):** Small payload + 10ms processing delay.
- **W3 (Medium Tool):** Small payload + 100ms processing delay.
- **W4 (Deep Workflow):** 5 sequential tool invocations.
- **W5 (Large Payload):** 1MB tool payload serialization.
- **W6 (Multi-Tool):** 5 parallel tool invocations.
- **W7 (Mixed Stress):** Heavy payload + delays.

### Load Drivers (`benchmarks/locustfiles/` & `scripts/`)
- **Locust**: A dynamic `locustfile.py` that reads W1-W7 from disk and orchestrates scaled load with configurable ramps.
- **Dataset Generators (`scripts/`)**: Automated scripts (`run_baseline_dataset.py`, etc.) designed to run rigorous parameter-sweeps over users (1-500) and repetitions, aggregating results into CSVs and recording snapshots of Prometheus metrics.

## 4. Infrastructure (`docker-compose.yml`)
The stack is fully containerized, launching:
- **agent_host**: The core orchestrator API.
- **echo_tool**: FastMCP tool endpoint.
- **prometheus**: Scrapes metrics from both the host and the tool server.
- **grafana**: Provisioned automatically to load the Prometheus datasource and the pre-configured `mcp-scalability` dashboard showing latency decompositions.
- **ollama** (Optional via overrides).

## 5. Recent Fixes Ensuring Validity
To ensure research-grade correctness, the following recent updates were applied:
1. **Pipeline Execution Integrity**: `AgentPipeline` now perfectly honors the predefined W1-W7 workflows rather than skipping them if the model adapter returns an empty tool call list.
2. **End-to-End Tracing**: `ToolExecutor` passes the `trace_id` securely to FastMCP via arguments, binding tool execution logs to the root orchestrator request logs.
3. **HTTP Transport Alignment**: Modified `ToolExecutor` to hit `/mcp` instead of `/messages`, aligning perfectly with FastMCP's internal streamable HTTP routing.
4. **Focused Unit Testing**: New tests (`tests/test_workload_pipeline.py`) verify the mathematical correctness of tool counts, payload inflation, and latency aggregation.
