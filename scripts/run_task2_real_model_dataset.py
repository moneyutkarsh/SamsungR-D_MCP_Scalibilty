#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd


WORKLOADS = [
    "benchmarks/workloads/w1_pure_mcp.json",
    "benchmarks/workloads/w2_light_tool.json",
    "benchmarks/workloads/w3_medium_tool.json",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Task 2: Build initial real-model dataset (Mock vs Ollama) for W1-W3."
    )
    parser.add_argument("--model", default="phi3:mini", help="Ollama model name")
    parser.add_argument("--users", nargs="+", type=int, default=[10, 50, 100], help="Concurrency levels")
    parser.add_argument("--repeats", type=int, default=3, help="Repeats per config")
    parser.add_argument("--requests-per-user", type=int, default=15, help="Requests per user per repeat")
    parser.add_argument("--host", default="http://localhost:8000", help="Agent host URL")
    parser.add_argument("--prometheus-url", default="http://localhost:9090", help="Prometheus URL")
    parser.add_argument(
        "--result-root",
        default="data/results/task2_initial_real_model",
        help="Root output directory for Task 2 artifacts",
    )
    parser.add_argument(
        "--skip-docker-setup",
        action="store_true",
        help="Skip docker compose setup/restart steps and only run dataset scripts",
    )
    return parser.parse_args()


def run_cmd(cmd: list[str], env: dict[str, str] | None = None) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)


def ensure_health(host: str, timeout_s: int = 120) -> None:
    import httpx

    deadline = time.time() + timeout_s
    last_error = "health check timeout"
    with httpx.Client(timeout=5.0) as client:
        while time.time() < deadline:
            try:
                response = client.get(f"{host}/health")
                if response.status_code == 200:
                    return
                last_error = f"status={response.status_code}"
            except Exception as ex:
                last_error = str(ex)
            time.sleep(2)
    raise RuntimeError(f"Agent host health check failed: {last_error}")


def restart_agent_with_backend(backend: str, model: str) -> None:
    env = os.environ.copy()
    env["MODEL_BACKEND"] = backend
    env["OLLAMA_MODEL"] = model

    run_cmd(["docker-compose", "up", "-d", "echo_tool", "prometheus", "grafana", "ollama"], env=env)
    run_cmd(["docker-compose", "up", "-d", "--force-recreate", "agent_host"], env=env)


def run_baseline_subset(
    python_exe: str,
    host: str,
    prom_url: str,
    users: list[int],
    repeats: int,
    requests_per_user: int,
    result_root: Path,
) -> None:
    cmd = [
        python_exe,
        "scripts/run_baseline_dataset.py",
        "--host",
        host,
        "--prometheus-url",
        prom_url,
        "--workloads",
        *WORKLOADS,
        "--users",
        *[str(u) for u in users],
        "--repeats",
        str(repeats),
        "--requests-per-user",
        str(requests_per_user),
        "--result-root",
        str(result_root),
    ]
    run_cmd(cmd)


def build_comparison(result_root: Path, mock_root: Path, ollama_root: Path) -> None:
    mock_long = pd.read_csv(mock_root / "summary_statistics_long.csv")
    ollama_long = pd.read_csv(ollama_root / "summary_statistics_long.csv")

    join_keys = ["workload", "users", "metric"]

    mock_cols = {
        c: f"mock_{c}"
        for c in ["count", "mean", "std", "median", "q1", "q3", "iqr", "ci95_low", "ci95_high", "cv_pct"]
        if c in mock_long.columns
    }
    ollama_cols = {
        c: f"ollama_{c}"
        for c in ["count", "mean", "std", "median", "q1", "q3", "iqr", "ci95_low", "ci95_high", "cv_pct"]
        if c in ollama_long.columns
    }

    mock_df = mock_long.rename(columns=mock_cols)
    ollama_df = ollama_long.rename(columns=ollama_cols)

    merged = mock_df.merge(ollama_df, on=join_keys, how="outer")

    if "mock_median" in merged.columns and "ollama_median" in merged.columns:
        merged["median_abs_delta"] = merged["ollama_median"] - merged["mock_median"]
        merged["median_pct_delta"] = (
            (merged["median_abs_delta"] / merged["mock_median"]) * 100.0
        )

    if "mock_mean" in merged.columns and "ollama_mean" in merged.columns:
        merged["mean_abs_delta"] = merged["ollama_mean"] - merged["mock_mean"]
        merged["mean_pct_delta"] = (
            (merged["mean_abs_delta"] / merged["mock_mean"]) * 100.0
        )

    merged = merged.sort_values(["workload", "users", "metric"])
    merged.to_csv(result_root / "mock_vs_ollama_comparison.csv", index=False)

    key_metrics = [
        "throughput_rps",
        "total_pipeline_ms",
        "mcp_protocol_overhead_ms",
        "tool_processing_ms",
        "protocol_overhead_pct",
    ]
    summary = merged[merged["metric"].isin(key_metrics)].copy()
    summary.to_csv(result_root / "mock_vs_ollama_comparison_key_metrics.csv", index=False)


def main() -> None:
    args = parse_args()

    result_root = Path(args.result_root)
    result_root.mkdir(parents=True, exist_ok=True)

    manifest = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "task": "task2_initial_real_model_dataset",
        "workloads": WORKLOADS,
        "users": args.users,
        "repeats": args.repeats,
        "requests_per_user": args.requests_per_user,
        "ollama_model": args.model,
        "host": args.host,
        "prometheus_url": args.prometheus_url,
        "skip_docker_setup": args.skip_docker_setup,
    }
    with (result_root / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    python_exe = sys.executable
    mock_root = result_root / "mock"
    ollama_root = result_root / "ollama"

    if not args.skip_docker_setup:
        restart_agent_with_backend("mock", args.model)
    ensure_health(args.host)
    run_baseline_subset(
        python_exe=python_exe,
        host=args.host,
        prom_url=args.prometheus_url,
        users=args.users,
        repeats=args.repeats,
        requests_per_user=args.requests_per_user,
        result_root=mock_root,
    )

    if not args.skip_docker_setup:
        restart_agent_with_backend("ollama", args.model)
        run_cmd(["docker", "exec", "ollama", "ollama", "pull", args.model])
    ensure_health(args.host)
    run_baseline_subset(
        python_exe=python_exe,
        host=args.host,
        prom_url=args.prometheus_url,
        users=args.users,
        repeats=args.repeats,
        requests_per_user=args.requests_per_user,
        result_root=ollama_root,
    )

    build_comparison(result_root=result_root, mock_root=mock_root, ollama_root=ollama_root)

    print("\nTask 2 dataset complete")
    print(f"Artifacts written to: {result_root}")


if __name__ == "__main__":
    main()
