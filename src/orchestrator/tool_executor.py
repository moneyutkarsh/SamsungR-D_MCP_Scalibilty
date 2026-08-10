import os
import time
import uuid
import httpx
import orjson
import asyncio

from core.context import request_trace_id
from utils.jsonl_logger import JSONLLogger

# For stdio transport
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

class ToolExecutor:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=60.0,
            limits=httpx.Limits(max_connections=500, max_keepalive_connections=100)
        )

        self.registry = {
            "echo": os.getenv("ECHO_TOOL_URL", "http://localhost:8001"),
            "math": os.getenv("MATH_TOOL_URL", "http://localhost:8002"),
            "search": os.getenv("SEARCH_TOOL_URL", "http://localhost:8003"),
            "db": os.getenv("DB_TOOL_URL", "http://localhost:8004"),
            "file": os.getenv("FILE_TOOL_URL", "http://localhost:8005"),
            "sleep": os.getenv("SLEEP_TOOL_URL", "http://localhost:8006"),
        }
        
        self.stdio_registry = {
            "echo": ["python", "-m", "servers.echo_tool.server"],
            "math": ["python", "-m", "servers.math_tool.server"],
            "search": ["python", "-m", "servers.search_tool.server"],
            "db": ["python", "-m", "servers.db_tool.server"],
            "file": ["python", "-m", "servers.file_tool.server"],
            "sleep": ["python", "-m", "servers.sleep_tool.server"],
        }

        self.stdio_sessions = {}
        self.stdio_locks = {name: asyncio.Lock() for name in self.stdio_registry}

        tool_log_path = os.getenv("TOOL_LOG_PATH", "data/logs/tool_executor.jsonl")
        self.tool_logger = JSONLLogger(tool_log_path)

    async def _start_stdio_server(self, name: str):
        cmd = self.stdio_registry.get(name)
        if not cmd:
            raise ValueError(f"Tool {name} not found in stdio registry")

        server_params = StdioServerParameters(command=cmd[0], args=cmd[1:], env=os.environ.copy())
        
        cm = stdio_client(server_params)
        read_stream, write_stream = await cm.__aenter__()
        
        session_cm = ClientSession(read_stream, write_stream)
        session = await session_cm.__aenter__()
        await session.initialize()
        
        self.stdio_sessions[name] = {
            "cm": cm,
            "session_cm": session_cm,
            "session": session
        }

    async def _stop_stdio_server(self, name: str):
        ctx = self.stdio_sessions.pop(name, None)
        if ctx:
            try:
                await asyncio.wait_for(ctx["session_cm"].__aexit__(None, None, None), timeout=5.0)
            except Exception as e:
                print(f"Error closing session for {name}: {e}")
            try:
                await asyncio.wait_for(ctx["cm"].__aexit__(None, None, None), timeout=5.0)
            except Exception as e:
                print(f"Error closing process for {name}: {e}")

    async def initialize_servers(self):
        # Warm up SSE connections to verify all tool servers are reachable.
        # Stdio sessions are started lazily on first use in _call_stdio().
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
                await self.client.post(f"{url}/mcp", json=payload)
            except Exception as e:
                print(f"Warning: SSE handshake failed for tool={name} url={url}: {e}")

    async def _call_sse(self, tool_name: str, args: dict, trace_id: str):
        server_url = self.registry.get(tool_name)
        if not server_url:
            raise ValueError(f"Tool {tool_name} not found in registry")

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

        response = await self.client.post(
            f"{server_url}/mcp",
            content=orjson.dumps(payload),
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return orjson.loads(response.content)

    async def _call_stdio(self, tool_name: str, args: dict, trace_id: str):
        if tool_name not in self.stdio_sessions:
            async with self.stdio_locks[tool_name]:
                if tool_name not in self.stdio_sessions:
                    await self._start_stdio_server(tool_name)
                    
        session = self.stdio_sessions[tool_name]["session"]
        
        try:
            result = await asyncio.wait_for(session.call_tool(tool_name, arguments=args), timeout=30.0)
        except (Exception, asyncio.CancelledError) as e:
            print(f"[{trace_id}] Stdio session for {tool_name} failed or timed out ({e}). Respawning...")
            async with self.stdio_locks[tool_name]:
                if self.stdio_sessions.get(tool_name, {}).get("session") == session:
                    await self._stop_stdio_server(tool_name)
                    await self._start_stdio_server(tool_name)
                session = self.stdio_sessions[tool_name]["session"]
            result = await asyncio.wait_for(session.call_tool(tool_name, arguments=args), timeout=30.0)
            
        if result.content and len(result.content) > 0:
            text_out = result.content[0].text
            try:
                parsed = orjson.loads(text_out)
                return {"result": parsed}
            except Exception:
                return {"result": {"result": text_out, "_meta": {"duration_ms": 0.0}}}
        return {"result": {}}

    async def call_mcp_tool(self, tool_name: str, args: dict, transport: str = "sse"):
        trace_id = request_trace_id.get()
        args = dict(args)
        args.setdefault("trace_id", trace_id)

        start_net = time.perf_counter()

        try:
            if transport == "sse":
                data = await asyncio.wait_for(self._call_sse(tool_name, args, trace_id), timeout=30.0)
            else:
                data = await self._call_stdio(tool_name, args, trace_id)
        except asyncio.TimeoutError:
            print(f"[{trace_id}] Timeout calling tool {tool_name} via {transport}")
            raise
        except Exception as e:
            print(f"[{trace_id}] Error calling tool {tool_name} via {transport}: {e}")
            raise

        end_net = time.perf_counter()
        total_latency_ms = (end_net - start_net) * 1000

        result = data.get("result", {})
        meta = result.get("_meta", {}) or {}
        internal_proc_ms = meta.get("duration_ms", 0.0)

        record = {
            "trace_id": trace_id,
            "tool_name": tool_name,
            "transport": transport,
            "total_latency_ms": total_latency_ms,
            "tool_processing_ms": internal_proc_ms,
            "mcp_protocol_overhead_ms": total_latency_ms - internal_proc_ms
        }

        await self.tool_logger.log(record)

        return {
            "output": result.get("result"),
            "tool_name": tool_name,
            "total_latency_ms": total_latency_ms,
            "tool_processing_ms": internal_proc_ms,
            "mcp_protocol_overhead_ms": total_latency_ms - internal_proc_ms
        }

    async def close(self):
        await self.client.aclose()
        for name in list(self.stdio_sessions.keys()):
            await self._stop_stdio_server(name)
