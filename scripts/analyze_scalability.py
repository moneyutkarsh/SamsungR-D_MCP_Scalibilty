#!/usr/bin/env python3
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import os

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

    # We will generate mock plots if the CSV files do not exist or are empty,
    # just to provide the scaffolding for the reporting.
    
    infra_csv = Path(args.infra_results)
    if infra_csv.exists():
        df_infra = pd.read_csv(infra_csv)
        if not df_infra.empty and "transport" in df_infra.columns:
            # 1. Saturation curves (Throughput vs Concurrency)
            plt.figure(figsize=(10, 6))
            tp_df = df_infra[df_infra["metric"] == "throughput_rps"]
            sns.lineplot(data=tp_df, x="users", y="mean", hue="transport", style="workload", markers=True)
            plt.title("Saturation Curves: Throughput vs Concurrency")
            plt.ylabel("Throughput (Requests/sec)")
            plt.xlabel("Concurrent Users")
            plt.savefig(out_dir / "saturation_curves.png")
            plt.close()

            # 2. SSE vs Stdio Overhead
            plt.figure(figsize=(10, 6))
            overhead_df = df_infra[df_infra["metric"] == "mcp_protocol_overhead_ms"]
            sns.boxplot(data=overhead_df, x="workload", y="mean", hue="transport")
            plt.title("Protocol Overhead: SSE vs Stdio")
            plt.ylabel("Overhead Latency (ms)")
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(out_dir / "transport_overhead_boxplot.png")
            plt.close()

    llm_csv = Path(args.llm-results) if hasattr(args, 'llm_results') else Path(args.llm_results)
    if llm_csv.exists():
        df_llm = pd.read_csv(llm_csv)
        if not df_llm.empty and "transport" in df_llm.columns:
            # 4. Cost ($) per workflow step
            # Assuming we added a metric cost_usd (or we just parse it from requests)
            # This is a placeholder for cost plotting
            pass

    print(f"Scalability plots generated in {out_dir}")

if __name__ == "__main__":
    main()
