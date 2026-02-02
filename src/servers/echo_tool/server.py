from mcp.server.fastmcp import FastMCP
import asyncio
import time
import os

from utils.jsonl_logger import JSONLLogger

mcp = FastMCP("EchoServer")

echo_log_path = os.getenv("ECHO_LOG_PATH", "data/logs/echo_tool.jsonl")
tool_logger = JSONLLogger(echo_log_path)

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
    import sys
    from pathlib import Path
    
    # Add src to path for imports
    src_path = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(src_path))
    
    import uvicorn
    # Run the FastMCP server
    uvicorn.run("servers.echo_tool.server:mcp", host="0.0.0.0", port=8001)
