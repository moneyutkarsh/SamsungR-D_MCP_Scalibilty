import time

class AgentPipeline:
    def __init__(self, model_adapter, tool_executor, tool_server_url):
        self.model = model_adapter
        self.tools = tool_executor
        self.tool_server_url = tool_server_url

    async def run(self, prompt: str, tool_schemas: list):
        pipeline_start = time.perf_counter()

        # ---- Model phase ----
        model_resp = await self.model.generate(prompt=prompt, tools=tool_schemas)
        model_latency_ms = model_resp.metadata.total_latency_ms

        tool_metrics = await self.tools.call_mcp_tool(
        tool_name=tool_name,
        args=tool_args
        )


        if model_resp.tool_calls:
            call = model_resp.tool_calls[0]
            tool_name = call["function"]["name"]
            tool_args = call["function"]["arguments"]

            tool_metrics = await self.tools.call_mcp_tool(
                server_url=self.tool_server_url,
                tool_name=tool_name,
                args=tool_args
            )

        pipeline_end = time.perf_counter()
        total_pipeline_ms = (pipeline_end - pipeline_start) * 1000

        tool_total_ms = tool_metrics["total_latency_ms"] if tool_metrics else 0.0

        pipeline_overhead_ms = (
            total_pipeline_ms
            - model_latency_ms
            - tool_total_ms
        )

        return {
            "final_output": tool_metrics["output"] if tool_metrics else model_resp.text,
            "metrics": {
                "total_pipeline_ms": total_pipeline_ms,
                "model_latency_ms": model_latency_ms,
                "tool_total_ms": tool_total_ms,
                "tool_processing_ms": tool_metrics["tool_processing_ms"] if tool_metrics else 0.0,
                "mcp_protocol_overhead_ms": tool_metrics["mcp_protocol_overhead_ms"] if tool_metrics else 0.0,
                "pipeline_overhead_ms": pipeline_overhead_ms,
            }
        }
