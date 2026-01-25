from mcp.server.fastmcp import FastMCP
import asyncio
import time
import os

from utils.jsonl_logger import JSONLLogger

mcp = FastMCP("EchoServer")

tool_logger = JSONLLogger("/data/logs/echo_tool.jsonl")

@mcp.tool()
async def echo(text: str, delay_ms: int = 0, payload_size_kb: int = 1):
    start = time.perf_counter()

    if delay_ms > 0:
        await asyncio.sleep(delay_ms / 1000)

    # Expand payload to requested size
    target_size = payload_size_kb * 1024
    data = (text * (target_size // max(1, len(text))))[:target_size]

    end = time.perf_counter()

    # trace_id will be propagated via MCP protocol metadata
    trace_id = "none"

    proc_ms = (end - start) * 1000

    # Async non-blocking tool log
    await tool_logger.log({
        "trace_id": trace_id,
        "tool_name": "echo",
        "tool_processing_ms": proc_ms,
        "payload_bytes": len(data)
    })

    return {
        "result": data,
        "_meta": {
            "duration_ms": proc_ms
        }
    }

if __name__ == "__main__":
    import uvicorn
    # FastMCP creates an internal app that needs to be accessed via the mcp object
    # We run uvicorn directly pointing to the module
    uvicorn.run("servers.echo_tool.server:mcp", host="0.0.0.0", port=8001)
