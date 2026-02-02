#!/bin/bash

set -e  # Exit on error

echo "=========================================================================="
echo "MCP Scalability Analysis - Full Test Run (Docker + Prometheus + Grafana)"
echo "=========================================================================="

# Clean up any previous containers
echo ""
echo "[0/6] Cleaning up previous containers..."
docker-compose down -v 2>/dev/null || true
docker ps -a | grep mcp-scalability-analysis | awk '{print $1}' | xargs -r docker rm -f 2>/dev/null || true

# Step 1: Start Ollama
echo ""
echo "[1/6] Starting Ollama service..."
docker-compose up -d ollama

# Wait for Ollama to be ready
echo "Waiting for Ollama to start..."
for i in {1..30}; do
  if docker ps | grep -q ollama && docker exec ollama ollama list >/dev/null 2>&1; then
    echo "Ollama is ready!"
    break
  fi
  echo "  Attempt $i/30..."
  sleep 2
done

echo "Pulling phi3:mini model..."
docker exec ollama ollama pull phi3:mini

# Step 2: Build and Start All Services
echo ""
echo "[2/6] Building and starting all services..."
docker-compose up --build -d

echo "Waiting for services to be ready..."
sleep 15

echo "Checking container status..."
docker-compose ps

# Verify critical services are running
echo "Verifying services..."
if ! docker ps | grep -q agent_host; then
  echo "ERROR: agent_host container is not running"
  docker-compose logs agent_host
  exit 1
fi

if ! docker ps | grep -q echo_tool; then
  echo "ERROR: echo_tool container is not running"
  docker-compose logs echo_tool
  exit 1
fi

echo "All critical services are running!"

# Step 3: Health Check
echo ""
echo "[3/6] Running health checks..."
health_ok=false
for i in {1..10}; do
  echo "Health check attempt $i/10..."
  if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "OK Agent Host is healthy"
    health_ok=true
    break
  fi
  sleep 3
done

if [ "$health_ok" = false ]; then
  echo "ERROR: Agent Host health check failed after 10 attempts"
  echo "Container logs:"
  docker-compose logs agent_host
  exit 1
fi

# Step 4: Run All Workloads
echo ""
echo "[4/6] Running all workloads..."

workloads=(
  "w1_pure_mcp"
  "w2_light_tool"
  "w3_medium_tool"
  "w4_deep_workflow"
  "w5_large_payload"
  "w6_multi_tool"
  "w7_mixed"
)

timestamp=$(date +%Y-%m-%d_%H-%M-%S)
successful=0
failed=0

for workload in "${workloads[@]}"; do
  echo ""
  echo "  Running workload: $workload"
  
  if [ ! -f "benchmarks/workloads/$workload.json" ]; then
    echo "    SKIP Workload file not found"
    continue
  fi
  
  start_time=$(date +%s)
  
  response=$(curl -s -w "\n%{http_code}" -X POST http://localhost:8000/run \
    -H "Content-Type: application/json" \
    -d @benchmarks/workloads/$workload.json 2>&1)
  
  http_code=$(echo "$response" | tail -n1)
  
  if [ "$http_code" = "200" ]; then
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    echo "    OK Completed in ${duration}s"
    ((successful++))
  else
    echo "    FAIL HTTP Status: $http_code"
    ((failed++))
  fi
  
  sleep 2
done

# Step 5: Display Monitoring URLs
echo ""
echo "[5/6] Monitoring dashboards available at:"
echo "  - Prometheus: http://localhost:9090"
echo "  - Grafana:    http://localhost:3000 (admin/admin)"
echo "  - Agent Host: http://localhost:8000/health"
echo "  - Echo Tool:  http://localhost:8001"

# Step 6: Collect Logs
echo ""
echo "[6/6] Collecting logs and results..."
mkdir -p data/logs

echo "Exporting container logs..."
docker-compose logs agent_host > data/logs/agent_host_$timestamp.log 2>&1 || echo "Failed to export agent_host logs"
docker-compose logs echo_tool > data/logs/echo_tool_$timestamp.log 2>&1 || echo "Failed to export echo_tool logs"
docker-compose logs ollama > data/logs/ollama_$timestamp.log 2>&1 || echo "Failed to export ollama logs"
echo "Logs saved in data/logs/"

# Summary Report
echo ""
echo "=========================================================================="
echo "TEST EXECUTION SUMMARY"
echo "=========================================================================="
echo ""
echo "Execution Statistics:"
echo "  Total Workloads: ${#workloads[@]}"
echo "  Successful: $successful"
echo "  Failed: $failed"
echo ""
echo "Next Steps:"
echo "  1. View metrics in Grafana: http://localhost:3000"
echo "  2. Check Prometheus: http://localhost:9090"
echo "  3. View logs: cat data/logs/agent_host_$timestamp.log"
echo "  4. Stop services: docker-compose down"
echo ""
echo "OK Test run complete!"
