import time
from openai import AsyncOpenAI
import json
from .base import IMCPAdapter, ModelResponse, ModelMetadata, calculate_cost_usd

class OpenAIAdapter(IMCPAdapter):
    def __init__(self, api_key: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    def name(self) -> str:
        return f"openai:{self.model}"

    async def generate(self, prompt: str, tools=None, **kwargs) -> ModelResponse:
        start_time = time.perf_counter()
        
        # Tool routing overhead starts here
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            tools=tools, # Pass MCP tools here
            **kwargs
        )
        
        end_time = time.perf_counter()
        latency = (end_time - start_time) * 1000

        input_toks = response.usage.prompt_tokens if response.usage else 0
        output_toks = response.usage.completion_tokens if response.usage else 0
        cost = calculate_cost_usd(self.name(), input_toks, output_toks)

        # Parse tool calls to match the standard format if needed
        raw_tool_calls = getattr(response.choices[0].message, 'tool_calls', [])
        tool_calls = []
        if raw_tool_calls:
            for tc in raw_tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments)
                    }
                })

        return ModelResponse(
            text=response.choices[0].message.content,
            tool_calls=tool_calls,
            metadata=ModelMetadata(
                total_latency_ms=latency,
                input_tokens=input_toks,
                output_tokens=output_toks,
                cost_usd=cost
            ),
            raw=response.model_dump()
        )