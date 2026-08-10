from fastmcp import FastMCP
import time
import os
import aiofiles

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

from utils.jsonl_logger import JSONLLogger

mcp = FastMCP("FileServer")

file_log_path = os.getenv("FILE_LOG_PATH", "data/logs/file_tool.jsonl")
tool_logger = JSONLLogger(file_log_path)

FILE_TOOL_CALLS = Counter("file_tool_calls_total", "Total file tool calls")
FILE_TOOL_LATENCY = Histogram("file_tool_processing_ms", "File tool processing latency", buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000])

@mcp.tool()
async def write_file(filename: str, content: str, trace_id: str = "none", step_index: int = 0):
    start = time.perf_counter()
    
    filepath = os.path.join("data/tool_files", filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    try:
        async with aiofiles.open(filepath, mode='w') as f:
            await f.write(content)
        result = "Success"
    except Exception as e:
        result = f"Error: {e}"

    end = time.perf_counter()
    proc_ms = (end - start) * 1000
    FILE_TOOL_CALLS.inc()
    FILE_TOOL_LATENCY.observe(proc_ms)

    await tool_logger.log({
        "trace_id": trace_id, "tool_name": "file_write", "step_index": step_index,
        "tool_processing_ms": proc_ms, "filename": filename, "content_length": len(content)
    })

    return {"result": result, "_meta": {"duration_ms": proc_ms}}

@mcp.tool()
async def read_file(filename: str, trace_id: str = "none", step_index: int = 0):
    start = time.perf_counter()
    
    filepath = os.path.join("data/tool_files", filename)
    
    try:
        async with aiofiles.open(filepath, mode='r') as f:
            content = await f.read()
        result = content
    except Exception as e:
        result = f"Error: {e}"

    end = time.perf_counter()
    proc_ms = (end - start) * 1000
    FILE_TOOL_CALLS.inc()
    FILE_TOOL_LATENCY.observe(proc_ms)

    await tool_logger.log({
        "trace_id": trace_id, "tool_name": "file_read", "step_index": step_index,
        "tool_processing_ms": proc_ms, "filename": filename
    })

    return {"result": result, "_meta": {"duration_ms": proc_ms}}

@mcp.custom_route("/metrics", methods=["GET"], include_in_schema=False)
async def metrics(request: Request) -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    import uvicorn
    uvicorn.run("servers.file_tool.server:mcp", host="0.0.0.0", port=8005)
