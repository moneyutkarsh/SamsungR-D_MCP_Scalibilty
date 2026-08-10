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
    parser.add_argument("--infra-results", default="data/results/baseline_mockadapter/summary_statistics_long.csv")
    parser.add_argument("--llm-results", default="data/results/live_llm/summary_statistics_long.csv")
    parser.add_argument("--output-dir", default="docs/reports/figures")
    args = parser.parse_args()

    out_dir = ensure_dir(Path(args.output_dir))

    # 1. Analyze Infrastructure Results (Mock Adapter)
    infra_csv = Path(args.infra_results)
    if infra_csv.exists():
        df_infra = pd.read_csv(infra_csv)
        if not df_infra.empty and "transport" in df_infra.columns:
            # Saturation curves (Throughput vs Concurrency)
            plt.figure(figsize=(10, 6))
            tp_df = df_infra[df_infra["metric"] == "throughput_rps"]
            if not tp_df.empty:
                sns.lineplot(data=tp_df, x="users", y="mean", hue="transport", style="workload", markers=True)
                plt.title("Saturation Curves: Throughput vs Concurrency")
                plt.ylabel("Throughput (Requests/sec)")
                plt.xlabel("Concurrent Users")
                plt.savefig(out_dir / "saturation_curves.png")
            plt.close()

            # SSE vs Stdio Overhead
            plt.figure(figsize=(10, 6))
            overhead_df = df_infra[df_infra["metric"] == "mcp_protocol_overhead_ms"]
            if not overhead_df.empty:
                sns.boxplot(data=overhead_df, x="workload", y="mean", hue="transport")
                plt.title("Protocol Overhead: SSE vs Stdio")
                plt.ylabel("Overhead Latency (ms)")
                plt.xticks(rotation=45)
                plt.tight_layout()
                plt.savefig(out_dir / "transport_overhead_boxplot.png")
            plt.close()

    # 2. Analyze Live LLM Results (Cognitive Stress)
    llm_csv = Path(args.llm_results)
    if llm_csv.exists():
        df_llm = pd.read_csv(llm_csv)
        if not df_llm.empty and "metric" in df_llm.columns:
            # Cost ($) per workflow vs Concurrency
            plt.figure(figsize=(10, 6))
            cost_df = df_llm[df_llm["metric"] == "cost_usd"]
            if not cost_df.empty:
                sns.lineplot(data=cost_df, x="users", y="mean", hue="workload", markers=True)
                plt.title("LLM Cost Scaling: Average Cost per Workflow")
                plt.ylabel("Cost (USD)")
                plt.xlabel("Concurrent Users")
                plt.savefig(out_dir / "llm_cost_scaling.png")
            plt.close()

            # Error Recovery Rates (tool recovery count)
            plt.figure(figsize=(10, 6))
            recovery_df = df_llm[df_llm["metric"] == "mcp_tool_recovery_total"]
            if not recovery_df.empty:
                sns.barplot(data=recovery_df, x="workload", y="mean", hue="users")
                plt.title("Error Recovery Rates by Workload")
                plt.ylabel("Average Recoveries per Workflow")
                plt.xticks(rotation=45)
                plt.tight_layout()
                plt.savefig(out_dir / "error_recovery_rates.png")
            plt.close()

    print(f"Scalability plots generated in {out_dir}")

if __name__ == "__main__":
    main()
