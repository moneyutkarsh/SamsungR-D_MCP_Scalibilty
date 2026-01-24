import time
from .base import IMCPAdapter, ModelResponse


class LocalAdapter(IMCPAdapter):
    def __init__(self, model_name: str):
        self.model_name = model_name

    def name(self) -> str:
        return f"local:{self.model_name}"

    def generate(self, prompt: str, **kwargs) -> ModelResponse:
        start = time.time()

        # TODO: Replace this with real local inference call
        time.sleep(0.2)  # simulate model latency

        text = "Local model response"

        latency_ms = (time.time() - start) * 1000

        return ModelResponse(
            text=text,
            raw={"model": self.model_name},
            latency_ms=latency_ms
        )
