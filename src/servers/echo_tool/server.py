from mcp.server.fastmcp import FastMCP
import asyncio
import time

mcp = FastMCP("EchoServer")

@mcp.tool()
async def echo(text: str) -> str:
    start = time.perf_counter()
    await asyncio.sleep(0.01)  # Simulate work
    end = time.perf_counter()

    return {
        "result": text,
        "_meta": {
            "duration_ms": (end - start) * 1000
        }
    }

# Health endpoint for Docker
@mcp.resource("health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    mcp.run(transport="sse", port=8001)
