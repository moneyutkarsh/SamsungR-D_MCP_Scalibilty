import time
from .base import IMCPAdapter, ModelResponse


class AnthropicAdapter(IMCPAdapter):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def name(self) -> str:
        return f"anthropic:{self.model}"

    def generate(self, prompt: str, **kwargs) -> ModelResponse:
        start = time.time()

        # TODO: Call Claude API
        time.sleep(0.3)  # simulate API latency

        text = "Claude response"

        latency_ms = (time.time() - start) * 1000

        return ModelResponse(
            text=text,
            raw={"model": self.model},
            latency_ms=latency_ms
        )
