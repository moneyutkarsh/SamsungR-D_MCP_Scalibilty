from contextvars import ContextVar

# One trace_id per concurrent request (async-safe)
request_trace_id: ContextVar[str] = ContextVar("trace_id", default="none")
