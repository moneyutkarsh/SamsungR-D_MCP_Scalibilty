import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from prometheus_fastapi_instrumentator import Instrumentator

from metrics.prometheus import MCP_REQUESTS, MCP_LATENCY, MCP_COST_USD, MCP_TOOL_RECOVERY
from orchestrator.tool_executor import ToolExecutor
from orchestrator.pipeline import AgentPipeline

# Adapters
from model_adapters.mock_adapter import MockAdapter
from model_adapters.ollama_adapter import OllamaAdapter

from core.context import request_trace_id
from utils.jsonl_logger import JSONLLogger

# Environment tag for cross-env comparison (local, docker, cloud, etc)
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")

# Which model backend to use: mock | ollama | openai | anthropic
MODEL_BACKEND = os.getenv("MODEL_BACKEND", "ollama")

class ToolParams(BaseModel):
    delay_ms: int = Field(ge=0, le=300000)
    payload_size_kb: int = Field(ge=0, le=10240)


class WorkloadDefinition(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    model: Literal["mock", "ollama", "openai", "anthropic"] = "mock"
    transport: Literal["sse", "stdio"] = "sse"
    prompt: Optional[str] = None
    execution_mode: Literal["sequential", "parallel"] = "sequential"
    workflow: List[Literal["echo"]] = Field(default_factory=list)
    tool_params: ToolParams = Field(default_factory=lambda: ToolParams(delay_ms=0, payload_size_kb=1))
    payload: Dict[str, Any] = Field(default_factory=dict)
    tool_schemas: List[Dict[str, Any]] = Field(default_factory=list)

class RunRequest(BaseModel):
    workload: WorkloadDefinition

# -------------------------------
# Initialize core components
# -------------------------------

executor = ToolExecutor()
adapters = {}

print("Initializing MockAdapter")
adapters["mock"] = MockAdapter()

print("Initializing OllamaAdapter")
adapters["ollama"] = OllamaAdapter(
    model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
    base_url=os.getenv("OLLAMA_URL", "http://localhost:11434")
)

if os.getenv("OPENAI_API_KEY"):
    print("Initializing OpenAIAdapter")
    from model_adapters.openai_adapter import OpenAIAdapter
    adapters["openai"] = OpenAIAdapter(
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )

if os.getenv("ANTHROPIC_API_KEY"):
    print("Initializing AnthropicAdapter")
    from model_adapters.anthropic_adapter import AnthropicAdapter
    adapters["anthropic"] = AnthropicAdapter(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
    )

# Async JSONL logger
log_path = os.getenv("LOG_PATH", "data/logs/agent_host.jsonl")
request_logger = JSONLLogger(log_path)

# -------------------------------
# FastAPI app lifecycle
# -------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await executor.initialize_servers()
    yield
    for adapter in adapters.values():
        if hasattr(adapter, "close"):
            await adapter.close()
    await executor.close()

app = FastAPI(lifespan=lifespan)

# Automatic HTTP metrics
Instrumentator().instrument(app).expose(app)

# -------------------------------
# API Endpoints
# -------------------------------

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.post("/run")
async def run(req: RunRequest):
    trace_id = str(uuid.uuid4())

    # Set context var for this request
    token = request_trace_id.set(trace_id)

    try:
        start = time.perf_counter()
        workload = req.workload.dict(exclude_none=True)
        
        # Configure transport for this request dynamically
        transport = workload.get("transport", "sse")

        # Select model backend dynamically based on workload payload
        requested_model = workload.get("model", "mock")
        if requested_model not in adapters:
            # Fallback if specific api key was missing or unavailable
            print(f"Warning: requested model {requested_model} not available, falling back to mock")
            requested_model = "mock"

        # Extract labels
        workload_name = workload.get("name", "unknown")
        users = str(workload.get("users", "1"))
        label_kwargs = {
            "model": requested_model,
            "transport": transport,
            "workload": workload_name,
            "users": users
        }

        # Initialize metrics so Prometheus tracks them immediately
        MCP_REQUESTS.labels(**label_kwargs).inc()
        MCP_TOOL_RECOVERY.labels(status="failed", **label_kwargs).inc(0)
        MCP_TOOL_RECOVERY.labels(status="recovered", **label_kwargs).inc(0)
        
        pipeline = AgentPipeline(adapters[requested_model], executor, transport=transport, labels=label_kwargs)

        result = await pipeline.run_workload(workload)
        total_ms = (time.perf_counter() - start) * 1000

        m = result["metrics"]

        # Prometheus metrics
        MCP_LATENCY.labels(component="total", **label_kwargs).observe(total_ms)
        MCP_LATENCY.labels(component="model", **label_kwargs).observe(m["model_latency_ms"])
        MCP_LATENCY.labels(component="tool", **label_kwargs).observe(m["tool_total_ms"])
        MCP_LATENCY.labels(component="protocol", **label_kwargs).observe(m["mcp_protocol_overhead_ms"])
        MCP_LATENCY.labels(component="pipeline", **label_kwargs).observe(m["pipeline_overhead_ms"])

        cost = m.get("cost_usd", 0.0)
        MCP_COST_USD.labels(**label_kwargs).inc(cost)

        cost = m.get("cost_usd", 0.0)

        # Async non-blocking structured log
        await request_logger.log({
            "trace_id": trace_id,
            "environment": ENVIRONMENT,
            "workload": workload.get("name", "unknown"),
            "metrics": m,
            "model_backend": MODEL_BACKEND,
            "cost_usd": cost
        })

        return {
            "trace_id": trace_id,
            "result": result
        }
    finally:
        # Reset context var unconditionally
        request_trace_id.reset(token)
