# Task 4 - Formal Hypotheses and Statistical Testing

This document defines the formal hypotheses, null hypotheses, test procedures, and outcomes for MCP scalability analysis.

## Dataset Scope

- Baseline MockAdapter: W1-W7 at users [1, 10, 50, 100, 200, 500]
- Real model comparison: Ollama (llama3.2:3b) vs MockAdapter for W1-W3 at users [10, 50, 100]
- Significance level: alpha = 0.05

## Hypotheses

### H1 - Protocol Overhead Scalability
- Statement: MCP protocol overhead percentage remains <= 20% and stable across 1-100 users.
- Null (H0): Protocol overhead percentage varies significantly with concurrency or exceeds 20%.
- Procedure: One-sample t-test for mean < 20%, plus Kruskal-Wallis test across users [1,10,50,100].

### H2 - Throughput Scalability
- Statement: Throughput scales up from 1 to 100 concurrent users across workloads.
- Null (H0): Throughput at 100 users is not greater than at 1 user.
- Procedure: Paired Wilcoxon signed-rank test on workload-level throughput deltas (100u - 1u).

### H3 - Tool Complexity Impact
- Statement: Median total pipeline latency follows W3 > W2 > W1 at matched concurrency (10/50/100 users).
- Null (H0): Ordering W3 > W2 > W1 does not hold.
- Procedure: Kruskal-Wallis omnibus test, then one-sided Mann-Whitney tests for W3>W2 and W2>W1.

### H4 - Real Model vs Mock
- Statement: Ollama backend increases latency and reduces throughput versus MockAdapter (W1-W3, users 10/50/100).
- Null (H0): No significant latency/throughput difference between Ollama and MockAdapter.
- Procedure: Paired Wilcoxon signed-rank tests on matched medians (latency alternative=greater; throughput alternative=less).

## Results

| Hypothesis | Primary p-value | Secondary p-value | Decision | Evidence |
|---|---:|---:|---|---|
| H1 | 1 | 0 | Supported | median=0.0000%, max=0.0000% |
| H2 | 0.01562 | NA | Supported | median_delta_rps=44.3725, pairs=7 |
| H3 | 1.014e-54 | 1 | Rejected | medians_ms: W1=0.0140, W2=0.0091, W3=0.0121 |
| H4 | 0.001953 | 0.001953 | Supported | median_delta_latency_ms=4282.4412, median_delta_throughput_rps=-79.8378 |

## Interpretation

- Supported = statistical evidence aligns with the hypothesis statement under alpha = 0.05.
- Rejected = evidence does not support the claimed direction/threshold behavior.

## Output Files

- CSV: docs/reports/task4_hypothesis_results.csv
- Figures: docs/reports/figures/plot1_latency_decomposition.png to plot6_latency_cdf.png