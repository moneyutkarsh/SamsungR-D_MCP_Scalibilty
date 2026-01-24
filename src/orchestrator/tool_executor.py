import time
import httpx

class ToolExecutor:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=60.0,
            limits=httpx.Limits(max_connections=500, max_keepalive_connections=100)
        )

    async def initialize_servers(self, urls):
        # MCP handshake warm-up
        for url in urls:
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
                print(f"Warning: handshake failed for {url}: {e}")

    async def call_mcp_tool(self, server_url, tool_name, args):
        start_net = time.perf_counter()

        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": args},
            "id": "bench_call"
        }

        response = await self.client.post(f"{server_url}/messages", json=payload)
        response.raise_for_status()
        data = response.json()

        end_net = time.perf_counter()

        total_latency_ms = (end_net - start_net) * 1000

        result = data.get("result", {})
        meta = result.get("_meta", {}) or {}
        internal_proc_ms = meta.get("duration_ms", 0.0)

        return {
            "output": result.get("result"),
            "total_latency_ms": total_latency_ms,
            "tool_processing_ms": internal_proc_ms,
            "mcp_protocol_overhead_ms": total_latency_ms - internal_proc_ms
        }

    async def close(self):
        await self.client.aclose()
