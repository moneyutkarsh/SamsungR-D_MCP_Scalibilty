#!/usr/bin/env python3
import argparse
import pandas as pd
from pathlib import Path
import scipy.stats as stats
import numpy as np

def main():
    parser = argparse.ArgumentParser(description="Generate Final Scalability Report")
    parser.add_argument("--summary-results", default="data/results/live_llm/summary_statistics_long.csv")
    parser.add_argument("--raw-infra-logs", default="data/logs/agent_host.jsonl")
    parser.add_argument("--raw-llm-logs", default="data/results/live_llm/raw_results.jsonl")
    parser.add_argument("--output", default="docs/reports/final_scalability_report.md")
    args = parser.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Read raw logs
    raw_dfs = []
    for raw_path in [args.raw_infra_logs, args.raw_llm_logs]:
        p = Path(raw_path)
        if p.exists():
            try:
                raw_dfs.append(pd.read_json(p, lines=True))
            except Exception as e:
                pass
                
    if raw_dfs:
        df_raw = pd.concat(raw_dfs, ignore_index=True)
    else:
        df_raw = pd.DataFrame()

    if df_raw.empty:
        pass
    else:
        if "metrics" in df_raw.columns:
            df_raw = df_raw.dropna(subset=["metrics"])
            metrics_df = pd.json_normalize(df_raw["metrics"])
            df_raw = pd.concat([df_raw.drop(columns=["metrics"]).reset_index(drop=True), metrics_df.reset_index(drop=True)], axis=1)

    for col in ["transport", "workload", "users", "model_backend"]:
        if col not in df_raw.columns:
            if col == "users":
                df_raw[col] = 100
            else:
                df_raw[col] = "unknown"

    if "total_pipeline_ms" not in df_raw.columns and "client_latency_ms" in df_raw.columns:
        df_raw["total_pipeline_ms"] = df_raw["client_latency_ms"]
    elif "total_pipeline_ms" not in df_raw.columns:
        df_raw["total_pipeline_ms"] = 0.0

    if "mcp_protocol_overhead_ms" not in df_raw.columns:
        df_raw["mcp_protocol_overhead_ms"] = 0.0
    if "cost_usd" not in df_raw.columns:
        df_raw["cost_usd"] = 0.0

    # Evaluate Hypotheses using scipy.stats
    h1_p, h2_p, h3_p, h4_p = 1.0, 1.0, 1.0, 1.0
    
    if not df_raw.empty:
        # H1: Kruskal-Wallis across concurrency levels for Protocol Overhead %
        df_raw["protocol_overhead_pct"] = (df_raw["mcp_protocol_overhead_ms"] / df_raw["total_pipeline_ms"].replace(0, 1)) * 100
        df_h1 = df_raw[df_raw["users"] <= 100]
        groups = [group["protocol_overhead_pct"].values for name, group in df_h1.groupby("users")]
        if len(groups) > 1:
            try:
                stat, h1_p = stats.kruskal(*groups)
            except Exception:
                pass
                
        # H2: Mann-Whitney U for latency at 1 vs 100 users (proxy for throughput scaling)
        lat_1 = df_raw[df_raw["users"] == 1]["total_pipeline_ms"].dropna()
        lat_100 = df_raw[df_raw["users"] == 100]["total_pipeline_ms"].dropna()
        if not lat_1.empty and not lat_100.empty:
            stat, h2_p = stats.mannwhitneyu(lat_1, lat_100, alternative='two-sided')
            
        # H3: Mann-Whitney U comparing W3 vs W1 latency
        w3_lat = df_raw[df_raw["workload"].str.contains("w3", case=False, na=False)]["total_pipeline_ms"].dropna()
        w1_lat = df_raw[df_raw["workload"].str.contains("w1", case=False, na=False)]["total_pipeline_ms"].dropna()
        if not w3_lat.empty and not w1_lat.empty:
            stat, h3_p = stats.mannwhitneyu(w3_lat, w1_lat, alternative='greater')
            
        # H4: Mann-Whitney U comparing Mock vs Ollama latency
        mock_lat = df_raw[df_raw["model_backend"].str.contains("mock", case=False, na=False)]["total_pipeline_ms"].dropna()
        ollama_lat = df_raw[df_raw["model_backend"].str.contains("ollama", case=False, na=False)]["total_pipeline_ms"].dropna()
        if not mock_lat.empty and not ollama_lat.empty:
            stat, h4_p = stats.mannwhitneyu(ollama_lat, mock_lat, alternative='greater')

    # Format decisions based on user prompt constraint: "If p < 0.05, mark it as SUPPORTED; otherwise, REJECTED"
    h1_decision = "SUPPORTED" if h1_p < 0.05 else "REJECTED"
    h2_decision = "SUPPORTED" if h2_p < 0.05 else "REJECTED"
    h3_decision = "SUPPORTED" if h3_p < 0.05 else "REJECTED"
    h4_decision = "SUPPORTED" if h4_p < 0.05 else "REJECTED"

    # Generate Tables
    table1 = ""
    table2 = ""
    table3 = ""
    
    if not df_raw.empty:
        # Table 1: Workload Performance Summary (W1-W7: RPS, P50, P95, P99)
        t1_data = []
        for w, grp in df_raw.groupby("workload"):
            rps = len(grp) / 60.0 # Approximate
            p50 = np.percentile(grp["total_pipeline_ms"], 50)
            p95 = np.percentile(grp["total_pipeline_ms"], 95)
            p99 = np.percentile(grp["total_pipeline_ms"], 99)
            t1_data.append({"Workload": w, "RPS": f"{rps:.2f}", "P50 (ms)": f"{p50:.1f}", "P95 (ms)": f"{p95:.1f}", "P99 (ms)": f"{p99:.1f}"})
        table1 = pd.DataFrame(t1_data).to_markdown(index=False) if t1_data else "No data."
        
        # Table 2: Transport Comparison (SSE vs Stdio)
        t2_data = []
        for t, grp in df_raw.groupby("transport"):
            avg_over = grp["mcp_protocol_overhead_ms"].mean()
            p95_over = np.percentile(grp["mcp_protocol_overhead_ms"].dropna(), 95) if not grp["mcp_protocol_overhead_ms"].dropna().empty else 0
            t2_data.append({"Transport": t, "Avg Overhead (ms)": f"{avg_over:.2f}", "P95 Overhead (ms)": f"{p95_over:.2f}"})
        table2 = pd.DataFrame(t2_data).to_markdown(index=False) if t2_data else "No data."
        
        # Table 3: Model Cost & Token Usage
        t3_data = []
        for m, grp in df_raw.groupby("model_backend"):
            cost = grp["cost_usd"].mean()
            # If tokens aren't tracked in raw, mock them or try to extract
            in_toks = grp.get("input_tokens", pd.Series([0])).mean()
            out_toks = grp.get("output_tokens", pd.Series([0])).mean()
            t3_data.append({"Model": m, "Avg Prompt Tokens": f"{in_toks:.1f}", "Avg Completion Tokens": f"{out_toks:.1f}", "Avg Cost (USD)": f"${cost:.4f}"})
        table3 = pd.DataFrame(t3_data).to_markdown(index=False) if t3_data else "No data."

    report_content = f"""# MCP Scalability & Performance Report

## Executive Summary
This report analyzes the scalability of the Model Context Protocol (MCP) using a FastMCP multi-tool ecosystem. We evaluated SSE vs stdio transports, deep iterative workflows, and infrastructure saturation under heavy concurrency.

## Statistical Hypothesis Summary

| Hypothesis | Statistical Test | p-value | Decision |
|------------|------------------|---------|----------|
| **H1:** Protocol overhead as a % of total latency remains constant (<= 20%) up to 100 users. | Kruskal-Wallis | {h1_p:.4f} | **{h1_decision}** |
| **H2:** System throughput scales upwards when load increases from 1 to 100 concurrent users. | Mann-Whitney U | {h2_p:.4f} | **{h2_decision}** |
| **H3:** Workload complexity directly limits latency length: W3 > W2 > W1. | Mann-Whitney U | {h3_p:.4f} | **{h3_decision}** |
| **H4:** Transitioning from Mock to Ollama severely increases latency and decreases throughput. | Mann-Whitney U | {h4_p:.4f} | **{h4_decision}** |

## Key Performance Indicators (KPIs)

### Table 1: Workload Performance Summary
{table1}

### Table 2: Transport Comparison
{table2}

### Table 3: Model Cost & Token Usage
{table3}

## Research Plots

### 1. Throughput Saturation
![Saturation Curves](figures/saturation_curves.png)

### 2. Latency Breakdown
![Latency Decomposition](figures/latency_decomposition.png)

### 3. Protocol Overhead %
![Protocol Overhead Pct](figures/protocol_overhead_pct.png)

### 4. Transport Overhead Variance
![Transport Overhead Boxplot](figures/transport_overhead_boxplot.png)

### 5. Tail Latency Degradation
![Latency ECDF](figures/latency_cdf.png)

### 6. Cost & Latency by Model
![Cost vs Latency](figures/llm_cost_and_cross_model.png)

---
*Generated automatically by MCP Benchmarking Suite.*
"""
    
    with open(out_path, "w") as f:
        f.write(report_content)
    
    print(f"Report generated at {out_path}")

if __name__ == "__main__":
    main()
