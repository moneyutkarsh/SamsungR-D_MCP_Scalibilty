FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ /app/

CMD ["uvicorn", "orchestrator.agent_host:app", "--host", "0.0.0.0", "--port", "8000"]
