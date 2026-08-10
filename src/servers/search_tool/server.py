from mcp.server.fastmcp import FastMCP
import asyncio
import time
import os

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

from utils.jsonl_logger import JSONLLogger

mcp = FastMCP("SearchServer")

search_log_path = os.getenv("SEARCH_LOG_PATH", "data/logs/search_tool.jsonl")
tool_logger = JSONLLogger(search_log_path)

SEARCH_TOOL_CALLS = Counter("search_tool_calls_total", "Total search tool calls")
SEARCH_TOOL_LATENCY = Histogram("search_tool_processing_ms", "Search tool processing latency", buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000])

@mcp.tool()
async def search(query: str, delay_ms: int = 10, results_count: int = 5, trace_id: str = "none", step_index: int = 0):
    start = time.perf_counter()
    if delay_ms > 0:
        await asyncio.sleep(delay_ms / 1000)
    
    results = [f"Search result {i+1} for '{query}'" for i in range(results_count)]
    
    end = time.perf_counter()
    proc_ms = (end - start) * 1000
    SEARCH_TOOL_CALLS.inc()
    SEARCH_TOOL_LATENCY.observe(proc_ms)

    await tool_logger.log({
        "trace_id": trace_id, "tool_name": "search", "step_index": step_index,
        "tool_processing_ms": proc_ms, "query": query, "results_count": results_count
    })

    return {"result": results, "_meta": {"duration_ms": proc_ms}}

@mcp.custom_route("/metrics", methods=["GET"], include_in_schema=False)
async def metrics(request: Request) -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Expose proper ASGI app for uvicorn (FastMCP is not directly callable)
app = mcp.sse_app()

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    if "--stdio" in sys.argv:
        mcp.run(transport="stdio")
    else:
        import uvicorn
        uvicorn.run("servers.search_tool.server:app", host="0.0.0.0", port=8003)
