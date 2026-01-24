import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel

from prometheus_fastapi_instrumentator import Instrumentator

from metrics.prometheus import MCP_REQUESTS, MCP_LATENCY
from orchestrator.tool_executor import ToolExecutor
from orchestrator.pipeline import AgentPipeline
from orchestrator.tool_schema import ECHO_TOOL_SCHEMA

from model_adapters.mock_adapter import MockAdapter
# or OpenAIAdapter

TOOL_SERVER_URL = os.getenv("ECHO_TOOL_URL", "http://echo_tool:8001")

class RunRequest(BaseModel):
    prompt: str

executor = ToolExecutor()
model = MockAdapter()
pipeline = AgentPipeline(model, executor, TOOL_SERVER_URL)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await executor.initialize_servers([TOOL_SERVER_URL])
    yield
    await executor.close()

app = FastAPI(lifespan=lifespan)

# Automatic HTTP metrics
Instrumentator().instrument(app).expose(app)

@app.post("/run")
async def run(req: RunRequest):
    MCP_REQUESTS.inc()

    start = time.perf_counter()
    result = await pipeline.run(req.prompt, [ECHO_TOOL_SCHEMA])
    total_ms = (time.perf_counter() - start) * 1000

    m = result["metrics"]

    MCP_LATENCY.labels(component="total").observe(total_ms)
    MCP_LATENCY.labels(component="model").observe(m["model_latency_ms"])
    MCP_LATENCY.labels(component="tool").observe(m["tool_total_ms"])
    MCP_LATENCY.labels(component="protocol").observe(m["mcp_protocol_overhead_ms"])
    MCP_LATENCY.labels(component="pipeline").observe(m["pipeline_overhead_ms"])

    return result
