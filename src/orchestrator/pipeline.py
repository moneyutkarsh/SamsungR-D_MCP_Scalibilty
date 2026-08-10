import asyncio
import json
import time

class AgentPipeline:
    def __init__(self, model_adapter, tool_executor):
        self.model = model_adapter
        self.tools = tool_executor

    async def run_workload(self, workload: dict):
        pipeline_start = time.perf_counter()

        prompt = workload.get("prompt") or self._build_prompt(workload)
        tool_schemas = workload.get("tool_schemas", [])

        # ---- Model phase ----
        model_resp = await self.model.generate(prompt=prompt, tools=tool_schemas)
        model_latency_ms = model_resp.metadata.total_latency_ms

        tool_results = []

        workflow = workload.get("workflow", [])
        if workflow:
            tool_results = await self._run_declared_workflow(workload, workflow)
        elif model_resp.tool_calls:
            tool_results = await self._run_model_tool_calls(model_resp.tool_calls)

        pipeline_end = time.perf_counter()
        total_pipeline_ms = (pipeline_end - pipeline_start) * 1000

        tool_total_ms = sum(item["total_latency_ms"] for item in tool_results)
        tool_processing_ms = sum(item["tool_processing_ms"] for item in tool_results)
        protocol_overhead_ms = sum(item["mcp_protocol_overhead_ms"] for item in tool_results)

        pipeline_overhead_ms = (
            total_pipeline_ms
            - model_latency_ms
            - tool_total_ms
        )

        return {
            "final_output": self._final_output(model_resp.text, tool_results),
            "tool_results": tool_results,
            "metrics": {
                "total_pipeline_ms": total_pipeline_ms,
                "model_latency_ms": model_latency_ms,
                "tool_total_ms": tool_total_ms,
                "tool_processing_ms": tool_processing_ms,
                "mcp_protocol_overhead_ms": protocol_overhead_ms,
                "pipeline_overhead_ms": pipeline_overhead_ms,
                "tool_call_count": len(tool_results),
            }
        }

    def _build_prompt(self, workload: dict) -> str:
        name = workload.get("name", "unknown")
        description = workload.get("description", "")
        workflow = ", ".join(workload.get("workflow", []))
        return f"Run workload {name}. {description}. Workflow: {workflow}."

    async def _run_declared_workflow(self, workload: dict, workflow: list[str]):
        payload = dict(workload.get("payload", {}))
        tool_params = dict(workload.get("tool_params", {}))
        execution_mode = workload.get("execution_mode", "sequential")

        async def call_tool(index: int, tool_name: str):
            args = {**payload, **tool_params, "step_index": index}
            return await self.tools.call_mcp_tool(tool_name=tool_name, args=args)

        if execution_mode == "parallel":
            return await asyncio.gather(
                *(call_tool(index, tool_name) for index, tool_name in enumerate(workflow))
            )

        results = []
        for index, tool_name in enumerate(workflow):
            result = await call_tool(index, tool_name)
            results.append(result)
        return results

    async def _run_model_tool_calls(self, tool_calls):
        results = []
        for call in tool_calls:
            function = call.get("function", {})
            tool_name = function.get("name")
            tool_args = function.get("arguments", {})
            if isinstance(tool_args, str):
                tool_args = json.loads(tool_args)
            results.append(
                await self.tools.call_mcp_tool(tool_name=tool_name, args=tool_args)
            )
        return results

    def _final_output(self, model_text, tool_results):
        if not tool_results:
            return model_text
        if len(tool_results) == 1:
            return tool_results[0]["output"]
        return [item["output"] for item in tool_results]
