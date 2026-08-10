import asyncio
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from model_adapters.mock_adapter import MockAdapter
from orchestrator.pipeline import AgentPipeline


class FakeToolExecutor:
    def __init__(self):
        self.calls = []

    async def call_mcp_tool(self, tool_name: str, args: dict):
        self.calls.append((tool_name, args))
        delay_ms = float(args.get("delay_ms", 0))
        payload_size_kb = int(args.get("payload_size_kb", 1))
        text = args.get("text", "")
        output = (text * ((payload_size_kb * 1024) // max(1, len(text))))[: payload_size_kb * 1024]
        await asyncio.sleep(0)
        return {
            "output": output,
            "tool_name": tool_name,
            "total_latency_ms": delay_ms + 2.0,
            "tool_processing_ms": delay_ms,
            "mcp_protocol_overhead_ms": 2.0,
        }


class WorkloadPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_w2_records_light_tool_processing(self):
        executor = FakeToolExecutor()
        pipeline = AgentPipeline(MockAdapter(), executor)

        result = await pipeline.run_workload(
            {
                "name": "w2_light_tool",
                "description": "Single tool, 10ms delay",
                "model": "mock",
                "execution_mode": "sequential",
                "workflow": ["echo"],
                "tool_params": {"delay_ms": 10, "payload_size_kb": 1},
                "payload": {"text": "hello"},
            }
        )

        self.assertEqual(result["metrics"]["tool_call_count"], 1)
        self.assertEqual(result["metrics"]["tool_processing_ms"], 10)
        self.assertEqual(result["metrics"]["mcp_protocol_overhead_ms"], 2)

    async def test_w3_records_medium_tool_processing(self):
        executor = FakeToolExecutor()
        pipeline = AgentPipeline(MockAdapter(), executor)

        result = await pipeline.run_workload(
            {
                "name": "w3_medium_tool",
                "description": "Single tool, 100ms delay",
                "model": "mock",
                "execution_mode": "sequential",
                "workflow": ["echo"],
                "tool_params": {"delay_ms": 100, "payload_size_kb": 1},
                "payload": {"text": "hello"},
            }
        )

        self.assertEqual(result["metrics"]["tool_call_count"], 1)
        self.assertEqual(result["metrics"]["tool_processing_ms"], 100)

    async def test_w4_executes_five_sequential_steps(self):
        executor = FakeToolExecutor()
        pipeline = AgentPipeline(MockAdapter(), executor)

        result = await pipeline.run_workload(
            {
                "name": "w4_deep_workflow",
                "description": "5-step deep workflow",
                "model": "mock",
                "execution_mode": "sequential",
                "workflow": ["echo", "echo", "echo", "echo", "echo"],
                "tool_params": {"delay_ms": 10, "payload_size_kb": 1},
                "payload": {"text": "chain"},
            }
        )

        self.assertEqual(result["metrics"]["tool_call_count"], 5)
        self.assertEqual(result["metrics"]["tool_processing_ms"], 50)
        self.assertEqual([call[1]["step_index"] for call in executor.calls], [0, 1, 2, 3, 4])

    async def test_w5_large_payload_returns_one_mb(self):
        executor = FakeToolExecutor()
        pipeline = AgentPipeline(MockAdapter(), executor)

        result = await pipeline.run_workload(
            {
                "name": "w5_large_payload",
                "description": "1MB payload test",
                "model": "mock",
                "execution_mode": "sequential",
                "workflow": ["echo"],
                "tool_params": {"delay_ms": 10, "payload_size_kb": 1024},
                "payload": {"text": "X"},
            }
        )

        self.assertEqual(result["metrics"]["tool_call_count"], 1)
        self.assertEqual(len(result["final_output"]), 1024 * 1024)

    async def test_w6_executes_five_parallel_steps(self):
        executor = FakeToolExecutor()
        pipeline = AgentPipeline(MockAdapter(), executor)

        result = await pipeline.run_workload(
            {
                "name": "w6_multi_tool",
                "description": "5 parallel tool invocations",
                "model": "mock",
                "execution_mode": "parallel",
                "workflow": ["echo", "echo", "echo", "echo", "echo"],
                "tool_params": {"delay_ms": 10, "payload_size_kb": 1},
                "payload": {"text": "menu"},
            }
        )

        self.assertEqual(result["metrics"]["tool_call_count"], 5)
        self.assertEqual(len(executor.calls), 5)


if __name__ == "__main__":
    unittest.main()
