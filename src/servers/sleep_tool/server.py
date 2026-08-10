from fastmcp import FastMCP
import asyncio
import time
import os

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

from utils.jsonl_logger import JSONLLogger

mcp = FastMCP("SleepServer")

sleep_log_path = os.getenv("SLEEP_LOG_PATH", "data/logs/sleep_tool.jsonl")
tool_logger = JSONLLogger(sleep_log_path)

SLEEP_TOOL_CALLS = Counter("sleep_tool_calls_total", "Total sleep tool calls")
SLEEP_TOOL_LATENCY = Histogram("sleep_tool_processing_ms", "Sleep tool processing latency", buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000])

@mcp.tool()
async def sleep(delay_ms: int = 1000, trace_id: str = "none", step_index: int = 0):
    start = time.perf_counter()
    
    await asyncio.sleep(delay_ms / 1000.0)

    end = time.perf_counter()
    proc_ms = (end - start) * 1000
    SLEEP_TOOL_CALLS.inc()
    SLEEP_TOOL_LATENCY.observe(proc_ms)

    await tool_logger.log({
        "trace_id": trace_id, "tool_name": "sleep", "step_index": step_index,
        "tool_processing_ms": proc_ms, "delay_ms": delay_ms
    })

    return {"result": f"Slept for {delay_ms} ms", "_meta": {"duration_ms": proc_ms}}

@mcp.custom_route("/metrics", methods=["GET"], include_in_schema=False)
async def metrics(request: Request) -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    import uvicorn
    uvicorn.run("servers.sleep_tool.server:mcp", host="0.0.0.0", port=8006)
