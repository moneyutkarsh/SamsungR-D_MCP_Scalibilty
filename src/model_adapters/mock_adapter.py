import time
from .base import IMCPAdapter, ModelResponse


class MockAdapter(IMCPAdapter):
    """
    Deterministic zero-cost model used to measure MCP overhead only.
    """

    def name(self) -> str:
        return "mock"

    def generate(self, prompt: str, **kwargs) -> ModelResponse:
        start = time.time()

        # Deterministic fake response
        text = "OK"

        latency_ms = (time.time() - start) * 1000

        return ModelResponse(
            text=text,
            raw={"mock": True},
            latency_ms=latency_ms
        )
