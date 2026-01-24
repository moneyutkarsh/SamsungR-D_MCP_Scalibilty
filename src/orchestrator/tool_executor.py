import os
import time
import uuid
import httpx
import orjson

from core.context import request_trace_id
from utils.jsonl_logger import JSONLLogger

class ToolExecutor:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=60.0,
            limits=httpx.Limits(max_connections=500, max_keepalive_connections=100)
        )

        # Tool registry: tool_name -> server_url
        self.registry = {
            "echo": os.getenv("ECHO_TOOL_URL", "http://echo_tool:8001"),
            # Future:
            # "math": os.getenv("MATH_TOOL_URL"),
            # "search": os.getenv("SEARCH_TOOL_URL"),
        }

        self.tool_logger = JSONLLogger("/data/logs/tool_executor.jsonl")

    async def initialize_servers(self):
        # MCP handshake warm-up for all tools
        for name, url in self.registry.items():
            payload = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "clientInfo": {"name": "mcp-bench", "version": "1.0"},
                    "capabilities": {}
                },
                "id": 0
            }
            try:
                await self.client.post(f"{url}/messages", json=payload)
            except Exception as e:
                print(f"Warning: handshake failed for tool={name} url={url}: {e}")

    async def call_mcp_tool(self, tool_name: str, args: dict):
        server_url = self.registry[tool_name]

        trace_id = request_trace_id.get()

        start_net = time.perf_counter()

        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": args
            },
            "id": str(uuid.uuid4()),
            "_meta": {
                "trace_id": trace_id
            }
        }

        # Use orjson for fast serialization (important for large payloads)
        response = await self.client.post(
            f"{server_url}/messages",
            content=orjson.dumps(payload),
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()

        data = orjson.loads(response.content)

        end_net = time.perf_counter()

        total_latency_ms = (end_net - start_net) * 1000

        result = data.get("result", {})
        meta = result.get("_meta", {}) or {}
        internal_proc_ms = meta.get("duration_ms", 0.0)

        record = {
            "trace_id": trace_id,
            "tool_name": tool_name,
            "total_latency_ms": total_latency_ms,
            "tool_processing_ms": internal_proc_ms,
            "mcp_protocol_overhead_ms": total_latency_ms - internal_proc_ms
        }

        # Async non-blocking log
        await self.tool_logger.log(record)

        return {
            "output": result.get("result"),
            "total_latency_ms": total_latency_ms,
            "tool_processing_ms": internal_proc_ms,
            "mcp_protocol_overhead_ms": total_latency_ms - internal_proc_ms
        }

    async def close(self):
        await self.client.aclose()
