# Benchmarking Execution Steps

This guide outlines the necessary steps to set up the environment and run the benchmarking tests for the MCP Scalability Analysis project.

## 1. Start the Infrastructure

The orchestrator, tool servers, and observability stack are fully containerized. Start them using Docker Compose:

```bash
# Start all services in detached mode
docker-compose up -d
```

Ensure all services are running without errors:
```bash
docker-compose ps
docker-compose logs -f
```

*Note: The Grafana dashboard is pre-provisioned and can be accessed at `http://localhost:3000` (default credentials: admin/admin).*

## 2. Verify with Unit Tests

Before running heavy benchmarks, verify the orchestrator's pipeline executes workloads correctly. A specific suite tests the logic for workflow depth, payload serialization, and delays.

Ensure you have a Python environment set up with `pytest` or `unittest` and the necessary dependencies from `requirements.txt`:

```bash
# Run the workload pipeline tests
python -m unittest discover tests
```

## 3. Run Automated Dataset Generation (Recommended)

To run a full sweep across different workloads (W1-W7) and concurrent user levels (1, 10, 50, 100, etc.), use the provided automated scripts. These scripts aggregate statistics and capture Prometheus snapshots.

```bash
# Run the infrastructure stress test suite (using MockAdapter over sse and stdio)
python scripts/run_infra_stress.py

# Run the live LLM cognitive stress test suite (using OpenAI/Anthropic APIs)
# Use --dry-run to validate the environment before consuming real API credits
python scripts/run_live_llm_stress.py --dry-run
python scripts/run_live_llm_stress.py
```

Results (CSV summaries, JSONL raw logs, and Prometheus snapshots) will be saved in the `data/results/` directory.

## 4. Run Locust Load Tests Manually (Optional)

If you wish to visualize the load test in real-time or run custom profiles, you can start Locust directly. Locust dynamically loads workloads W1-W7 from `benchmarks/workloads/`.

```bash
# Start Locust UI
locust -f benchmarks/locustfiles/locustfile.py
```

Then, open your browser to `http://localhost:8089`. Enter the desired number of users and spawn rate.

Alternatively, run Locust headlessly for a specific workload via environment variables (if configured):
```bash
locust -f benchmarks/locustfiles/locustfile.py --headless -u 100 -r 10 --run-time 1m
```

## 5. Analyze Results

Once data is generated, you can run the analysis script to parse the CSV outputs and generate plots for the report.

```bash
# Generate scalability and transport comparison plots
python scripts/analyze_scalability.py

# Generate final scalability markdown report
python scripts/generate_report.py
```

Plots will be generated and saved in `docs/reports/figures/`.

## 6. Teardown

When you're finished benchmarking, stop the containers and clean up resources:

```bash
docker-compose down
```
