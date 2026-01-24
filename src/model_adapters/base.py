from abc import ABC, abstractmethod
from typing import Dict, Any


class ModelResponse:
    def __init__(self, text: str, raw: Dict[str, Any], latency_ms: float):
        self.text = text
        self.raw = raw
        self.latency_ms = latency_ms


class IMCPAdapter(ABC):
    """
    Abstract interface for all foundation model backends.
    This allows swapping models without changing MCP orchestration logic.
    """

    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> ModelResponse:
        """
        Generate a response from the foundation model.

        Must return:
        - text: final text output
        - raw: raw provider response
        - latency_ms: end-to-end latency in milliseconds
        """
        pass
