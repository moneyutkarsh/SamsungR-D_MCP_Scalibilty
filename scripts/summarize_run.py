import pandas as pd

df = pd.read_json("data/logs/agent_host.jsonl", lines=True)

metrics_df = df["metrics"].apply(pd.Series)

# Basic stats
summary = metrics_df.describe(percentiles=[0.5, 0.95, 0.99])
summary.to_csv("data/results/latest/summary.csv")

# Protocol overhead percentage
df["proto_percent"] = (
    metrics_df["mcp_protocol_overhead_ms"] / metrics_df["total_pipeline_ms"]
) * 100

print(f"P95 Protocol Impact: {df['proto_percent'].quantile(0.95):.2f}%")

# Group by environment (cross-env comparison ready)
if "environment" in df.columns:
    print(df.groupby("environment")["proto_percent"].describe())
