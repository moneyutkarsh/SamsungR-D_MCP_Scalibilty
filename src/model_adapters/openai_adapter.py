import time
from openai import AsyncOpenAI
from .base import IMCPAdapter, ModelResponse, ModelMetadata

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

        return ModelResponse(
            text=response.choices[0].message.content,
            tool_calls=getattr(response.choices[0].message, 'tool_calls', []),
            metadata=ModelMetadata(
                total_latency_ms=latency,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens
            ),
            raw=response.model_dump()
        )