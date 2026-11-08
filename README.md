# 25LAI46MS_Systematic_Analysis_of_MCP_Scalability
SRIB-PRISM Program

## Project Status

### Completed Milestones

- ✅ **Core Infrastructure:** Fully containerized microservices architecture with Docker Compose orchestration
- ✅ **Model Integration:** Pluggable adapter system supporting Mock, Ollama, OpenAI, and Anthropic backends
- ✅ **Observability Stack:** End-to-end instrumentation with Prometheus metrics, structured JSONL logging, and distributed tracing
- ✅ **Workload Suite:** Eight canonical workload profiles (W1-W8) covering orthogonal scalability dimensions, including diverse tool orchestration
- ✅ **Data Pipeline:** Automated aggregation and analysis scripts for experimental results, token cost tracking, and error recovery plotting
- ✅ **MCP Tool Servers:** Full ecosystem of 5 FastMCP servers (Echo, Math, Search, Database, File System, Sleep)
- ✅ **Agent Orchestration:** Complete agentic workflow pipeline with deep iterative tool execution and context chaining
- ✅ **Transport Layer:** Configurable transport modes supporting both HTTP/SSE and localized Stdio subprocesses

## System Architecture

The system follows a multi-layered microservices architecture designed for systematic performance analysis:

![System Architecture](docs/architecture/Architectural%20diagram.png)

### Key Capabilities

The platform measures the following performance characteristics:

- **Latency Decomposition:** Model latency, tool execution cost, MCP protocol overhead, pipeline orchestration overhead
- **Throughput Metrics:** Requests per second (RPS) under varying load conditions
- **Latency Distribution:** p50, p95, p99 percentiles
- **Saturation Analysis:** Concurrency limits and degradation behavior
- **Resource Utilization:** CPU, memory, and network consumption patterns
- **Protocol Efficiency:** MCP overhead percentage relative to total request latency
- **Economic Scalability:** Granular Prompt vs Completion token tracking ($) per workflow step
- **Resilience:** Autonomous error recovery and tool-failure tracking at deep iteration scales (depth=5)

## Setup Guide

### Prerequisites

- **Docker:** Version 20.10 or higher
- **Docker Compose:** Version 2.0 or higher
- **System Requirements:** Minimum 4GB RAM, 10GB available disk space

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd mcp-scalability-analysis
   ```

2. **Configure environment:**
   Create a `.env` file to customize model backend and API keys. **This is required for Live LLM tests.**
   ```bash
   # External LLM Providers
   OPENAI_API_KEY=your_actual_key_here
   ANTHROPIC_API_KEY=your_actual_key_here
   
   MODEL_BACKEND=ollama
   OLLAMA_MODEL=llama3.2:3b
   OLLAMA_URL=http://ollama:11434
   ```

3. **Build and start services:**
   ```bash
   docker-compose up --build -d
   ```

4. **Verify deployment:**
   ```bash
   docker-compose ps
   ```

### Service Endpoints

| Service | URL | Purpose |
|---------|-----|---------|
| Agent Host API | http://localhost:8000 | Main API endpoint |
| Prometheus UI | http://localhost:9090 | Metrics query interface |
| Grafana | http://localhost:3000 | Visualization dashboards |
| Ollama API | http://localhost:11434 | Local LLM service |

## Usage Guide & Runbook

For a highly detailed guide on executing the benchmarking suites, setting token prices, and generating research reports, **please read the comprehensive [RUNBOOK](docs/RUNBOOK.md)**.

### Running Automated Test Suites

The benchmarking suite is split into two phases:

1. **Infrastructure Stress Test (Suite A)**:
   Tests pure concurrency scaling up to 500 users using the Mock Adapter and tests both `sse` and `stdio` transports.
   ```bash
   python scripts/run_infra_stress.py
   ```

2. **Live LLM Cognitive Stress Test (Suite B)**:
   Tests token costs, error recovery, and deep context chaining across live commercial or local models.
   ```bash
   python scripts/run_live_llm_stress.py --model-backend openai --users 1 5 10
   ```

### Generating Research Artifacts

Once the test suites generate the CSV logs, compile the final research plots (Cost Scaling, Error Recovery, Saturation) and dynamic markdown report:

```bash
# Generate plots in docs/reports/figures/
python scripts/analyze_scalability.py

# Compile the final Markdown report
python scripts/generate_report.py
```

### Workload Profiles

The platform includes eight canonical workload profiles designed to isolate bottlenecks:

| Workload | Description | Primary Metric |
|----------|-------------|----------------|
| W1 | Pure MCP overhead | Protocol efficiency |
| W2 | Light tool invocation (10ms) | Tool execution baseline |
| W3 | Medium tool invocation (100ms) | Tool scaling behavior |
| W4 | Deep workflow chain (depth=5) | Workflow orchestration overhead |
| W5 | Large payload (1MB) | Serialization performance |
| W6 | Multi-tool orchestration | Concurrent tool execution |
| W7 | Mixed workload stress test | System saturation characteristics |
| W8 | Diverse tools | Complex context chaining (Math, DB, File) |

## Experimental Methodology

For rigorous performance analysis, follow these guidelines:

- **Warm-up Period:** 60 seconds before measurement
- **Measurement Duration:** 3-5 minutes per data point
- **Repetitions:** Minimum 3 runs, report median values
- **Variable Control:** Vary one independent variable per experiment
- **Resource Isolation:** Run experiments on dedicated infrastructure
- **Data Persistence:** All logs and metrics are persisted in `data/` directory
