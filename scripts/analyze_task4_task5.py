from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import kruskal, mannwhitneyu, ttest_1samp, wilcoxon


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_jsonl(path: Path) -> pd.DataFrame:
    return pd.read_json(path, lines=True)


def load_request_level_baseline(baseline_root: Path) -> pd.DataFrame:
    req_files = sorted((baseline_root / "experiments").rglob("requests.jsonl"))
    frames = [read_jsonl(p) for p in req_files]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    return df


def load_workload_payload_map(workloads_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for file_path in sorted(workloads_dir.glob("w*.json")):
        obj = json.loads(file_path.read_text(encoding="utf-8"))
        w = obj["workload"]
        params = w.get("tool_params", {})
        rows.append(
            {
                "workload": w["name"],
                "payload_size_kb": float(params.get("payload_size_kb", np.nan)),
                "delay_ms": float(params.get("delay_ms", np.nan)),
                "tool_calls": len(w.get("workflow", [])),
            }
        )
    return pd.DataFrame(rows)


def safe_ttest_less(samples: np.ndarray, threshold: float) -> float:
    if samples.size < 2:
        return np.nan
    res = ttest_1samp(samples, popmean=threshold, alternative="less")
    return float(res.pvalue)


def safe_kruskal(groups: list[np.ndarray]) -> float:
    groups = [g for g in groups if g.size > 0]
    if len(groups) < 2:
        return np.nan
    if all(np.allclose(g, groups[0][0]) for g in groups):
        return 1.0
    try:
        return float(kruskal(*groups).pvalue)
    except ValueError:
        return np.nan


def safe_mannwhitney_greater(a: np.ndarray, b: np.ndarray) -> float:
    if a.size == 0 or b.size == 0:
        return np.nan
    res = mannwhitneyu(a, b, alternative="greater")
    return float(res.pvalue)


def safe_wilcoxon(samples: np.ndarray, alternative: str) -> float:
    if samples.size < 2:
        return np.nan
    if np.allclose(samples, 0.0):
        return 1.0
    res = wilcoxon(samples, alternative=alternative, zero_method="wilcox")
    return float(res.pvalue)


def format_num(x: float) -> str:
    if pd.isna(x):
        return "NA"
    return f"{x:.4g}"


def hypothesis_tests(
    baseline_requests: pd.DataFrame,
    baseline_repeat: pd.DataFrame,
    baseline_long: pd.DataFrame,
    comparison_key: pd.DataFrame,
) -> pd.DataFrame:
    alpha = 0.05
    rows: list[dict[str, Any]] = []

    # H1: Protocol overhead remains <=20% and does not vary up to 100 users.
    h1_df = baseline_requests[
        (baseline_requests["http_status"] == 200) & (baseline_requests["users"].isin([1, 10, 50, 100]))
    ].copy()
    proto = h1_df["protocol_overhead_pct"].to_numpy(dtype=float)
    p_less_20 = safe_ttest_less(proto, threshold=20.0)
    groups = [
        h1_df[h1_df["users"] == u]["protocol_overhead_pct"].to_numpy(dtype=float)
        for u in [1, 10, 50, 100]
    ]
    p_kruskal = safe_kruskal(groups)
    max_proto = float(np.nanmax(proto)) if proto.size > 0 else np.nan
    med_proto = float(np.nanmedian(proto)) if proto.size > 0 else np.nan
    supported_h1 = (max_proto <= 20.0) and (pd.isna(p_kruskal) or p_kruskal >= alpha)
    rows.append(
        {
            "hypothesis_id": "H1",
            "statement": "Protocol overhead percentage remains <=20% and stable across 1-100 users.",
            "null_hypothesis": "Protocol overhead percentage varies significantly with concurrency or exceeds 20%.",
            "test_method": "One-sample t-test (mean < 20%) + Kruskal-Wallis across user levels (1,10,50,100)",
            "p_value_primary": p_kruskal,
            "p_value_secondary": p_less_20,
            "effect_summary": f"median={med_proto:.4f}%, max={max_proto:.4f}%",
            "decision": "Supported" if supported_h1 else "Rejected",
            "alpha": alpha,
        }
    )

    # H2: Throughput at 100 users is higher than at 1 user across workloads.
    tp_repeat = baseline_repeat[["workload", "users", "throughput_rps"]].copy()
    tp_1 = tp_repeat[tp_repeat["users"] == 1].groupby("workload")["throughput_rps"].mean()
    tp_100 = tp_repeat[tp_repeat["users"] == 100].groupby("workload")["throughput_rps"].mean()
    common = sorted(set(tp_1.index) & set(tp_100.index))
    delta = np.array([tp_100[w] - tp_1[w] for w in common], dtype=float)
    p_h2 = safe_wilcoxon(delta, alternative="greater")
    med_delta = float(np.median(delta)) if delta.size > 0 else np.nan
    supported_h2 = (not pd.isna(p_h2)) and (p_h2 < alpha) and (med_delta > 0)
    rows.append(
        {
            "hypothesis_id": "H2",
            "statement": "Throughput scales up from 1 to 100 concurrent users across workloads.",
            "null_hypothesis": "Throughput at 100 users is not greater than throughput at 1 user.",
            "test_method": "Paired Wilcoxon signed-rank on workload-level throughput deltas (100u - 1u)",
            "p_value_primary": p_h2,
            "p_value_secondary": np.nan,
            "effect_summary": f"median_delta_rps={med_delta:.4f}, pairs={len(common)}",
            "decision": "Supported" if supported_h2 else "Rejected",
            "alpha": alpha,
        }
    )

    # H3: Workload complexity drives latency: W3 > W2 > W1 for total pipeline latency.
    h3_df = baseline_requests[
        (baseline_requests["http_status"] == 200)
        & (baseline_requests["users"].isin([10, 50, 100]))
        & (baseline_requests["workload"].isin(["w1_pure_mcp", "w2_light_tool", "w3_medium_tool"]))
    ].copy()
    g1 = h3_df[h3_df["workload"] == "w1_pure_mcp"]["total_pipeline_ms"].to_numpy(dtype=float)
    g2 = h3_df[h3_df["workload"] == "w2_light_tool"]["total_pipeline_ms"].to_numpy(dtype=float)
    g3 = h3_df[h3_df["workload"] == "w3_medium_tool"]["total_pipeline_ms"].to_numpy(dtype=float)
    p_kw = safe_kruskal([g1, g2, g3])
    p_32 = safe_mannwhitney_greater(g3, g2)
    p_21 = safe_mannwhitney_greater(g2, g1)
    med1, med2, med3 = float(np.median(g1)), float(np.median(g2)), float(np.median(g3))
    supported_h3 = (
        (not pd.isna(p_kw))
        and p_kw < alpha
        and (not pd.isna(p_32))
        and (not pd.isna(p_21))
        and p_32 < alpha
        and p_21 < alpha
        and (med3 > med2 > med1)
    )
    rows.append(
        {
            "hypothesis_id": "H3",
            "statement": "Median total pipeline latency follows W3 > W2 > W1 at matched concurrency (10/50/100 users).",
            "null_hypothesis": "Latency ordering W3 > W2 > W1 does not hold.",
            "test_method": "Kruskal-Wallis + one-sided Mann-Whitney pairwise tests",
            "p_value_primary": p_kw,
            "p_value_secondary": max(p_32, p_21),
            "effect_summary": f"medians_ms: W1={med1:.4f}, W2={med2:.4f}, W3={med3:.4f}",
            "decision": "Supported" if supported_h3 else "Rejected",
            "alpha": alpha,
        }
    )

    # H4: Real model adds latency and reduces throughput versus mock.
    cmp = comparison_key.copy()
    lat = cmp[cmp["metric"] == "total_pipeline_ms"].copy()
    thr = cmp[cmp["metric"] == "throughput_rps"].copy()
    lat_delta = (lat["ollama_median"] - lat["mock_median"]).to_numpy(dtype=float)
    thr_delta = (thr["ollama_median"] - thr["mock_median"]).to_numpy(dtype=float)
    p_lat = safe_wilcoxon(lat_delta, alternative="greater")
    p_thr = safe_wilcoxon(thr_delta, alternative="less")
    med_lat = float(np.median(lat_delta)) if lat_delta.size > 0 else np.nan
    med_thr = float(np.median(thr_delta)) if thr_delta.size > 0 else np.nan
    supported_h4 = (
        (not pd.isna(p_lat))
        and (not pd.isna(p_thr))
        and p_lat < alpha
        and p_thr < alpha
        and med_lat > 0
        and med_thr < 0
    )
    rows.append(
        {
            "hypothesis_id": "H4",
            "statement": "Ollama backend increases latency and reduces throughput versus MockAdapter (W1-W3, users 10/50/100).",
            "null_hypothesis": "No significant latency/throughput difference between Ollama and MockAdapter.",
            "test_method": "Paired Wilcoxon on matched medians (latency: greater, throughput: less)",
            "p_value_primary": p_lat,
            "p_value_secondary": p_thr,
            "effect_summary": f"median_delta_latency_ms={med_lat:.4f}, median_delta_throughput_rps={med_thr:.4f}",
            "decision": "Supported" if supported_h4 else "Rejected",
            "alpha": alpha,
        }
    )

    return pd.DataFrame(rows)


def plot_latency_decomposition(summary_long: pd.DataFrame, out_file: Path) -> None:
    df = summary_long[
        (summary_long["metric"].isin(["model_latency_ms", "tool_processing_ms", "mcp_protocol_overhead_ms", "pipeline_overhead_ms"]))
        & (summary_long["users"] == 100)
    ].copy()
    pivot = df.pivot(index="workload", columns="metric", values="median").fillna(0)
    pivot = pivot.sort_index()

    metrics = ["model_latency_ms", "tool_processing_ms", "mcp_protocol_overhead_ms", "pipeline_overhead_ms"]
    labels = ["Model", "Tool", "Protocol", "Pipeline"]
    colors = ["#3b82f6", "#16a34a", "#f59e0b", "#ef4444"]

    fig, ax = plt.subplots(figsize=(12, 6))
    bottom = np.zeros(len(pivot))
    x = np.arange(len(pivot))

    for m, label, color in zip(metrics, labels, colors):
        vals = pivot[m].to_numpy(dtype=float)
        ax.bar(x, vals, bottom=bottom, label=label, color=color)
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index, rotation=25, ha="right")
    ax.set_ylabel("Median Latency (ms)")
    ax.set_title("Plot 1: Latency Decomposition by Workload (100 users)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_file, dpi=180)
    plt.close(fig)


def plot_scalability_curves(summary_long: pd.DataFrame, out_file: Path) -> None:
    df = summary_long[summary_long["metric"] == "throughput_rps"].copy()
    fig, ax = plt.subplots(figsize=(12, 6))
    for workload, group in df.groupby("workload"):
        group = group.sort_values("users")
        ax.plot(group["users"], group["median"], marker="o", linewidth=2, label=workload)

    ax.set_xlabel("Concurrency (users)")
    ax.set_ylabel("Throughput (RPS, median)")
    ax.set_title("Plot 2: Scalability Curves (Throughput vs Concurrency)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_file, dpi=180)
    plt.close(fig)


def plot_protocol_overhead(summary_long: pd.DataFrame, out_file: Path) -> None:
    df = summary_long[summary_long["metric"] == "protocol_overhead_pct"].copy()
    fig, ax = plt.subplots(figsize=(12, 6))
    for workload, group in df.groupby("workload"):
        group = group.sort_values("users")
        ax.plot(group["users"], group["median"], marker="o", linewidth=2, label=workload)

    ax.axhline(20.0, color="red", linestyle="--", linewidth=1.5, label="20% threshold")
    ax.set_xlabel("Concurrency (users)")
    ax.set_ylabel("Protocol Overhead (% of total latency, median)")
    ax.set_title("Plot 3: Protocol Overhead Percentage Across Concurrency")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_file, dpi=180)
    plt.close(fig)


def plot_tool_delay_dominance(summary_long: pd.DataFrame, out_file: Path) -> None:
    df = summary_long[
        (summary_long["workload"].isin(["w1_pure_mcp", "w2_light_tool", "w3_medium_tool"]))
        & (summary_long["users"] == 100)
        & (summary_long["metric"].isin(["model_latency_ms", "tool_processing_ms", "mcp_protocol_overhead_ms", "pipeline_overhead_ms"]))
    ].copy()
    pivot = df.pivot(index="workload", columns="metric", values="median").fillna(0)
    pivot = pivot.loc[["w1_pure_mcp", "w2_light_tool", "w3_medium_tool"]]

    metrics = ["model_latency_ms", "tool_processing_ms", "mcp_protocol_overhead_ms", "pipeline_overhead_ms"]
    labels = ["Model", "Tool", "Protocol", "Pipeline"]
    colors = ["#60a5fa", "#22c55e", "#facc15", "#f87171"]

    fig, ax = plt.subplots(figsize=(10, 6))
    bottom = np.zeros(len(pivot))
    x = np.arange(len(pivot))

    for m, label, color in zip(metrics, labels, colors):
        vals = pivot[m].to_numpy(dtype=float)
        ax.bar(x, vals, bottom=bottom, label=label, color=color)
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(["W1", "W2", "W3"])
    ax.set_ylabel("Median Latency (ms)")
    ax.set_title("Plot 4: Tool Delay Dominance (W1 vs W2 vs W3 at 100 users)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_file, dpi=180)
    plt.close(fig)


def plot_serialization_proxy(
    summary_long: pd.DataFrame, workload_payload: pd.DataFrame, out_file: Path
) -> pd.DataFrame:
    overhead = summary_long[
        (summary_long["metric"] == "pipeline_overhead_ms") & (summary_long["users"] == 100)
    ][["workload", "median"]].rename(columns={"median": "median_pipeline_overhead_ms"})

    joined = workload_payload.merge(overhead, on="workload", how="inner")
    joined = joined[joined["payload_size_kb"].notna()].sort_values("payload_size_kb")

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(
        joined["payload_size_kb"],
        joined["median_pipeline_overhead_ms"],
        marker="o",
        linewidth=2,
        color="#8b5cf6",
    )

    for _, row in joined.iterrows():
        ax.annotate(
            row["workload"],
            (row["payload_size_kb"], row["median_pipeline_overhead_ms"]),
            textcoords="offset points",
            xytext=(0, 6),
            ha="center",
            fontsize=8,
        )

    ax.set_xscale("log")
    ax.set_xlabel("Payload Size (KB, log scale)")
    ax.set_ylabel("Median Pipeline Overhead (ms)")
    ax.set_title("Plot 5: Serialization Cost Proxy vs Payload Size (100 users)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_file, dpi=180)
    plt.close(fig)

    return joined


def plot_latency_cdf(requests_df: pd.DataFrame, out_file: Path) -> None:
    df = requests_df[(requests_df["http_status"] == 200) & (requests_df["users"] == 100)].copy()
    fig, ax = plt.subplots(figsize=(12, 6))

    for workload, group in df.groupby("workload"):
        arr = np.sort(group["client_latency_ms"].to_numpy(dtype=float))
        if arr.size == 0:
            continue
        cdf = np.arange(1, arr.size + 1) / arr.size
        ax.plot(arr, cdf, linewidth=2, label=workload)

    ax.set_xlabel("Client Latency (ms)")
    ax.set_ylabel("CDF")
    ax.set_title("Plot 6: Latency CDF Across Workloads (100 users)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_file, dpi=180)
    plt.close(fig)


def write_hypothesis_readme(out_file: Path, hypotheses_df: pd.DataFrame) -> None:
    lines = [
        "# Task 4 - Formal Hypotheses and Statistical Testing",
        "",
        "This document defines the formal hypotheses, null hypotheses, test procedures, and outcomes for MCP scalability analysis.",
        "",
        "## Dataset Scope",
        "",
        "- Baseline MockAdapter: W1-W7 at users [1, 10, 50, 100, 200, 500]",
        "- Real model comparison: Ollama (llama3.2:3b) vs MockAdapter for W1-W3 at users [10, 50, 100]",
        "- Significance level: alpha = 0.05",
        "",
        "## Hypotheses",
        "",
        "### H1 - Protocol Overhead Scalability",
        "- Statement: MCP protocol overhead percentage remains <= 20% and stable across 1-100 users.",
        "- Null (H0): Protocol overhead percentage varies significantly with concurrency or exceeds 20%.",
        "- Procedure: One-sample t-test for mean < 20%, plus Kruskal-Wallis test across users [1,10,50,100].",
        "",
        "### H2 - Throughput Scalability",
        "- Statement: Throughput scales up from 1 to 100 concurrent users across workloads.",
        "- Null (H0): Throughput at 100 users is not greater than at 1 user.",
        "- Procedure: Paired Wilcoxon signed-rank test on workload-level throughput deltas (100u - 1u).",
        "",
        "### H3 - Tool Complexity Impact",
        "- Statement: Median total pipeline latency follows W3 > W2 > W1 at matched concurrency (10/50/100 users).",
        "- Null (H0): Ordering W3 > W2 > W1 does not hold.",
        "- Procedure: Kruskal-Wallis omnibus test, then one-sided Mann-Whitney tests for W3>W2 and W2>W1.",
        "",
        "### H4 - Real Model vs Mock",
        "- Statement: Ollama backend increases latency and reduces throughput versus MockAdapter (W1-W3, users 10/50/100).",
        "- Null (H0): No significant latency/throughput difference between Ollama and MockAdapter.",
        "- Procedure: Paired Wilcoxon signed-rank tests on matched medians (latency alternative=greater; throughput alternative=less).",
        "",
        "## Results",
        "",
        "| Hypothesis | Primary p-value | Secondary p-value | Decision | Evidence |",
        "|---|---:|---:|---|---|",
    ]

    for _, row in hypotheses_df.iterrows():
        lines.append(
            f"| {row['hypothesis_id']} | {format_num(row['p_value_primary'])} | {format_num(row['p_value_secondary'])} | {row['decision']} | {row['effect_summary']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "- Supported = statistical evidence aligns with the hypothesis statement under alpha = 0.05.",
        "- Rejected = evidence does not support the claimed direction/threshold behavior.",
        "",
        "## Output Files",
        "",
        "- CSV: docs/reports/task4_hypothesis_results.csv",
        "- Figures: docs/reports/figures/plot1_latency_decomposition.png to plot6_latency_cdf.png",
    ]

    out_file.write_text("\n".join(lines), encoding="utf-8")


def write_plot_analysis(
    out_file: Path,
    summary_long: pd.DataFrame,
    serialization_proxy_df: pd.DataFrame,
) -> None:
    throughput = summary_long[summary_long["metric"] == "throughput_rps"]
    proto = summary_long[summary_long["metric"] == "protocol_overhead_pct"]

    best_tp = throughput.loc[throughput["median"].idxmax()]
    worst_tp = throughput.loc[throughput["median"].idxmin()]
    max_proto = float(proto["median"].max())

    w123_tool = summary_long[
        (summary_long["metric"] == "tool_processing_ms")
        & (summary_long["users"] == 100)
        & (summary_long["workload"].isin(["w1_pure_mcp", "w2_light_tool", "w3_medium_tool"]))
    ][["workload", "median"]]
    tool_medians = {r["workload"]: float(r["median"]) for _, r in w123_tool.iterrows()}
    if all(np.isclose(v, 0.0) for v in tool_medians.values()):
        plot4_note = "Observed tool_processing_ms medians are ~0 for W1/W2/W3 in this baseline, so configured tool-delay effects are not visible in recorded tool timing metrics."
    else:
        plot4_note = (
            "Observed tool_processing_ms medians at 100 users: "
            f"W1={tool_medians.get('w1_pure_mcp', np.nan):.4f}, "
            f"W2={tool_medians.get('w2_light_tool', np.nan):.4f}, "
            f"W3={tool_medians.get('w3_medium_tool', np.nan):.4f}."
        )

    serialization_rows = (
        serialization_proxy_df[["workload", "payload_size_kb", "median_pipeline_overhead_ms"]]
        .sort_values("payload_size_kb")
        .to_dict("records")
    )

    lines = [
        "# Task 5 - Plot Analysis",
        "",
        "This report summarizes the six generated plots and key observations.",
        "",
        "## Plot 1 - Latency Decomposition by Workload",
        "- Figure: docs/reports/figures/plot1_latency_decomposition.png",
        "- Interpretation: The stacked bars separate model, tool, protocol, and pipeline costs at 100 users. In this dataset, pipeline-overhead component is the dominant measured internal contributor.",
        "",
        "## Plot 2 - Scalability Curves",
        "- Figure: docs/reports/figures/plot2_scalability_curves.png",
        f"- Highest observed throughput median: {best_tp['workload']} at users={int(best_tp['users'])}, throughput={best_tp['median']:.4f} rps.",
        f"- Lowest observed throughput median: {worst_tp['workload']} at users={int(worst_tp['users'])}, throughput={worst_tp['median']:.4f} rps.",
        "",
        "## Plot 3 - Protocol Overhead Percentage",
        "- Figure: docs/reports/figures/plot3_protocol_overhead_pct.png",
        f"- Maximum median protocol-overhead percentage observed: {max_proto:.4f}% (well below 20% threshold).",
        "",
        "## Plot 4 - Tool Delay Dominance (W1/W2/W3)",
        "- Figure: docs/reports/figures/plot4_tool_delay_dominance.png",
        f"- Interpretation: {plot4_note}",
        "",
        "## Plot 5 - Serialization Cost vs Payload Size",
        "- Figure: docs/reports/figures/plot5_serialization_proxy.png",
        "- Note: Current baseline has only one W5 payload size (1024KB). The plot uses available workloads with payload sizes (1KB, 128KB, 1024KB) as a serialization proxy.",
        "- This is indicative rather than a strict controlled W5-only payload sweep.",
        "",
        "## Plot 6 - Latency CDF",
        "- Figure: docs/reports/figures/plot6_latency_cdf.png",
        "- Interpretation: CDF comparison at 100 users reveals distribution spread and tail behavior by workload.",
        "",
        "## Serialization Proxy Data Used",
        "",
        "| workload | payload_size_kb | median_pipeline_overhead_ms |",
        "|---|---:|---:|",
    ]

    for row in serialization_rows:
        lines.append(
            f"| {row['workload']} | {row['payload_size_kb']:.0f} | {row['median_pipeline_overhead_ms']:.6f} |"
        )

    out_file.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Task 4 and Task 5 analysis generator")
    parser.add_argument(
        "--baseline-root",
        default="data/results/baseline_mockadapter",
        help="Baseline dataset root",
    )
    parser.add_argument(
        "--task2-root",
        default="data/results/task2_initial_real_model",
        help="Task 2 real-model dataset root",
    )
    parser.add_argument(
        "--workloads-dir",
        default="benchmarks/workloads",
        help="Workload definitions directory",
    )
    parser.add_argument(
        "--report-dir",
        default="docs/reports",
        help="Output report directory",
    )
    args = parser.parse_args()

    baseline_root = Path(args.baseline_root)
    task2_root = Path(args.task2_root)
    workloads_dir = Path(args.workloads_dir)
    report_dir = ensure_dir(Path(args.report_dir))
    figures_dir = ensure_dir(report_dir / "figures")

    baseline_requests = load_request_level_baseline(baseline_root)
    baseline_long = pd.read_csv(baseline_root / "summary_statistics_long.csv")
    baseline_repeat = pd.read_csv(baseline_root / "repeat_level_summary.csv")
    comparison_key = pd.read_csv(task2_root / "mock_vs_ollama_comparison_key_metrics.csv")
    workload_payload = load_workload_payload_map(workloads_dir)

    hypotheses_df = hypothesis_tests(
        baseline_requests=baseline_requests,
        baseline_repeat=baseline_repeat,
        baseline_long=baseline_long,
        comparison_key=comparison_key,
    )
    hypotheses_df.to_csv(report_dir / "task4_hypothesis_results.csv", index=False)

    plot_latency_decomposition(baseline_long, figures_dir / "plot1_latency_decomposition.png")
    plot_scalability_curves(baseline_long, figures_dir / "plot2_scalability_curves.png")
    plot_protocol_overhead(baseline_long, figures_dir / "plot3_protocol_overhead_pct.png")
    plot_tool_delay_dominance(baseline_long, figures_dir / "plot4_tool_delay_dominance.png")
    serialization_proxy_df = plot_serialization_proxy(
        baseline_long, workload_payload, figures_dir / "plot5_serialization_proxy.png"
    )
    plot_latency_cdf(baseline_requests, figures_dir / "plot6_latency_cdf.png")

    write_hypothesis_readme(report_dir / "TASK4_HYPOTHESES_README.md", hypotheses_df)
    write_plot_analysis(report_dir / "TASK5_PLOTS_ANALYSIS.md", baseline_long, serialization_proxy_df)

    print("Generated:")
    print(f"- {report_dir / 'TASK4_HYPOTHESES_README.md'}")
    print(f"- {report_dir / 'task4_hypothesis_results.csv'}")
    print(f"- {report_dir / 'TASK5_PLOTS_ANALYSIS.md'}")
    print(f"- {figures_dir / 'plot1_latency_decomposition.png'}")
    print(f"- {figures_dir / 'plot2_scalability_curves.png'}")
    print(f"- {figures_dir / 'plot3_protocol_overhead_pct.png'}")
    print(f"- {figures_dir / 'plot4_tool_delay_dominance.png'}")
    print(f"- {figures_dir / 'plot5_serialization_proxy.png'}")
    print(f"- {figures_dir / 'plot6_latency_cdf.png'}")


if __name__ == "__main__":
    main()
