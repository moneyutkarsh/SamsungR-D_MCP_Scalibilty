import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from prometheus_fastapi_instrumentator import Instrumentator

from metrics.prometheus import MCP_REQUESTS, MCP_LATENCY
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
    prompt: Optional[str] = None
    execution_mode: Literal["sequential", "parallel"] = "sequential"
    workflow: List[Literal["echo"]] = Field(min_items=1)
    tool_params: ToolParams
    payload: Dict[str, Any]
    tool_schemas: List[Dict[str, Any]] = Field(default_factory=list)


class RunRequest(BaseModel):
    workload: WorkloadDefinition

# -------------------------------
# Initialize core components
# -------------------------------

executor = ToolExecutor()

# Select model backend
if MODEL_BACKEND == "mock":
    print("Using MockAdapter")
    model = MockAdapter()

elif MODEL_BACKEND == "ollama":
    print("Using OllamaAdapter")
    model = OllamaAdapter(
        model=os.getenv("OLLAMA_MODEL", "phi3:mini"),
        base_url=os.getenv("OLLAMA_URL", "http://localhost:11434")
    )

elif MODEL_BACKEND == "openai":
    print("Using OpenAIAdapter")
    from model_adapters.openai_adapter import OpenAIAdapter
    model = OpenAIAdapter(
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )

elif MODEL_BACKEND == "anthropic":
    print("Using AnthropicAdapter")
    from model_adapters.anthropic_adapter import AnthropicAdapter
    model = AnthropicAdapter(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
    )

else:
    raise RuntimeError(f"Unknown MODEL_BACKEND: {MODEL_BACKEND}")

pipeline = AgentPipeline(model, executor)

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
    if hasattr(model, "close"):
        await model.close()
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

    MCP_REQUESTS.inc()

    start = time.perf_counter()
    workload = req.workload.dict(exclude_none=True)
    result = await pipeline.run_workload(workload)
    total_ms = (time.perf_counter() - start) * 1000

    m = result["metrics"]

    # Prometheus metrics
    MCP_LATENCY.labels(component="total").observe(total_ms)
    MCP_LATENCY.labels(component="model").observe(m["model_latency_ms"])
    MCP_LATENCY.labels(component="tool").observe(m["tool_total_ms"])
    MCP_LATENCY.labels(component="protocol").observe(m["mcp_protocol_overhead_ms"])
    MCP_LATENCY.labels(component="pipeline").observe(m["pipeline_overhead_ms"])

    # Async non-blocking structured log
    await request_logger.log({
        "trace_id": trace_id,
        "environment": ENVIRONMENT,
        "workload": workload.get("name", "unknown"),
        "metrics": m,
        "model_backend": MODEL_BACKEND
    })

    # Reset context var
    request_trace_id.reset(token)

    return {
        "trace_id": trace_id,
        "result": result
    }
