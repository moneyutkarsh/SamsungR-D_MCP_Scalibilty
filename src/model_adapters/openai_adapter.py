import time
from openai import OpenAI
from .base import IMCPAdapter, ModelResponse


class OpenAIAdapter(IMCPAdapter):
    def __init__(self, api_key: str, model: str):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def name(self) -> str:
        return f"openai:{self.model}"

    def generate(self, prompt: str, **kwargs) -> ModelResponse:
        start = time.time()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.choices[0].message.content

        latency_ms = (time.time() - start) * 1000

        return ModelResponse(
            text=text,
            raw=response.model_dump(),
            latency_ms=latency_ms
        )
