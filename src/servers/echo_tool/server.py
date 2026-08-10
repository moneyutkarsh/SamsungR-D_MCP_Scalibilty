from fastmcp import FastMCP
import asyncio
import time
import os

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

from utils.jsonl_logger import JSONLLogger

mcp = FastMCP("EchoServer")

echo_log_path = os.getenv("ECHO_LOG_PATH", "data/logs/echo_tool.jsonl")
tool_logger = JSONLLogger(echo_log_path)

ECHO_TOOL_CALLS = Counter(
    "echo_tool_calls_total",
    "Total echo tool calls",
)

ECHO_TOOL_LATENCY = Histogram(
    "echo_tool_processing_ms",
    "Echo tool internal processing latency",
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000],
)

@mcp.tool()
async def echo(
    text: str,
    delay_ms: int = 0,
    payload_size_kb: int = 1,
    trace_id: str = "none",
    step_index: int = 0,
):
    start = time.perf_counter()

    if delay_ms > 0:
        await asyncio.sleep(delay_ms / 1000)

    # Expand payload to requested size
    target_size = payload_size_kb * 1024
    data = (text * (target_size // max(1, len(text))))[:target_size]

    end = time.perf_counter()

    proc_ms = (end - start) * 1000
    ECHO_TOOL_CALLS.inc()
    ECHO_TOOL_LATENCY.observe(proc_ms)

    # Async non-blocking tool log
    await tool_logger.log({
        "trace_id": trace_id,
        "tool_name": "echo",
        "step_index": step_index,
        "tool_processing_ms": proc_ms,
        "payload_bytes": len(data)
    })

    return {
        "result": data,
        "_meta": {
            "duration_ms": proc_ms
        }
    }

@mcp.custom_route("/metrics", methods=["GET"], include_in_schema=False)
async def metrics(request: Request) -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Add src to path for imports
    src_path = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(src_path))
    
    import uvicorn
    # Run the FastMCP server
    uvicorn.run("servers.echo_tool.server:mcp", host="0.0.0.0", port=8001)
