from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel # Recommended for structured data

class ModelMetadata(BaseModel):
    total_latency_ms: float
    ttft_ms: Optional[float] = None  # Time to First Token
    input_tokens: int = 0
    output_tokens: int = 0
    routing_overhead_ms: float = 0.0 # Time taken to select the tool

class ModelResponse(BaseModel):
    text: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = []
    metadata: ModelMetadata
    raw: Dict[str, Any]

class IMCPAdapter(ABC):
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def generate(
        self, 
        prompt: str, 
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> ModelResponse:
        """
        Async generation that handles both text and MCP tool schemas.
        """
        pass