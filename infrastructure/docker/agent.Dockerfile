FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ /app/src/
COPY data/ /app/data/

# Make sure Python can find src/
ENV PYTHONPATH=/app/src

# Expose API
EXPOSE 8000

CMD ["uvicorn", "orchestrator.agent_host:app", "--host", "0.0.0.0", "--port", "8000"]
