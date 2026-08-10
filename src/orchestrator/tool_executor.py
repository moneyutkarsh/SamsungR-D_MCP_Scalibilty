import os
import time
import uuid
import httpx
import orjson
import asyncio

from core.context import request_trace_id
from utils.jsonl_logger import JSONLLogger

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.sse import sse_client
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
            "echo": ["python", "-m", "servers.echo_tool.server", "--stdio"],
            "math": ["python", "-m", "servers.math_tool.server", "--stdio"],
            "search": ["python", "-m", "servers.search_tool.server", "--stdio"],
            "db": ["python", "-m", "servers.db_tool.server", "--stdio"],
            "file": ["python", "-m", "servers.file_tool.server", "--stdio"],
            "sleep": ["python", "-m", "servers.sleep_tool.server", "--stdio"],
        }

        self.stdio_sessions = {}
        self.stdio_locks = {name: asyncio.Lock() for name in self.stdio_registry}

        self.sse_sessions = {}
        self.sse_locks = {name: asyncio.Lock() for name in self.registry}

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
            try:
                await self._start_sse_session(name)
            except Exception as e:
                print(f"Warning: SSE handshake failed for tool={name} url={url}: {e}")

    async def _start_sse_session(self, name: str):
        url = self.registry.get(name)
        if not url:
            raise ValueError(f"Tool {name} not found in sse registry")

        cm = sse_client(f"{url}/sse")
        read_stream, write_stream = await cm.__aenter__()
        
        session_cm = ClientSession(read_stream, write_stream)
        session = await session_cm.__aenter__()
        await session.initialize()
        
        self.sse_sessions[name] = {
            "session": session,
            "cm": cm,
            "session_cm": session_cm
        }

    async def _stop_sse_session(self, name: str):
        if name in self.sse_sessions:
            session_data = self.sse_sessions[name]
            try:
                await session_data["session_cm"].__aexit__(None, None, None)
            except Exception:
                pass
            try:
                await session_data["cm"].__aexit__(None, None, None)
            except Exception:
                pass
            del self.sse_sessions[name]

    async def _call_sse(self, tool_name: str, args: dict, trace_id: str):
        if tool_name not in self.sse_sessions:
            async with self.sse_locks[tool_name]:
                if tool_name not in self.sse_sessions:
                    await self._start_sse_session(tool_name)
                    
        session = self.sse_sessions[tool_name]["session"]
        
        try:
            result = await asyncio.wait_for(session.call_tool(tool_name, arguments=args), timeout=30.0)
        except (Exception, asyncio.CancelledError) as e:
            print(f"[{trace_id}] SSE session for {tool_name} failed or timed out ({e}). Respawning...")
            async with self.sse_locks[tool_name]:
                if self.sse_sessions.get(tool_name, {}).get("session") == session:
                    await self._stop_sse_session(tool_name)
                    await self._start_sse_session(tool_name)
                session = self.sse_sessions[tool_name]["session"]
            result = await asyncio.wait_for(session.call_tool(tool_name, arguments=args), timeout=30.0)
            
        if result.content and len(result.content) > 0:
            text_out = result.content[0].text
            try:
                parsed = orjson.loads(text_out)
                return {"result": parsed}
            except Exception:
                return {"result": {"result": text_out, "_meta": {"duration_ms": 0.0}}}
        return {"result": {}}

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
        for name in list(self.sse_sessions.keys()):
            await self._stop_sse_session(name)
