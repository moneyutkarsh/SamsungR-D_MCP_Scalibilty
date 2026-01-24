import time
from .base import IMCPAdapter, ModelResponse, ModelMetadata


class MockAdapter(IMCPAdapter):
    """
    Deterministic, near-zero-cost adapter for measuring pure MCP overhead.
    """

    def name(self) -> str:
        return "mock"

    async def generate(self, prompt: str, tools=None, **kwargs) -> ModelResponse:
        start = time.perf_counter()

        # Simulate trivial processing
        text = "OK"

        end = time.perf_counter()
        latency_ms = (end - start) * 1000

        return ModelResponse(
            text=text,
            tool_calls=[],
            metadata=ModelMetadata(
                total_latency_ms=latency_ms,
                ttft_ms=latency_ms,
                input_tokens=1,
                output_tokens=1
            ),
            raw={"mock": True}
        )
