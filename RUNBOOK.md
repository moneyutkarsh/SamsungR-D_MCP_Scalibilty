# MCP Benchmarking Runbook

## Overview
This runbook explains how to execute the MCP Scalability automated testing suites. We split the tests into two suites to respect external API rate limits while fully stressing our local infrastructure.

## Prerequisites
1. Ensure Docker daemon is running.
2. Verify all API keys are set in `.env` if testing Live LLMs:
   ```bash
   OPENAI_API_KEY=your_key
   ANTHROPIC_API_KEY=your_key
   ```
3. Start the infrastructure:
   ```bash
   docker-compose up -d --build
   ```

## Suite A: Infrastructure Stress Test
**Goal**: Test orchestrator and transport scaling (SSE vs Stdio) up to 500 concurrent users.
**Model**: `MockAdapter` (zero external network latency).

**Command**:
```bash
python scripts/run_infra_stress.py --users 1 50 100 200 500
```
This will run workloads W1-W7 iteratively across both transports and output data to `data/results/baseline_mockadapter`.

## Suite B: Live LLM Cognitive Stress
**Goal**: Test complex context accumulation, iterative workflows, and error recovery using real intelligence.
**Model**: OpenAI/Anthropic/Ollama (dynamically selectable per test).
**Constraint**: Rate limits apply to external APIs (HTTP 429). Max concurrency ~50.

**Command**:
```bash
# Dry-run to validate setup (default is openai)
python scripts/run_live_llm_stress.py --dry-run

# Run with Anthropic models
python scripts/run_live_llm_stress.py --model-backend anthropic --users 1 5 10

# Run with local Ollama models (no API keys required, safe to push concurrency higher if hardware permits)
python scripts/run_live_llm_stress.py --model-backend ollama --users 1 5 10 20 50
```

## Generate Reports & Dashboards
After running the suites, you can generate graphs and the final markdown report:
```bash
# Generate scalability plots
python scripts/analyze_scalability.py

# Generate final text report
python scripts/generate_report.py
```

Check Grafana at `http://localhost:3000` to view real-time latency profiles and overhead metrics.
