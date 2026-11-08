import asyncio
import time
from .base import IMCPAdapter, ModelResponse, ModelMetadata


class LocalAdapter(IMCPAdapter):
    def __init__(self, model_name: str):
        self.model_name = model_name

    def name(self) -> str:
        return f"local:{self.model_name}"

    async def generate(self, prompt: str, tools=None, **kwargs) -> ModelResponse:
        start = time.time()

        # TODO: Replace this with real local inference call
        await asyncio.sleep(0.2)  # simulate model latency

        text = "Local model response"

        latency_ms = (time.time() - start) * 1000

        return ModelResponse(
            text=text,
            tool_calls=[],
            metadata=ModelMetadata(
                total_latency_ms=latency_ms,
                ttft_ms=latency_ms,
                input_tokens=1,
                output_tokens=1,
                cost_usd=0.0
            ),
            raw={"model": self.model_name}
        )
