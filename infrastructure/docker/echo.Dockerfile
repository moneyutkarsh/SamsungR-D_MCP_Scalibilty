FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

RUN pip install mcp fastapi uvicorn

COPY src/servers/echo_tool /app

CMD ["python", "server.py"]
