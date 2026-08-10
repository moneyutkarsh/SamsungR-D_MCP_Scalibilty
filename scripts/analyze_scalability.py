#!/usr/bin/env python3
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path

def main():
    parser = argparse.ArgumentParser(description="Analyze Scalability Results")
    parser.add_argument("--summary-results", default="data/results/live_llm/summary_statistics_long.csv")
    parser.add_argument("--raw-infra-logs", default="data/logs/agent_host.jsonl")
    parser.add_argument("--raw-llm-logs", default="data/results/live_llm/raw_results.jsonl")
    parser.add_argument("--output-dir", default="docs/reports/figures")
    args = parser.parse_args()

    out_dir = ensure_dir(Path(args.output_dir))

    # Read summary statistics if available
    df_summary = pd.DataFrame()
    if Path(args.summary_results).exists():
        df_summary = pd.read_csv(args.summary_results)
    
    # Read raw logs
    raw_dfs = []
    for raw_path in [args.raw_infra_logs, args.raw_llm_logs]:
        p = Path(raw_path)
        if p.exists():
            try:
                # Some logs might be JSONL, others CSV. Assuming JSONL based on prompt.
                raw_dfs.append(pd.read_json(p, lines=True))
            except Exception as e:
                print(f"Failed to read {p}: {e}")
                
    if raw_dfs:
        df_raw = pd.concat(raw_dfs, ignore_index=True)
    else:
        df_raw = pd.DataFrame()

    if df_raw.empty:
        print("No raw data found. Exiting plotting.")
        return

    # Unpack nested metrics column if it exists
    if "metrics" in df_raw.columns:
        # Drop rows where metrics is not a dict
        df_raw = df_raw.dropna(subset=["metrics"])
        metrics_df = pd.json_normalize(df_raw["metrics"])
        df_raw = pd.concat([df_raw.drop(columns=["metrics"]).reset_index(drop=True), metrics_df.reset_index(drop=True)], axis=1)

    # Ensure required columns exist for plotting, fill with defaults if missing
    for col in ["transport", "workload", "users", "model_backend"]:
        if col not in df_raw.columns:
            df_raw[col] = "unknown"

    # Pre-process raw data to compute missing fields if necessary
    if "total_pipeline_ms" not in df_raw.columns and "client_latency_ms" in df_raw.columns:
        df_raw["total_pipeline_ms"] = df_raw["client_latency_ms"]
    
    if "mcp_protocol_overhead_ms" not in df_raw.columns:
        df_raw["mcp_protocol_overhead_ms"] = 0.0

    # 1. Saturation Curves (Throughput vs Concurrency)
    # If summary stats are available, use them; otherwise, approximate RPS from raw
    plt.figure(figsize=(10, 6))
    if not df_summary.empty and "metric" in df_summary.columns:
        tp_df = df_summary[df_summary["metric"] == "throughput_rps"]
        if not tp_df.empty:
            sns.lineplot(data=tp_df, x="users", y="mean", hue="transport", style="workload", markers=True)
    else:
        # Approximate RPS from raw: count requests per user/workload group and assume 1 minute test duration
        rps_df = df_raw.groupby(["users", "transport", "workload"]).size().reset_index(name="count")
        rps_df["rps"] = rps_df["count"] / 60.0 # Assuming 60s test
        sns.lineplot(data=rps_df, x="users", y="rps", hue="transport", style="workload", markers=True)
    
    plt.title("Saturation Curves: Throughput vs Concurrency")
    plt.ylabel("Throughput (Requests/sec)")
    plt.xlabel("Concurrent Users")
    plt.tight_layout()
    plt.savefig(out_dir / "saturation_curves.png", dpi=300)
    plt.close()

    # 2. Latency Decomposition (Stacked Bar Chart at 100 users)
    df_100 = df_raw[df_raw["users"] == 100]
    if not df_100.empty:
        # Ensure decomposition columns exist
        decomp_cols = ["model_latency_ms", "tool_total_ms", "mcp_protocol_overhead_ms", "pipeline_overhead_ms"]
        for col in decomp_cols:
            if col not in df_100.columns:
                df_100[col] = 0.0
                
        agg_100 = df_100.groupby("workload")[decomp_cols].mean()
        agg_100.plot(kind="bar", stacked=True, figsize=(10, 6), colormap="viridis")
        plt.title("Latency Decomposition across Workloads (100 Users)")
        plt.ylabel("Latency (ms)")
        plt.xlabel("Workload")
        plt.xticks(rotation=45)
        plt.legend(title="Components", bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        plt.savefig(out_dir / "latency_decomposition.png", dpi=300)
        plt.close()

    # 3. Protocol Overhead %
    plt.figure(figsize=(10, 6))
    # Calculate % overhead per request
    if "total_pipeline_ms" in df_raw.columns:
        df_raw["protocol_overhead_pct"] = (df_raw["mcp_protocol_overhead_ms"] / df_raw["total_pipeline_ms"].replace(0, 1)) * 100
        sns.lineplot(data=df_raw, x="users", y="protocol_overhead_pct", hue="transport", style="workload", markers=True, errorbar=None)
        plt.axhline(y=20, color='r', linestyle='--', label="20% Threshold")
        plt.title("Protocol Overhead as % of Total Latency")
        plt.ylabel("Protocol Overhead (%)")
        plt.xlabel("Concurrent Users")
        plt.legend()
        plt.tight_layout()
        plt.savefig(out_dir / "protocol_overhead_pct.png", dpi=300)
    plt.close()

    # 4. Transport Overhead Boxplot
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df_raw, x="workload", y="mcp_protocol_overhead_ms", hue="transport")
    plt.title("Protocol Overhead: SSE vs Stdio")
    plt.ylabel("Overhead Latency (ms)")
    plt.xlabel("Workload")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(out_dir / "transport_overhead_boxplot.png", dpi=300)
    plt.close()

    # 5. Latency ECDF Plot (100 vs 500 users)
    plt.figure(figsize=(10, 6))
    df_ecdf = df_raw[df_raw["users"].isin([100, 500])]
    if not df_ecdf.empty and "total_pipeline_ms" in df_ecdf.columns:
        sns.ecdfplot(data=df_ecdf, x="total_pipeline_ms", hue="workload", style="users")
        plt.title("ECDF of Pipeline Latency (100 vs 500 Users)")
        plt.xlabel("Total Pipeline Latency (ms)")
        plt.ylabel("Cumulative Probability")
        plt.tight_layout()
        plt.savefig(out_dir / "latency_cdf.png", dpi=300)
    plt.close()

    # 6. Cost vs Latency
    plt.figure(figsize=(10, 6))
    if "cost_usd" in df_raw.columns and "total_pipeline_ms" in df_raw.columns:
        # Group by model_backend and workload
        cost_df = df_raw.groupby(["model_backend", "workload"])[["cost_usd", "total_pipeline_ms"]].mean().reset_index()
        sns.scatterplot(data=cost_df, x="total_pipeline_ms", y="cost_usd", hue="model_backend", style="workload", s=100)
        plt.title("LLM Cost vs Latency by Model")
        plt.xlabel("Average Total Pipeline Latency (ms)")
        plt.ylabel("Average Cost per Workflow (USD)")
        plt.tight_layout()
        plt.savefig(out_dir / "llm_cost_and_cross_model.png", dpi=300)
    plt.close()

    print(f"All research-grade scalability plots generated in {out_dir}")

if __name__ == "__main__":
    main()
