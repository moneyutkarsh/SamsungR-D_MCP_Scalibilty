from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel # Recommended for structured data

class ModelMetadata(BaseModel):
    total_latency_ms: float
    ttft_ms: Optional[float] = None  # Time to First Token
    input_tokens: int = 0
    output_tokens: int = 0
    routing_overhead_ms: float = 0.0 # Time taken to select the tool
    cost_usd: float = 0.0

class ModelResponse(BaseModel):
    text: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = []
    metadata: ModelMetadata
    raw: Dict[str, Any]

import json
import os

def calculate_cost_usd(model_name: str, input_tokens: int, output_tokens: int) -> float:
    try:
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'pricing_tiers.json')
        with open(config_path, 'r') as f:
            pricing = json.load(f)
        
        tier = pricing.get(model_name)
        if not tier:
            return 0.0
            
        prompt_cost = (input_tokens / 1_000_000) * tier["prompt_per_1m"]
        completion_cost = (output_tokens / 1_000_000) * tier["completion_per_1m"]
        return prompt_cost + completion_cost
    except Exception:
        return 0.0

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