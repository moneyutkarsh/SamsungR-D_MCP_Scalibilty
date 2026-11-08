# MCP Scalability Analysis - Detailed Runbook

This runbook is a comprehensive guide to executing the Model Context Protocol (MCP) Scalability benchmarking suite. It covers environment configuration, token pricing, automated dataset generation, and final report compilation to produce research-grade analysis.

## 1. Environment & Pricing Configuration

Before running any benchmarks, you must configure the environment and token pricing.

### A. The `.env` File
The `.env` file located in the root of the project contains paths and API keys. To test Live LLMs (Suite B), you must insert your API keys here:
```bash
# External LLM Providers
OPENAI_API_KEY=your_actual_key_here
ANTHROPIC_API_KEY=your_actual_key_here
```
*Note: If you only plan to run Suite A (Infrastructure) or test with local Ollama models, you can leave these blank.*

### B. Configuring Token Pricing
We track precise workflow costs in real-time. If you are using a new model (or if provider pricing changes), you must update `config/pricing_tiers.json`.

Prices are defined in **USD per 1 Million Tokens**:
```json
{
  "openai:gpt-4o-mini": {
    "prompt_per_1m": 0.15,
    "completion_per_1m": 0.60
  }
}
```
If a model is not found in this file, its cost will default to `$0.00`.

## 2. Starting the Infrastructure

The entire platform (Orchestrator, 5 Tool Servers, Prometheus, Grafana, and Ollama) is containerized.
1. Start the stack in detached mode:
   ```bash
   docker-compose up -d --build
   ```
2. Wait ~30 seconds for the health checks to pass.
3. Verify Grafana is up at `http://localhost:3000` (Login: `admin` / `admin`).

## 3. Running the Test Suites

We have split the testing into two suites to isolate protocol overhead from third-party network latency.

### Suite A: Infrastructure Stress Test
**Goal**: Measure peak throughput and absolute protocol overhead.
**Adapter**: `MockAdapter` (Zero network calls, instant generation).
**Transport**: Iterates through both `sse` and `stdio`.
**Concurrency**: Scales from 1 up to 500 users.

To run:
```bash
python scripts/run_infra_stress.py
```
This script will execute workloads `w1` through `w8`, capturing traces and logging the dataset directly to `data/results/baseline_mockadapter/`.

### Suite B: Live LLM Cognitive Stress Test
**Goal**: Measure error recovery rates, context accumulation cost, and complex multi-tool workflow depths.
**Adapter**: Selectable (`openai`, `anthropic`, or `ollama`).
**Transport**: Defaults to `sse`.
**Concurrency**: Capped at 50 users for external APIs (to avoid HTTP 429 bans), but can be pushed higher for local Ollama.

**Dry Run (Highly Recommended)**:
Always run a dry-run first to ensure workloads are parsed and configurations are valid without burning API tokens.
```bash
python scripts/run_live_llm_stress.py --dry-run
```

**Execution**:
```bash
# Test OpenAI (gpt-4o-mini)
python scripts/run_live_llm_stress.py --model-backend openai --users 1 5 10

# Test Anthropic (claude-3-5-haiku-latest)
python scripts/run_live_llm_stress.py --model-backend anthropic --users 1 5 10

# Test Local Ollama (llama3.2:3b)
python scripts/run_live_llm_stress.py --model-backend ollama --users 1 5 10 20 50
```
Results are saved to `data/results/live_llm/`.

## 4. Analyzing the Results

Once the suites complete, the raw JSONL traces and CSVs are generated. You can now compile them into visual and textual research reports.

### Generating Plots
```bash
python scripts/analyze_scalability.py
```
This script parses the CSV data and outputs PNG graphs into `docs/reports/figures/`:
- `saturation_curves.png`: Throughput (RPS) vs Concurrent Users.
- `transport_overhead_boxplot.png`: SSE vs Stdio latency distributions.
- `llm_cost_scaling.png`: Average Cost ($) per Workflow vs Concurrency.
- `error_recovery_rates.png`: Average Tool Recoveries triggered per Workflow.

### Compiling the Final Report
```bash
python scripts/generate_report.py
```
This reads the peak throughputs and averages from the CSVs and merges them with the generated plots to produce `docs/reports/final_scalability_report.md`.

## 5. Live Observability (Grafana)
During the tests, you can monitor the system in real-time.
1. Go to `http://localhost:3000`.
2. Open the **MCP Scalability Analysis** dashboard.
3. You will see live gauges for:
   - Request Latency (Broken down by Agent, Pipeline, Protocol, Tool)
   - Protocol Overhead (SSE vs Stdio)
   - Real-time Cost/sec ($)

## 6. Teardown
When the research is complete, clean up the environment:
```bash
docker-compose down
```
