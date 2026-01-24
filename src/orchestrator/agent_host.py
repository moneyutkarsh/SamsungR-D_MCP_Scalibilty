import os
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel

from prometheus_fastapi_instrumentator import Instrumentator

from metrics.prometheus import MCP_REQUESTS, MCP_LATENCY
from orchestrator.tool_executor import ToolExecutor
from orchestrator.pipeline import AgentPipeline

from model_adapters.mock_adapter import MockAdapter
# from model_adapters.openai_adapter import OpenAIAdapter

from core.context import request_trace_id
from utils.jsonl_logger import JSONLLogger

# Environment tag for cross-env comparison (local, docker, cloud, etc)
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")

class RunRequest(BaseModel):
    workload: dict

# Persistent components
executor = ToolExecutor()
model = MockAdapter()
# model = OpenAIAdapter(api_key="...", model="gpt-4o-mini")

pipeline = AgentPipeline(model, executor)

# Async JSONL logger
request_logger = JSONLLogger("/data/logs/agent_host.jsonl")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await executor.initialize_servers()
    yield
    await executor.close()

app = FastAPI(lifespan=lifespan)

# Automatic HTTP metrics
Instrumentator().instrument(app).expose(app)

@app.post("/run")
async def run(req: RunRequest):
    trace_id = str(uuid.uuid4())

    # Set context var for this request
    token = request_trace_id.set(trace_id)

    MCP_REQUESTS.inc()

    start = time.perf_counter()
    result = await pipeline.run_workload(req.workload)
    total_ms = (time.perf_counter() - start) * 1000

    m = result["metrics"]

    MCP_LATENCY.labels(component="total").observe(total_ms)
    MCP_LATENCY.labels(component="model").observe(m["model_latency_ms"])
    MCP_LATENCY.labels(component="tool").observe(m["tool_total_ms"])
    MCP_LATENCY.labels(component="protocol").observe(m["mcp_protocol_overhead_ms"])
    MCP_LATENCY.labels(component="pipeline").observe(m["pipeline_overhead_ms"])

    # Async non-blocking structured log
    await request_logger.log({
        "trace_id": trace_id,
        "environment": ENVIRONMENT,
        "workload": req.workload.get("name", "unknown"),
        "metrics": m
    })

    # Reset context var
    request_trace_id.reset(token)

    return {
        "trace_id": trace_id,
        "result": result
    }
