from mcp.server.fastmcp import FastMCP
import asyncio
import time
import os
import aiosqlite

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

from utils.jsonl_logger import JSONLLogger

mcp = FastMCP("DBServer")

db_log_path = os.getenv("DB_LOG_PATH", "data/logs/db_tool.jsonl")
tool_logger = JSONLLogger(db_log_path)

DB_TOOL_CALLS = Counter("db_tool_calls_total", "Total db tool calls")
DB_TOOL_LATENCY = Histogram("db_tool_processing_ms", "DB tool processing latency", buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000])

db_path = os.getenv("DB_TOOL_PATH", "data/tool_db.sqlite")

@mcp.tool()
async def query_db(query: str, trace_id: str = "none", step_index: int = 0):
    start = time.perf_counter()
    
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    try:
        async with aiosqlite.connect(db_path) as db:
            # WAL mode for high concurrency
            await db.execute("PRAGMA journal_mode=WAL;")
            # Basic setup if not exists
            await db.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY, value TEXT)")
            
            # Simple simulate query
            if query.lower().startswith("select"):
                async with db.execute(query) as cursor:
                    rows = await cursor.fetchall()
                result = {"rows": rows}
            else:
                await db.execute(query)
                await db.commit()
                result = {"status": "success"}
    except Exception as e:
        result = {"error": str(e)}

    end = time.perf_counter()
    proc_ms = (end - start) * 1000
    DB_TOOL_CALLS.inc()
    DB_TOOL_LATENCY.observe(proc_ms)

    await tool_logger.log({
        "trace_id": trace_id, "tool_name": "db", "step_index": step_index,
        "tool_processing_ms": proc_ms, "query": query
    })

    return {"result": result, "_meta": {"duration_ms": proc_ms}}

@mcp.custom_route("/metrics", methods=["GET"], include_in_schema=False)
async def metrics(request: Request) -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Expose proper ASGI app for uvicorn (FastMCP is not directly callable)
app = mcp.sse_app()

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    import uvicorn
    uvicorn.run("servers.db_tool.server:app", host="0.0.0.0", port=8004)
