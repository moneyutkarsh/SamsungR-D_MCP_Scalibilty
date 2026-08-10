from mcp.server.fastmcp import FastMCP
import time
import os

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

from utils.jsonl_logger import JSONLLogger

mcp = FastMCP("MathServer")

math_log_path = os.getenv("MATH_LOG_PATH", "data/logs/math_tool.jsonl")
tool_logger = JSONLLogger(math_log_path)

MATH_TOOL_CALLS = Counter(
    "math_tool_calls_total",
    "Total math tool calls",
)

MATH_TOOL_LATENCY = Histogram(
    "math_tool_processing_ms",
    "Math tool internal processing latency",
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000],
)

@mcp.tool()
async def calculate(
    expression: str,
    trace_id: str = "none",
    step_index: int = 0,
):
    start = time.perf_counter()

    # Extremely basic and safe math evaluation
    allowed_chars = set("0123456789+-*/(). ")
    if not all(c in allowed_chars for c in expression):
        result = "Error: Invalid characters in expression"
    else:
        try:
            # Using eval here is heavily restricted by the allowed_chars check
            result = str(eval(expression))
        except Exception as e:
            result = f"Error: {e}"

    end = time.perf_counter()
    proc_ms = (end - start) * 1000
    MATH_TOOL_CALLS.inc()
    MATH_TOOL_LATENCY.observe(proc_ms)

    await tool_logger.log({
        "trace_id": trace_id,
        "tool_name": "math",
        "step_index": step_index,
        "tool_processing_ms": proc_ms,
        "expression": expression
    })

    return {
        "result": result,
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
    
    src_path = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(src_path))
    
    import uvicorn
    uvicorn.run("servers.math_tool.server:mcp", host="0.0.0.0", port=8002)
