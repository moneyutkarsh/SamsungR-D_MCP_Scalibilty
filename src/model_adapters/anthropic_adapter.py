import time
from typing import Any, Dict, List, Optional

import httpx

from .base import IMCPAdapter, ModelMetadata, ModelResponse


class AnthropicAdapter(IMCPAdapter):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.anthropic.com",
    ):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when MODEL_BACKEND=anthropic")
        self.model = model
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=300.0,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )

    def name(self) -> str:
        return f"anthropic:{self.model}"

    async def generate(
        self,
        prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> ModelResponse:
        start = time.perf_counter()

        payload: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": kwargs.pop("max_tokens", 512),
            "messages": [{"role": "user", "content": prompt}],
            **kwargs,
        }
        if tools:
            payload["tools"] = tools

        response = await self.client.post("/v1/messages", json=payload)
        response.raise_for_status()
        data = response.json()

        total_ms = (time.perf_counter() - start) * 1000
        text_parts = [
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        ]
        tool_calls = [
            {
                "function": {
                    "name": block.get("name"),
                    "arguments": block.get("input", {}),
                }
            }
            for block in data.get("content", [])
            if block.get("type") == "tool_use"
        ]
        usage = data.get("usage", {})

        return ModelResponse(
            text="".join(text_parts) or None,
            tool_calls=tool_calls,
            metadata=ModelMetadata(
                total_latency_ms=total_ms,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
            ),
            raw=data,
        )

    async def close(self):
        await self.client.aclose()
