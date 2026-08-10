import time
import httpx
from .base import IMCPAdapter, ModelResponse, ModelMetadata

class OllamaAdapter(IMCPAdapter):
    def __init__(self, model: str, base_url: str = "http://ollama:11434"):
        self.model = model
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=300.0)

    def name(self) -> str:
        return f"ollama:{self.model}"

    async def generate(self, prompt: str, tools=None, **kwargs) -> ModelResponse:
        start = time.perf_counter()

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        response = await self.client.post(
            f"{self.base_url}/api/generate",
            json=payload
        )
        response.raise_for_status()
        data = response.json()

        end = time.perf_counter()

        total_ms = (end - start) * 1000

        return ModelResponse(
            text=data.get("response", ""),
            tool_calls=[],
            metadata=ModelMetadata(
                total_latency_ms=total_ms,
                ttft_ms=None,
                input_tokens=data.get("prompt_eval_count", 0),
                output_tokens=data.get("eval_count", 0),
                routing_overhead_ms=0.0
            ),
            raw=data
        )

    async def close(self):
        await self.client.aclose()
