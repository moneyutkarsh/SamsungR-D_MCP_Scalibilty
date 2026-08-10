import asyncio
import json
import time
import logging

from metrics.prometheus import MCP_WORKFLOW_DEPTH, MCP_TOOL_RECOVERY

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
        cost_usd = getattr(model_resp.metadata, "cost_usd", 0.0)

        workflow = workload.get("workflow", [])
        if workflow:
            tool_results = await self._run_declared_workflow(workload, workflow)
        elif model_resp.tool_calls:
            # We pass the prompt, the initial response, and tools to the iterative handler
            iter_result = await self._run_model_tool_calls_iterative(
                prompt=prompt,
                initial_resp=model_resp,
                tools=tool_schemas
            )
            tool_results = iter_result["tool_results"]
            model_latency_ms += iter_result["additional_model_latency_ms"]
            cost_usd += iter_result["additional_cost_usd"]

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
                "cost_usd": cost_usd
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

    async def _run_model_tool_calls_iterative(self, prompt: str, initial_resp, tools):
        """
        Iteratively execute tools and feed results back to the model.
        Includes infinite loop prevention and error recovery.
        """
        MAX_ITERATIONS = 5
        iteration = 0
        
        all_tool_results = []
        additional_latency_ms = 0.0
        additional_cost_usd = 0.0
        
        current_resp = initial_resp
        conversation_history = [{"role": "user", "content": prompt}]
        
        while current_resp.tool_calls and iteration < MAX_ITERATIONS:
            iteration += 1
            
            # Record assistant message with tool calls
            # (Assuming a simplified history structure for now, adaptable based on model backend)
            conversation_history.append({
                "role": "assistant",
                "content": current_resp.text or "",
                "tool_calls": current_resp.tool_calls
            })
            
            iteration_results = []
            tool_message_contents = []

            for call in current_resp.tool_calls:
                function = call.get("function", {})
                tool_name = function.get("name")
                tool_args = function.get("arguments", {})
                
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except json.JSONDecodeError:
                        tool_args = {}
                
                try:
                    res = await self.tools.call_mcp_tool(tool_name=tool_name, args=tool_args)
                    iteration_results.append(res)
                    MCP_TOOL_RECOVERY.labels(status="recovered").inc()
                    
                    tool_message_contents.append({
                        "tool_call_id": call.get("id", ""),
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps(res.get("output", {}))
                    })
                except Exception as e:
                    MCP_TOOL_RECOVERY.labels(status="failed").inc()
                    logging.warning(f"Tool execution failed: {e}")
                    # Error recovery mechanism: inform the model about the error
                    tool_message_contents.append({
                        "tool_call_id": call.get("id", ""),
                        "role": "tool",
                        "name": tool_name,
                        "content": f"Error executing tool: {str(e)}"
                    })
            
            all_tool_results.extend(iteration_results)
            
            # Append tool responses to history
            # In a real strict OpenAI schema, these would be separate messages
            for tmc in tool_message_contents:
                conversation_history.append(tmc)
                
            # Convert history back to a prompt for simplicity if adapter doesn't support full history natively
            # Ideally the adapter generate() supports `messages=conversation_history`
            # For this benchmark, if we just want iterative depth testing, we format as string
            full_prompt = json.dumps(conversation_history)
            
            # Call model again
            current_resp = await self.model.generate(prompt=full_prompt, tools=tools)
            additional_latency_ms += current_resp.metadata.total_latency_ms
            additional_cost_usd += getattr(current_resp.metadata, "cost_usd", 0.0)

        # Record metric
        MCP_WORKFLOW_DEPTH.observe(iteration)

        if iteration >= MAX_ITERATIONS and current_resp.tool_calls:
            logging.warning(f"Max iterations ({MAX_ITERATIONS}) reached. Aborting hallucination loop.")

        return {
            "tool_results": all_tool_results,
            "additional_model_latency_ms": additional_latency_ms,
            "additional_cost_usd": additional_cost_usd
        }

    def _final_output(self, model_text, tool_results):
        if not tool_results:
            return model_text
        if len(tool_results) == 1:
            return tool_results[0]["output"]
        return [item["output"] for item in tool_results]
