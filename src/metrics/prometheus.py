from prometheus_client import Counter, Histogram

LATENCY_BUCKETS = [
    5, 10, 25, 50, 100, 250, 500, 750,
    1000, 2500, 5000, 10000
]

MCP_REQUESTS = Counter(
    "mcp_requests_total",
    "Total MCP /run requests"
)

MCP_LATENCY = Histogram(
    "mcp_latency_ms",
    "Latency breakdown of the MCP pipeline",
    ["component"],  # model, tool, protocol, pipeline, total
    buckets=LATENCY_BUCKETS
)
