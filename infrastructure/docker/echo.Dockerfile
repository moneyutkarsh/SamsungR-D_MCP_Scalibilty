FROM python:3.11-slim

WORKDIR /app

# Install deps
RUN apt-get update && apt-get install -y netcat-openbsd && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/
COPY data/ /app/data/

ENV PYTHONPATH=/app/src
ENV PORT=8001

EXPOSE 8001

CMD ["uvicorn", "servers.echo_tool.server:app", "--host", "0.0.0.0", "--port", "8001"]
