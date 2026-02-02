# 25LAI46MS_Systematic_Analysis_of_MCP_Scalability
SRIB-PRISM Program

## Project Status

### Completed Milestones

- ✅ **Core Infrastructure:** Fully containerized microservices architecture with Docker Compose orchestration
- ✅ **Model Integration:** Pluggable adapter system supporting Mock, Ollama, OpenAI, and Anthropic backends
- ✅ **Observability Stack:** End-to-end instrumentation with Prometheus metrics, structured JSONL logging, and distributed tracing
- ✅ **Workload Suite:** Seven canonical workload profiles (W1-W7) covering orthogonal scalability dimensions
- ✅ **Load Testing:** High-concurrency load generation framework using Locust
- ✅ **Data Pipeline:** Automated aggregation and analysis scripts for experimental results
- ✅ **MCP Tool Servers:** Echo tool server implementation with FastMCP
- ✅ **Agent Orchestration:** Complete agentic workflow pipeline with tool execution engine

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

2. **Configure environment (optional):**
   
   Create a `.env` file to customize model backend:
   ```bash
   # Example: Use OpenAI
   MODEL_BACKEND=openai
   OPENAI_API_KEY=sk-your-api-key
   OPENAI_MODEL=gpt-4o-mini
   
   # Example: Use Ollama (default)
   MODEL_BACKEND=ollama
   OLLAMA_MODEL=llama3.2:3b
   OLLAMA_URL=http://ollama:11434
   
   # Example: Use Mock adapter for testing
   MODEL_BACKEND=mock
   ```

3. **Build and start services:**
   ```bash
   docker-compose up --build -d
   ```

4. **Verify deployment:**
   ```bash
   docker-compose ps
   ```
   
   Expected output:
   ```
   NAME         STATUS                    PORTS
   agent_host   Up                        0.0.0.0:8000->8000/tcp
   echo_tool    Up (healthy)              0.0.0.0:8001->8001/tcp
   grafana      Up                        0.0.0.0:3000->3000/tcp
   ollama       Up                        0.0.0.0:11434->11434/tcp
   prometheus   Up                        0.0.0.0:9090->9090/tcp
   ```

5. **Initialize Ollama model (if using Ollama backend):**
   ```bash
   docker exec -it ollama ollama pull llama3.2:3b
   ```

### Service Endpoints

| Service | URL | Purpose |
|---------|-----|---------|
| Agent Host API | http://localhost:8000 | Main API endpoint |
| Agent Host Docs | http://localhost:8000/docs | Interactive API documentation |
| Metrics Endpoint | http://localhost:8000/metrics | Prometheus metrics |
| Prometheus UI | http://localhost:9090 | Metrics query interface |
| Grafana | http://localhost:3000 | Visualization dashboards |
| Ollama API | http://localhost:11434 | Local LLM service |

## Usage Guide

### Running Performance Tests

1. **Execute a single workload:**
   ```bash
   curl -X POST http://localhost:8000/run \
     -H "Content-Type: application/json" \
     -d @benchmarks/workloads/w1_pure_mcp.json
   ```

2. **Start load testing:**
   ```bash
   # Install Locust (if not already installed)
   pip install locust
   
   # Launch Locust
   locust -f benchmarks/locustfiles/locustfile.py
   ```
   
   Access Locust UI at http://localhost:8089 and configure test parameters:
   - Number of users: 10-1000 (depending on test scenario)
   - Spawn rate: 10 users/second
   - Host: http://localhost:8000

3. **Monitor metrics in real-time:**
   - **Prometheus:** Navigate to http://localhost:9090 and query `mcp_latency_ms_bucket`
   - **Grafana:** Login at http://localhost:3000 (default credentials: `admin` / `admin`)

### Analyzing Results

1. **View structured logs:**
   ```bash
   # Agent host logs
   cat data/logs/agent_host.jsonl | jq '.'
   
   # Tool execution logs
   cat data/logs/tool_executor.jsonl | jq '.'
   ```

2. **Generate aggregated metrics:**
   ```bash
   python scripts/summarize_run.py
   ```
   
   Output location: `data/results/latest/summary.csv`
   
   The summary includes:
   - Latency percentiles (p50, p95, p99)
   - Throughput (requests per second)
   - Protocol overhead percentage
   - Resource utilization metrics

3. **Query Prometheus metrics:**
   ```promql
   # Average latency by component
   rate(mcp_latency_ms_sum[5m]) / rate(mcp_latency_ms_count[5m])
   
   # 95th percentile latency
   histogram_quantile(0.95, rate(mcp_latency_ms_bucket[5m]))
   ```

### Workload Profiles

The platform includes seven canonical workload profiles:

| Workload | Description | Primary Metric |
|----------|-------------|----------------|
| W1 | Pure MCP overhead | Protocol efficiency |
| W2 | Light tool invocation (10ms) | Tool execution baseline |
| W3 | Medium tool invocation (100ms) | Tool scaling behavior |
| W4 | Deep workflow chain (depth=5) | Workflow orchestration overhead |
| W5 | Large payload (1MB) | Serialization performance |
| W6 | Multi-tool orchestration | Concurrent tool execution |
| W7 | Mixed workload stress test | System saturation characteristics |

### Troubleshooting

1. **Check service health:**
   ```bash
   docker-compose logs agent_host
   docker-compose logs echo_tool
   docker-compose logs ollama
   ```

2. **Restart services:**
   ```bash
   docker-compose restart
   ```

3. **Complete reset:**
   ```bash
   docker-compose down -v
   docker-compose up --build
   ```

4. **Verify connectivity:**
   ```bash
   # Test Agent Host
   curl http://localhost:8000/metrics
   
   # Test Ollama
   curl http://localhost:11434/api/tags
   ```

## Experimental Methodology

For rigorous performance analysis, follow these guidelines:

- **Warm-up Period:** 60 seconds before measurement
- **Measurement Duration:** 3-5 minutes per data point
- **Repetitions:** Minimum 3 runs, report median values
- **Variable Control:** Vary one independent variable per experiment
- **Resource Isolation:** Run experiments on dedicated infrastructure
- **Data Persistence:** All logs and metrics are persisted in `data/` directory

---


