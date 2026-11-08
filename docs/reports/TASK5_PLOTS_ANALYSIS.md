# Task 5 - Plot Analysis

This report summarizes the six generated plots and key observations.

## Plot 1 - Latency Decomposition by Workload
- Figure: docs/reports/figures/plot1_latency_decomposition.png
- Interpretation: The stacked bars separate model, tool, protocol, and pipeline costs at 100 users. In this dataset, pipeline-overhead component is the dominant measured internal contributor.

## Plot 2 - Scalability Curves
- Figure: docs/reports/figures/plot2_scalability_curves.png
- Highest observed throughput median: w5_large_payload at users=10, throughput=194.3029 rps.
- Lowest observed throughput median: w1_pure_mcp at users=100, throughput=16.0565 rps.

## Plot 3 - Protocol Overhead Percentage
- Figure: docs/reports/figures/plot3_protocol_overhead_pct.png
- Maximum median protocol-overhead percentage observed: 0.0000% (well below 20% threshold).

## Plot 4 - Tool Delay Dominance (W1/W2/W3)
- Figure: docs/reports/figures/plot4_tool_delay_dominance.png
- Interpretation: Observed tool_processing_ms medians are ~0 for W1/W2/W3 in this baseline, so configured tool-delay effects are not visible in recorded tool timing metrics.

## Plot 5 - Serialization Cost vs Payload Size
- Figure: docs/reports/figures/plot5_serialization_proxy.png
- Note: Current baseline has only one W5 payload size (1024KB). The plot uses available workloads with payload sizes (1KB, 128KB, 1024KB) as a serialization proxy.
- This is indicative rather than a strict controlled W5-only payload sweep.

## Plot 6 - Latency CDF
- Figure: docs/reports/figures/plot6_latency_cdf.png
- Interpretation: CDF comparison at 100 users reveals distribution spread and tail behavior by workload.

## Serialization Proxy Data Used

| workload | payload_size_kb | median_pipeline_overhead_ms |
|---|---:|---:|
| w1_pure_mcp | 1 | 0.012899 |
| w2_light_tool | 1 | 0.008592 |
| w3_medium_tool | 1 | 0.012737 |
| w4_deep_workflow | 1 | 0.009500 |
| w6_multi_tool | 1 | 0.012086 |
| w7_mixed | 128 | 0.010010 |
| w5_large_payload | 1024 | 0.011518 |