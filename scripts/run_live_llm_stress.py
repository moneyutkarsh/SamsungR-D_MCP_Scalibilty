#!/usr/bin/env python3
import argparse
import asyncio
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pandas as pd


DEFAULT_WORKLOADS = [
    "benchmarks/workloads/w1_pure_mcp.json",
    "benchmarks/workloads/w2_light_tool.json",
    "benchmarks/workloads/w3_medium_tool.json",
    "benchmarks/workloads/w4_deep_workflow.json",
]

DEFAULT_USERS = [1, 5, 10, 20, 50]
PROM_QUERIES = {
    "mcp_requests_total": "mcp_requests_total",
    "mcp_latency_p50_total": "histogram_quantile(0.50, rate(mcp_latency_ms_bucket{component=\"total\"}[1m]))",
    "mcp_latency_p95_total": "histogram_quantile(0.95, rate(mcp_latency_ms_bucket{component=\"total\"}[1m]))",
    "mcp_latency_p99_total": "histogram_quantile(0.99, rate(mcp_latency_ms_bucket{component=\"total\"}[1m]))",
}


@dataclass
class RepeatResult:
    workload: str
    users: int
    repeat: int
    total_requests: int
    success_count: int
    error_count: int
    elapsed_s: float
    throughput_rps: float
    mean_latency_ms: float
    p95_latency_ms: float
    error_rate: float
    output_dir: Path
    trace_ids: set[str]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run MockAdapter baseline dataset (W1-W7 x concurrency levels) with statistical summaries."
    )
    parser.add_argument("--host", default="http://localhost:8000", help="Agent host base URL")
    parser.add_argument(
        "--prometheus-url",
        default="http://localhost:9090",
        help="Prometheus base URL for snapshot queries",
    )
    parser.add_argument(
        "--workloads",
        nargs="+",
        default=DEFAULT_WORKLOADS,
        help="Workload JSON paths",
    )
    parser.add_argument(
        "--users",
        nargs="+",
        type=int,
        default=DEFAULT_USERS,
        help="Concurrency/user levels",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Number of repeated runs per (workload, users)",
    )
    parser.add_argument(
        "--requests-per-user",
        type=int,
        default=20,
        help="Requests issued by each virtual user in each repeat",
    )
    parser.add_argument(
        "--warmup-seconds",
        type=float,
        default=2.0,
        help="Sleep before each repeat to stabilize system",
    )
    parser.add_argument(
        "--result-root",
        default="data/results/live_llm",
        help="Root output folder for dataset artifacts",
    )
    parser.add_argument(
        "--model-backend",
        choices=["openai", "anthropic", "ollama"],
        default="openai",
        help="Which model backend to stress test.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the setup without actually hitting the network or creating files.",
    )
    parser.add_argument(
        "--agent-log",
        default="data/logs/agent_host.jsonl",
        help="Agent JSONL log path for trace filtering",
    )
    parser.add_argument(
        "--tool-log",
        default="data/logs/tool_executor.jsonl",
        help="Tool executor JSONL log path for trace filtering",
    )
    parser.add_argument(
        "--echo-log",
        default="data/logs/echo_tool.jsonl",
        help="Echo tool JSONL log path for trace filtering",
    )
    for t in ["math", "search", "db", "file", "sleep"]:
        parser.add_argument(
            f"--{t}-log",
            default=f"data/logs/{t}_tool.jsonl",
            help=f"{t.capitalize()} tool JSONL log path for trace filtering",
        )
    parser.add_argument(
        "--ci-bootstrap-samples",
        type=int,
        default=2000,
        help="Bootstrap resamples for median 95%% CI",
    )
    return parser.parse_args()


def load_workload(path: Path) -> tuple[dict[str, Any], str]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if "workload" not in data:
        data = {"workload": data}

    workload_name = data.get("workload", {}).get("name", path.stem)
    return data, workload_name


async def check_health(host: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{host}/health")
        resp.raise_for_status()


async def query_prometheus_snapshot(prom_url: str) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "captured_at": utc_now_iso(),
        "queries": {},
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        for name, expr in PROM_QUERIES.items():
            try:
                resp = await client.get(
                    f"{prom_url}/api/v1/query",
                    params={"query": expr},
                )
                resp.raise_for_status()
                snapshot["queries"][name] = resp.json()
            except Exception as ex:
                snapshot["queries"][name] = {
                    "status": "error",
                    "error": str(ex),
                    "expression": expr,
                }

    return snapshot


async def run_single_repeat(
    host: str,
    prom_url: str,
    request_payload: dict[str, Any],
    workload_name: str,
    users: int,
    requests_per_user: int,
    repeat_index: int,
    output_dir: Path,
) -> RepeatResult:
    ensure_dir(output_dir)

    before_snapshot = await query_prometheus_snapshot(prom_url)
    with (output_dir / "prometheus_before.json").open("w", encoding="utf-8") as f:
        json.dump(before_snapshot, f, indent=2)

    records: list[dict[str, Any]] = []
    timeout = httpx.Timeout(300.0, connect=10.0)
    limits = httpx.Limits(max_connections=max(1000, users * 2), max_keepalive_connections=max(100, users))

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        start = time.perf_counter()

        async def user_worker(user_id: int) -> None:
            nonlocal records

            for request_idx in range(requests_per_user):
                ts = utc_now_iso()
                req_start = time.perf_counter()
                row: dict[str, Any] = {
                    "timestamp": ts,
                    "workload": workload_name,
                    "users": users,
                    "repeat": repeat_index,
                    "user_id": user_id,
                    "request_index": request_idx,
                }
                try:
                    payload_with_users = dict(request_payload)
                    if "workload" in payload_with_users:
                        payload_with_users["workload"]["users"] = str(users)
                    else:
                        payload_with_users["users"] = str(users)
                        
                    resp = await client.post(f"{host}/run", json=payload_with_users)
                    row["http_status"] = resp.status_code
                    row["client_latency_ms"] = (time.perf_counter() - req_start) * 1000

                    if resp.status_code == 200:
                        body = resp.json()
                        row["trace_id"] = body.get("trace_id")

                        metrics = body.get("result", {}).get("metrics", {})
                        for key in [
                            "total_pipeline_ms",
                            "model_latency_ms",
                            "tool_total_ms",
                            "tool_processing_ms",
                            "mcp_protocol_overhead_ms",
                            "pipeline_overhead_ms",
                        ]:
                            row[key] = metrics.get(key)

                        total = row.get("total_pipeline_ms") or 0.0
                        proto = row.get("mcp_protocol_overhead_ms") or 0.0
                        row["protocol_overhead_pct"] = (proto / total * 100.0) if total > 0 else 0.0
                    else:
                        row["error"] = resp.text[:500]
                except Exception as ex:
                    row["http_status"] = -1
                    row["client_latency_ms"] = (time.perf_counter() - req_start) * 1000
                    row["error"] = str(ex)

                records.append(row)

        tasks = [asyncio.create_task(user_worker(user_id=i + 1)) for i in range(users)]
        await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start

    with (output_dir / "requests.jsonl").open("w", encoding="utf-8") as f:
        for item in records:
            f.write(json.dumps(item) + "\n")

    success_records = [r for r in records if r.get("http_status") == 200]
    success_count = len(success_records)
    error_count = len(records) - success_count

    trace_ids = {
        str(r["trace_id"])
        for r in success_records
        if r.get("trace_id")
    }

    throughput_rps = success_count / elapsed if elapsed > 0 else 0.0

    repeat_summary = {
        "timestamp": utc_now_iso(),
        "workload": workload_name,
        "users": users,
        "repeat": repeat_index,
        "requests_per_user": requests_per_user,
        "total_requests": len(records),
        "success_count": success_count,
        "error_count": error_count,
        "elapsed_s": elapsed,
        "throughput_rps": throughput_rps,
    }
    with (output_dir / "repeat_summary.json").open("w", encoding="utf-8") as f:
        json.dump(repeat_summary, f, indent=2)

    after_snapshot = await query_prometheus_snapshot(prom_url)
    with (output_dir / "prometheus_after.json").open("w", encoding="utf-8") as f:
        json.dump(after_snapshot, f, indent=2)

    # Compute latency statistics from successful records
    latencies = [r["client_latency_ms"] for r in success_records if r.get("client_latency_ms") is not None]
    if latencies:
        mean_latency_ms = float(sum(latencies) / len(latencies))
        sorted_lat = sorted(latencies)
        p95_latency_ms = float(sorted_lat[int(len(sorted_lat) * 0.95)])
    else:
        mean_latency_ms = 0.0
        p95_latency_ms = 0.0
    error_rate = error_count / len(records) if records else 0.0

    return RepeatResult(
        workload=workload_name,
        users=users,
        repeat=repeat_index,
        total_requests=len(records),
        success_count=success_count,
        error_count=error_count,
        elapsed_s=elapsed,
        throughput_rps=throughput_rps,
        mean_latency_ms=mean_latency_ms,
        p95_latency_ms=p95_latency_ms,
        error_rate=error_rate,
        output_dir=output_dir,
        trace_ids=trace_ids,
    )


def filter_logs_for_trace_ids(source_log: Path, trace_ids: set[str], target_log: Path) -> int:
    if not source_log.exists() or not trace_ids:
        return 0

    ensure_dir(target_log.parent)
    matched = 0
    with source_log.open("r", encoding="utf-8") as src, target_log.open("w", encoding="utf-8") as dst:
        for line in src:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(obj.get("trace_id", "")) in trace_ids:
                dst.write(json.dumps(obj) + "\n")
                matched += 1
    return matched


def bootstrap_ci_median(values: np.ndarray, samples: int = 2000, alpha: float = 0.05) -> tuple[float, float]:
    clean = values[~np.isnan(values)]
    if clean.size == 0:
        return (math.nan, math.nan)
    if clean.size == 1:
        return (float(clean[0]), float(clean[0]))

    rng = np.random.default_rng(42)
    medians = np.empty(samples, dtype=float)
    n = clean.size
    for i in range(samples):
        sampled = clean[rng.integers(0, n, size=n)]
        medians[i] = np.median(sampled)

    lower = float(np.quantile(medians, alpha / 2))
    upper = float(np.quantile(medians, 1 - (alpha / 2)))
    return lower, upper


def summarize_metric(series: pd.Series, ci_samples: int) -> dict[str, float]:
    arr = pd.to_numeric(series, errors="coerce").dropna().to_numpy(dtype=float)
    if arr.size == 0:
        return {
            "count": 0,
            "mean": math.nan,
            "std": math.nan,
            "median": math.nan,
            "q1": math.nan,
            "q3": math.nan,
            "iqr": math.nan,
            "ci95_low": math.nan,
            "ci95_high": math.nan,
            "cv_pct": math.nan,
        }

    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0
    median = float(np.median(arr))
    q1 = float(np.quantile(arr, 0.25))
    q3 = float(np.quantile(arr, 0.75))
    iqr = q3 - q1
    ci95_low, ci95_high = bootstrap_ci_median(arr, samples=ci_samples)
    cv_pct = float((std / mean) * 100.0) if mean != 0 else math.nan

    return {
        "count": int(arr.size),
        "mean": mean,
        "std": std,
        "median": median,
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "ci95_low": ci95_low,
        "ci95_high": ci95_high,
        "cv_pct": cv_pct,
    }


def build_summaries(
    result_root: Path,
    all_request_rows: list[dict[str, Any]],
    repeat_results: list[RepeatResult],
    ci_samples: int,
) -> None:
    request_df = pd.DataFrame(all_request_rows)
    success_df = request_df[request_df["http_status"] == 200].copy() if not request_df.empty else pd.DataFrame()

    repeats_df = pd.DataFrame(
        [
            {
                "workload": r.workload,
                "users": r.users,
                "repeat": r.repeat,
                "total_requests": r.total_requests,
                "success_count": r.success_count,
                "error_count": r.error_count,
                "elapsed_s": r.elapsed_s,
                "throughput_rps": r.throughput_rps,
                "success_rate_pct": (r.success_count / r.total_requests * 100.0) if r.total_requests > 0 else 0.0,
                "output_dir": str(r.output_dir),
            }
            for r in repeat_results
        ]
    )
    repeats_df.to_csv(result_root / "repeat_level_summary.csv", index=False)

    metric_columns = [
        "client_latency_ms",
        "total_pipeline_ms",
        "model_latency_ms",
        "tool_total_ms",
        "tool_processing_ms",
        "mcp_protocol_overhead_ms",
        "pipeline_overhead_ms",
        "protocol_overhead_pct",
    ]

    long_rows: list[dict[str, Any]] = []

    if not success_df.empty:
        grouped = success_df.groupby(["workload", "users"], dropna=False)
        for (workload, users), group in grouped:
            for metric in metric_columns:
                stat = summarize_metric(group[metric], ci_samples=ci_samples)
                long_rows.append(
                    {
                        "workload": workload,
                        "users": int(users),
                        "metric": metric,
                        **stat,
                    }
                )

    if not repeats_df.empty:
        tp_grouped = repeats_df.groupby(["workload", "users"], dropna=False)
        for (workload, users), group in tp_grouped:
            stat = summarize_metric(group["throughput_rps"], ci_samples=ci_samples)
            long_rows.append(
                {
                    "workload": workload,
                    "users": int(users),
                    "metric": "throughput_rps",
                    **stat,
                }
            )

    long_df = pd.DataFrame(long_rows)
    long_df.to_csv(result_root / "summary_statistics_long.csv", index=False)

    if long_df.empty:
        pd.DataFrame().to_csv(result_root / "summary_statistics_wide.csv", index=False)
        return

    wide_df = long_df.pivot_table(
        index=["workload", "users"],
        columns="metric",
        values=["median", "iqr", "ci95_low", "ci95_high", "cv_pct", "mean", "std", "count"],
        aggfunc="first",
    )
    wide_df.columns = [f"{stat}__{metric}" for stat, metric in wide_df.columns]
    wide_df = wide_df.reset_index().sort_values(["workload", "users"])
    wide_df.to_csv(result_root / "summary_statistics_wide.csv", index=False)


async def main() -> None:
    args = parse_args()

    result_root = ensure_dir(Path(args.result_root))
    ensure_dir(result_root / "experiments")

    manifest = {
        "created_at": utc_now_iso(),
        "host": args.host,
        "prometheus_url": args.prometheus_url,
        "users": args.users,
        "workloads": args.workloads,
        "repeats": args.repeats,
        "requests_per_user": args.requests_per_user,
        "warmup_seconds": args.warmup_seconds,
        "ci_bootstrap_samples": args.ci_bootstrap_samples,
        "model_backend_expected": args.model_backend,
    }

    with (result_root / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    await check_health(args.host)

    all_requests: list[dict[str, Any]] = []
    all_repeats: list[RepeatResult] = []
    coverage_rows: list[dict[str, Any]] = []

    workload_defs: list[tuple[Path, dict[str, Any], str]] = []
    for w in args.workloads:
        path = Path(w)
        payload, workload_name = load_workload(path)
        workload_defs.append((path, payload, workload_name))

    for _, payload, workload_name in workload_defs:
        for users in args.users:
            for repeat in range(1, args.repeats + 1):
                for transport in ["sse", "stdio"]:
                    if args.warmup_seconds > 0:
                        await asyncio.sleep(args.warmup_seconds)

                    repeat_dir = (
                        result_root
                        / "experiments"
                        / transport
                        / workload_name
                        / f"users_{users}"
                        / f"repeat_{repeat}"
                    )

                    if args.dry_run:
                        print(f"[DRY-RUN] Would run: transport={transport} workload={workload_name} users={users} repeat={repeat}")
                        continue

                    # Update transport and model in workload payload
                    payload["workload"]["transport"] = transport
                    payload["workload"]["model"] = args.model_backend

                    repeat_result = await run_single_repeat(
                        host=args.host,
                        prom_url=args.prometheus_url,
                        request_payload=payload,
                        workload_name=f"{workload_name}_{transport}",
                        users=users,
                        requests_per_user=args.requests_per_user,
                        repeat_index=repeat,
                        output_dir=repeat_dir,
                    )
                    all_repeats.append(repeat_result)

                    repeat_requests = []
                    request_log_file = repeat_dir / "requests.jsonl"
                    with request_log_file.open("r", encoding="utf-8") as f:
                        for line in f:
                            row = json.loads(line)
                            row["transport"] = transport
                            repeat_requests.append(row)
                            all_requests.append(row)

                    filtered_log_dir = ensure_dir(repeat_dir / "filtered_logs")
                    agent_matches = filter_logs_for_trace_ids(
                        Path(args.agent_log),
                        repeat_result.trace_ids,
                        filtered_log_dir / "agent_host.jsonl",
                    )
                    tool_matches = filter_logs_for_trace_ids(
                        Path(args.tool_log),
                        repeat_result.trace_ids,
                        filtered_log_dir / "tool_executor.jsonl",
                    )
                    echo_matches = filter_logs_for_trace_ids(
                        Path(args.echo_log),
                        repeat_result.trace_ids,
                        filtered_log_dir / "echo_tool.jsonl",
                    )
                    extra_matches = {}
                    for t in ["math", "search", "db", "file", "sleep"]:
                        log_path = Path(getattr(args, f"{t}_log"))
                        if log_path.exists():
                            extra_matches[f"{t}_log_matches"] = filter_logs_for_trace_ids(
                                log_path,
                                repeat_result.trace_ids,
                                filtered_log_dir / f"{t}_tool.jsonl",
                            )

                    summary = {
                        "timestamp": datetime.now().isoformat(),
                        "workload": workload_name,
                        "transport": transport,
                        "users": users,
                        "repeat": repeat,
                        "mean_latency_ms": repeat_result.mean_latency_ms,
                        "p95_latency_ms": repeat_result.p95_latency_ms,
                        "throughput_rps": repeat_result.throughput_rps,
                        "error_rate": repeat_result.error_rate,
                        "filtered_logs": {
                            "agent_log_matches": agent_matches,
                            "tool_log_matches": tool_matches,
                            "echo_log_matches": echo_matches,
                            **extra_matches
                        },
                    }
                    coverage_rows.append(
                        {
                            "transport": transport,
                            "workload": workload_name,
                            "users": users,
                            "repeat": repeat,
                            "requests_expected": users * args.requests_per_user,
                            "requests_observed": len(repeat_requests),
                            "success_count": repeat_result.success_count,
                            "error_count": repeat_result.error_count,
                            "throughput_rps": repeat_result.throughput_rps,
                            "trace_ids": len(repeat_result.trace_ids),
                            "agent_log_matches": agent_matches,
                            "tool_log_matches": tool_matches,
                            "echo_log_matches": echo_matches,
                            "output_dir": str(repeat_result.output_dir),
                        }
                    )

                    print(
                        f"[DONE] transport={transport} workload={workload_name} users={users} repeat={repeat} "
                        f"ok={repeat_result.success_count}/{repeat_result.total_requests} "
                        f"throughput={repeat_result.throughput_rps:.2f} rps"
                    )

    if not args.dry_run:
        coverage_df = pd.DataFrame(coverage_rows).sort_values(["transport", "workload", "users", "repeat"])
        coverage_df.to_csv(result_root / "dataset_coverage.csv", index=False)

        build_summaries(
            result_root=result_root,
            all_request_rows=all_requests,
            repeat_results=all_repeats,
            ci_samples=args.ci_bootstrap_samples,
        )

        print("\nLive LLM stress dataset generation complete")
        print(f"Artifacts written to: {result_root}")
    else:
        print("\nDry-run complete. No artifacts written.")


if __name__ == "__main__":
    asyncio.run(main())
