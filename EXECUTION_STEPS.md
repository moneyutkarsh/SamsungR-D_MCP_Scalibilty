# MCP Scalability Analysis - Complete Execution Guide

## Prerequisites
- Docker Desktop installed and running
- Python 3.11+ installed
- Git installed

---

## Step 1: Setup Ollama (AI Model Server)

### 1.1 Install Ollama

**Windows (PowerShell):**
```powershell
# Download and install from https://ollama.ai/download
# Or use winget
winget install Ollama.Ollama
```

**Linux (Bash):**
```bash
# Install using official script
curl -fsSL https://ollama.ai/install.sh | sh

# Or manually download and install
# Visit https://ollama.ai/download for latest version
```

### 1.2 Start Ollama Service

**Windows (PowerShell):**
```powershell
# Ollama runs as a service automatically after installation
# Verify it's running
curl http://localhost:11434
```

**Linux (Bash):**
```bash
# Start Ollama service (if not running)
sudo systemctl start ollama

# Enable Ollama to start on boot
sudo systemctl enable ollama

# Verify it's running
curl http://localhost:11434
```

### 1.3 Pull and Setup Model

**Windows (PowerShell) / Linux (Bash) - Same commands:**
```bash
# Pull a lightweight model for testing (recommended: phi3 or llama3.2)
ollama pull phi3:mini

# Or for production testing
ollama pull llama3.2

# Verify model is available
ollama list

# Test the model
ollama run phi3:mini "Hello, how are you?"
```

---

## Step 2: Setup Your Python Environment

### 2.1 Create Virtual Environment

**Windows (PowerShell):**
```powershell
cd "d:\Projects\SRIB-PRISM\MCP Scalability\MCP_project\mcp-scalability-analysis"

# Create virtual environment
python -m venv venv

# Activate it
.\venv\Scripts\Activate.ps1
```

**Linux (Bash):**
```bash
cd /path/to/mcp-scalability-analysis

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate
```

### 2.2 Install Dependencies

**Windows (PowerShell) / Linux (Bash) - Same commands:**
```bash
pip install -r requirements.txt
```

---

## Step 3: Configure Your Application

### 3.1 Update Model Configuration
Edit configuration files or environment variables:

```yaml
# Example config/config.yaml
model:
  provider: "ollama"
  name: "phi3:mini"  # or "llama3.2"
  base_url: "http://localhost:11434"
  temperature: 0.7
  max_tokens: 500

mcp:
  servers:
    - name: "echo_server"
      command: "python"
      args: ["servers/echo_server.py"]
      timeout: 30

monitoring:
  prometheus_port: 9090
  pushgateway_url: "http://localhost:9091"
  metrics_enabled: true
```

---

## Step 4: Start Infrastructure with Docker Compose

### 4.1 Start All Services

**Windows (PowerShell) / Linux (Bash) - Same commands:**
```bash
# Start Prometheus, Grafana, and other services
docker-compose up --build -d
```

### 4.2 Verify Services are Running

**Windows (PowerShell) / Linux (Bash) - Same commands:**
```bash
# Check all containers
docker-compose ps

# Should show:
# - prometheus (port 9090)
# - grafana (port 3000)
# - pushgateway (port 9091)
```

### 4.3 Access Web UIs

**Windows (PowerShell):**
```powershell
# Prometheus - http://localhost:9090
Start-Process "http://localhost:9090"

# Grafana - http://localhost:3000 (default login: admin/admin)
Start-Process "http://localhost:3000"
```

**Linux (Bash):**
```bash
# Open in default browser
xdg-open http://localhost:9090  # Prometheus
xdg-open http://localhost:3000  # Grafana

# Or manually open:
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (default login: admin/admin)
```

---

## Step 5: Start Your MCP Application

### 5.1 Start the Main Application Server

**Windows (PowerShell) / Linux (Bash) - Same commands:**
```bash
# In terminal 1 (with venv activated)
python main.py

# Or if using src/orchestrator/agent_host.py directly
python src/orchestrator/agent_host.py
```

You should see:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 5.2 Verify Server is Running

**Windows (PowerShell) / Linux (Bash) - Same commands:**
```bash
# In a new terminal
curl http://localhost:8000/health

# Should return: {"status":"healthy"}
```

---

## Step 6: Run Single Workload Test

### 6.1 Test with Pure MCP Workload

**Windows (PowerShell):**
```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/run" `
  -ContentType "application/json" `
  -InFile "benchmarks/workloads/w1_pure_mcp.json"
```

**Linux (Bash):**
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d @benchmarks/workloads/w1_pure_mcp.json \
  http://localhost:8000/run
```

### 6.2 Test Other Workloads

**Windows (PowerShell):**
```powershell
# Light tool test (10ms delay)
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/run" `
  -ContentType "application/json" `
  -InFile "benchmarks/workloads/w2_light_tool.json"

# Medium tool test (100ms delay)
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/run" `
  -ContentType "application/json" `
  -InFile "benchmarks/workloads/w3_medium_tool.json"

# Deep workflow test (5 steps)
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/run" `
  -ContentType "application/json" `
  -InFile "benchmarks/workloads/w4_deep_workflow.json"

# Large payload test (1MB)
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/run" `
  -ContentType "application/json" `
  -InFile "benchmarks/workloads/w5_large_payload.json"

# Multi-tool test (5 tools)
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/run" `
  -ContentType "application/json" `
  -InFile "benchmarks/workloads/w6_multi_tool.json"

# Mixed workload
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/run" `
  -ContentType "application/json" `
  -InFile "benchmarks/workloads/w7_mixed.json"
```

**Linux (Bash):**
```bash
# Light tool test (10ms delay)
curl -X POST -H "Content-Type: application/json" \
  -d @benchmarks/workloads/w2_light_tool.json \
  http://localhost:8000/run

# Medium tool test (100ms delay)
curl -X POST -H "Content-Type: application/json" \
  -d @benchmarks/workloads/w3_medium_tool.json \
  http://localhost:8000/run

# Deep workflow test (5 steps)
curl -X POST -H "Content-Type: application/json" \
  -d @benchmarks/workloads/w4_deep_workflow.json \
  http://localhost:8000/run

# Large payload test (1MB)
curl -X POST -H "Content-Type: application/json" \
  -d @benchmarks/workloads/w5_large_payload.json \
  http://localhost:8000/run

# Multi-tool test (5 tools)
curl -X POST -H "Content-Type: application/json" \
  -d @benchmarks/workloads/w6_multi_tool.json \
  http://localhost:8000/run

# Mixed workload
curl -X POST -H "Content-Type: application/json" \
  -d @benchmarks/workloads/w7_mixed.json \
  http://localhost:8000/run
```

---

## Step 7: Run Load Tests with Locust

### 7.1 Install Locust (if not already installed)

**Windows (PowerShell) / Linux (Bash) - Same commands:**
```bash
pip install locust
```

### 7.2 Update Locustfile for Correct Payload
The locustfile has been updated to use the correct workload format. Check `benchmarks/locustfiles/locustfile.py`.

### 7.3 Start Locust Web UI

**Windows (PowerShell):**
```powershell
# In a new terminal (with venv activated)
cd "d:\Projects\SRIB-PRISM\MCP Scalability\MCP_project\mcp-scalability-analysis"
.\venv\Scripts\Activate.ps1

locust -f benchmarks/locustfiles/locustfile.py --host=http://localhost:8000
```

**Linux (Bash):**
```bash
# In a new terminal (with venv activated)
cd /path/to/mcp-scalability-analysis
source venv/bin/activate

locust -f benchmarks/locustfiles/locustfile.py --host=http://localhost:8000
```

### 7.4 Configure and Run Load Test
1. Open browser to http://localhost:8089
2. Enter:
   - **Number of users**: 10 (start small)
   - **Spawn rate**: 2 users/second
   - **Host**: http://localhost:8000
3. Click "Start Swarming"

### 7.5 Monitor the Load Test
- Watch requests per second (RPS)
- Monitor response times (p50, p95, p99)
- Check failure rate
- Gradually increase users: 10 → 50 → 100 → 500

### 7.6 Run Headless Load Test (Optional)

**Windows (PowerShell):**
```powershell
# Run without web UI
locust -f benchmarks/locustfiles/locustfile.py `
  --host=http://localhost:8000 `
  --users 100 `
  --spawn-rate 10 `
  --run-time 5m `
  --headless `
  --csv=results/locust_results
```

**Linux (Bash):**
```bash
# Run without web UI
locust -f benchmarks/locustfiles/locustfile.py \
  --host=http://localhost:8000 \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m \
  --headless \
  --csv=results/locust_results
```

---

## Step 8: Query Prometheus Metrics

### 8.1 Access Prometheus UI

**Windows (PowerShell):**
```powershell
Start-Process "http://localhost:9090"
```

**Linux (Bash):**
```bash
# Open in default browser
xdg-open http://localhost:9090

# Or manually navigate to: http://localhost:9090
```

### 8.2 Useful Prometheus Queries

**Request Rate (Requests per second):**
```promql
rate(mcp_requests_total[1m])
```

**Average Latency:**
```promql
rate(mcp_request_duration_seconds_sum[1m]) / rate(mcp_request_duration_seconds_count[1m])
```

**95th Percentile Latency:**
```promql
histogram_quantile(0.95, rate(mcp_request_duration_seconds_bucket[1m]))
```

**99th Percentile Latency:**
```promql
histogram_quantile(0.99, rate(mcp_request_duration_seconds_bucket[1m]))
```

**Error Rate:**
```promql
rate(mcp_requests_total{status="error"}[1m])
```

**Success Rate:**
```promql
rate(mcp_requests_total{status="success"}[1m]) / rate(mcp_requests_total[1m]) * 100
```

**Active MCP Sessions:**
```promql
mcp_active_sessions
```

**Tool Execution Count:**
```promql
sum(rate(mcp_tool_calls_total[1m])) by (tool_name)
```

**Memory Usage:**
```promql
process_resident_memory_bytes
```

**CPU Usage:**
```promql
rate(process_cpu_seconds_total[1m])
```

### 8.3 Export Data from Prometheus

**Windows (PowerShell):**
```powershell
# Query Prometheus API
Invoke-RestMethod "http://localhost:9090/api/v1/query?query=rate(mcp_requests_total[5m])" | ConvertTo-Json
```

**Linux (Bash):**
```bash
# Query Prometheus API
curl "http://localhost:9090/api/v1/query?query=rate(mcp_requests_total[5m])" | jq

# Or without jq for formatting
curl "http://localhost:9090/api/v1/query?query=rate(mcp_requests_total[5m])"
```

---

## Step 9: Setup Grafana Dashboards

### 9.1 Login to Grafana
1. Go to http://localhost:3000
2. Login with default credentials: **admin/admin**
3. Change password when prompted

### 9.2 Add Prometheus Data Source
1. Go to **Configuration** → **Data Sources** (or click gear icon)
2. Click **Add data source**
3. Select **Prometheus**
4. Set URL: `http://prometheus:9090`
   - If connection fails, try: `http://host.docker.internal:9090` (Windows/Mac)
   - Or use the IP: `http://172.17.0.1:9090` (Linux)
5. Click **Save & Test**
6. Should show: "Data source is working"

### 9.3 Create Dashboard - Option 1: Manual

1. Click **+** (plus icon) → **Dashboard**
2. Click **Add visualization**
3. Select **Prometheus** data source
4. Add panels with queries from Step 8.2

**Panel Examples:**

**Request Rate Panel:**
- Title: "Request Rate (RPS)"
- Query: `rate(mcp_requests_total[1m])`
- Visualization: Time series

**Latency Panel:**
- Title: "Response Time Percentiles"
- Queries:
  - P50: `histogram_quantile(0.50, rate(mcp_request_duration_seconds_bucket[1m]))`
  - P95: `histogram_quantile(0.95, rate(mcp_request_duration_seconds_bucket[1m]))`
  - P99: `histogram_quantile(0.99, rate(mcp_request_duration_seconds_bucket[1m]))`
- Visualization: Time series

**Error Rate Panel:**
- Title: "Error Rate"
- Query: `rate(mcp_requests_total{status="error"}[1m])`
- Visualization: Time series

### 9.4 Create Dashboard - Option 2: Import JSON

Create a dashboard JSON file:

```json
{
  "dashboard": {
    "title": "MCP Scalability Dashboard",
    "panels": [
      {
        "title": "Request Rate (RPS)",
        "targets": [{"expr": "rate(mcp_requests_total[1m])"}],
        "type": "timeseries",
        "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8}
      },
      {
        "title": "P95 Latency",
        "targets": [{"expr": "histogram_quantile(0.95, rate(mcp_request_duration_seconds_bucket[1m]))"}],
        "type": "timeseries",
        "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8}
      },
      {
        "title": "Error Rate",
        "targets": [{"expr": "rate(mcp_requests_total{status=\"error\"}[1m])"}],
        "type": "timeseries",
        "gridPos": {"x": 0, "y": 8, "w": 12, "h": 8}
      },
      {
        "title": "Active Sessions",
        "targets": [{"expr": "mcp_active_sessions"}],
        "type": "timeseries",
        "gridPos": {"x": 12, "y": 8, "w": 12, "h": 8}
      }
    ]
  }
}
```

Import:
1. Click **+** → **Import**
2. Paste JSON or upload file
3. Select Prometheus data source
4. Click **Import**

---

## Step 10: Run Complete Benchmark Suite

### 10.1 Run All Workloads Sequentially

**Windows (PowerShell):**
```powershell
# Create and run benchmark script
$workloadFiles = Get-ChildItem "benchmarks/workloads/*.json"
$results = @()

foreach ($file in $workloadFiles) {
    Write-Host "`nRunning $($file.Name)..." -ForegroundColor Cyan
    
    $response = Invoke-RestMethod `
        -Method Post `
        -Uri "http://localhost:8000/run" `
        -ContentType "application/json" `
        -InFile $file.FullName
    
    Write-Host "Status: Success" -ForegroundColor Green
    $results += @{
        workload = $file.BaseName
        status = "Success"
    }
    
    Start-Sleep -Seconds 2
}

Write-Host "`n=== Summary ===" -ForegroundColor Yellow
$results | ForEach-Object { Write-Host "$($_.workload): $($_.status)" }
```

**Linux (Bash):**
```bash
# Create and run benchmark script
echo "Running all workloads..."

for workload in benchmarks/workloads/*.json; do
    echo -e "\n\033[36mRunning $(basename $workload)...\033[0m"
    
    curl -X POST \
        -H "Content-Type: application/json" \
        -d @"$workload" \
        http://localhost:8000/run \
        && echo -e "\033[32mStatus: Success\033[0m" \
        || echo -e "\033[31mStatus: Failed\033[0m"
    
    sleep 2
done

echo -e "\n\033[33m=== Summary ===\033[0m"
echo "All workloads completed"
```

### 10.2 Run Comprehensive Load Test

**Windows (PowerShell):**
```powershell
# Run multiple load test scenarios
$scenarios = @(
    @{users=10; rate=2; time="2m"},
    @{users=50; rate=10; time="5m"},
    @{users=100; rate=20; time="5m"},
    @{users=200; rate=50; time="5m"}
)

foreach ($scenario in $scenarios) {
    Write-Host "`nRunning: $($scenario.users) users, spawn rate $($scenario.rate)/s" -ForegroundColor Cyan
    
    locust -f benchmarks/locustfiles/locustfile.py `
        --host=http://localhost:8000 `
        --users $scenario.users `
        --spawn-rate $scenario.rate `
        --run-time $scenario.time `
        --headless `
        --csv="data/results/load_test_$($scenario.users)users"
    
    Start-Sleep -Seconds 10
}
```

**Linux (Bash):**
```bash
# Run multiple load test scenarios
declare -a scenarios=(
    "10:2:2m"
    "50:10:5m"
    "100:20:5m"
    "200:50:5m"
)

for scenario in "${scenarios[@]}"; do
    IFS=':' read -r users rate time <<< "$scenario"
    echo -e "\n\033[36mRunning: ${users} users, spawn rate ${rate}/s\033[0m"
    
    locust -f benchmarks/locustfiles/locustfile.py \
        --host=http://localhost:8000 \
        --users ${users} \
        --spawn-rate ${rate} \
        --run-time ${time} \
        --headless \
        --csv="data/results/load_test_${users}users"
    
    sleep 10
done
```

---

## Step 11: Analyze Results

### 11.1 Check Application Logs

**Windows (PowerShell):**
```powershell
# View logs in real-time
Get-Content data/logs/agent_host.jsonl -Tail 50 -Wait

# Parse JSONL logs
Get-Content data/logs/agent_host.jsonl | ForEach-Object {
    $_ | ConvertFrom-Json
} | Select-Object timestamp, level, message | Format-Table
```

**Linux (Bash):**
```bash
# View logs in real-time
tail -f -n 50 data/logs/agent_host.jsonl

# Parse JSONL logs (with jq)
cat data/logs/agent_host.jsonl | jq -r '[.timestamp, .level, .message] | @tsv'

# Or without jq
cat data/logs/agent_host.jsonl | grep -E '"timestamp"|"level"|"message"'
```

### 11.2 Analyze Locust Results

**Windows (PowerShell):**
```powershell
# View CSV results
Import-Csv data/results/locust_results_stats.csv | Format-Table

# Calculate statistics
$stats = Import-Csv data/results/locust_results_stats.csv
$stats | Where-Object {$_.Name -ne "Aggregated"} | ForEach-Object {
    [PSCustomObject]@{
        Name = $_.Name
        Requests = $_.Requests
        Failures = $_.Failures
        AvgResponseTime = "$($_.'Average Response Time') ms"
        P95 = "$($_.'95%') ms"
        P99 = "$($_.'99%') ms"
    }
} | Format-Table
```

**Linux (Bash):**
```bash
# View CSV results
cat data/results/locust_results_stats.csv | column -t -s,

# Or using csvkit (if installed)
csvsql --query "SELECT * FROM locust_results_stats WHERE Name != 'Aggregated'" \
    data/results/locust_results_stats.csv | csvlook

# Simple awk parsing
awk -F, 'NR==1 || $1 != "Aggregated" {print $1, $2, $3, $8, $10, $11}' \
    data/results/locust_results_stats.csv | column -t
```

### 11.3 Query Prometheus for Historical Data

**Windows (PowerShell):**
```powershell
# Get average latency over last hour
$query = "avg_over_time(mcp_request_duration_seconds_sum[1h])"
Invoke-RestMethod "http://localhost:9090/api/v1/query?query=$query" | ConvertTo-Json -Depth 10
```

**Linux (Bash):**
```bash
# Get average latency over last hour
query="avg_over_time(mcp_request_duration_seconds_sum[1h])"
curl -G "http://localhost:9090/api/v1/query" \
    --data-urlencode "query=${query}" | jq
```

### 11.4 Generate Summary Report

**Windows (PowerShell) / Linux (Bash) - Same commands:**
```bash
# Run the summarize script
python scripts/summarize_run.py --input data/results/ --output reports/summary.md
```

---

## Step 12: Advanced Monitoring

### 12.1 Set up Alerts in Prometheus

Edit `infrastructure/prometheus/prometheus.yml` to add alerting rules:

```yaml
rule_files:
  - 'alerts.yml'

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']
```

Create `infrastructure/prometheus/alerts.yml`:

```yaml
groups:
  - name: mcp_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(mcp_requests_total{status="error"}[5m]) > 0.05
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} req/s"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(mcp_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency detected"
          description: "P95 latency is {{ $value }}s"
```

### 12.2 Enable Tracing (if implemented)

**Windows (PowerShell):**
```powershell
# Set environment variable for tracing
$env:ENABLE_TRACING = "true"
$env:JAEGER_ENDPOINT = "http://localhost:14268/api/traces"

# Restart application
python main.py
```

**Linux (Bash):**
```bash
# Set environment variable for tracing
export ENABLE_TRACING="true"
export JAEGER_ENDPOINT="http://localhost:14268/api/traces"

# Restart application
python main.py
```

---

## Step 13: Cleanup

### 13.1 Stop Load Tests
```powershell
# Stop Locust (Ctrl+C in terminal)
```

### 13.2 Stop Application
```powershell
# Stop main application (Ctrl+C in terminal)
```

### 13.3 Stop Docker Services

**Windows (PowerShell) / Linux (Bash) - Same commands:**
```bash
# Stop all docker-compose services
docker-compose down

# Or stop and remove volumes
docker-compose down -v
```

### 13.4 Stop Ollama (Optional)

**Windows (PowerShell):**
```powershell
# Stop Ollama service
Stop-Service Ollama

# Or restart it
Restart-Service Ollama
```

**Linux (Bash):**
```bash
# Stop Ollama service
sudo systemctl stop ollama

# Or restart it
sudo systemctl restart ollama
```

### 13.5 Deactivate Virtual Environment

**Windows (PowerShell) / Linux (Bash) - Same commands:**
```bash
deactivate
```

### 13.6 Archive Results

**Windows (PowerShell):**
```powershell
# Create archive of results
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
Compress-Archive -Path "data/results/*" -DestinationPath "archives/results_$timestamp.zip"
```

**Linux (Bash):**
```bash
# Create archive of results
timestamp=$(date +%Y%m%d_%H%M%S)
tar -czf "archives/results_${timestamp}.tar.gz" data/results/

# Or using zip
zip -r "archives/results_${timestamp}.zip" data/results/
```

---

## Troubleshooting

### Issue 1: "Connection refused" to Ollama

**Windows (PowerShell):**
```powershell
# Check Ollama service status
Get-Service Ollama

# If not running, start it
Start-Service Ollama

# Verify it's listening
netstat -ano | findstr "11434"

# Test connection
curl http://localhost:11434
```

**Linux (Bash):**
```bash
# Check Ollama service status
sudo systemctl status ollama

# If not running, start it
sudo systemctl start ollama

# Verify it's listening
ss -tulpn | grep 11434
# Or using netstat
netstat -tulpn | grep 11434

# Test connection
curl http://localhost:11434
```

### Issue 2: Docker containers won't start

**Windows (PowerShell):**
```powershell
# Check Docker Desktop is running
docker ps

# Check logs
docker-compose logs prometheus
docker-compose logs grafana

# Check port conflicts
netstat -ano | findstr "9090"
netstat -ano | findstr "3000"

# Kill process using port (if needed)
# Get PID from netstat output, then:
Stop-Process -Id <PID> -Force
```

**Linux (Bash):**
```bash
# Check Docker is running
docker ps
sudo systemctl status docker

# Check logs
docker-compose logs prometheus
docker-compose logs grafana

# Check port conflicts
sudo ss -tulpn | grep -E '9090|3000'
# Or using netstat
sudo netstat -tulpn | grep -E '9090|3000'

# Kill process using port (if needed)
# Get PID from ss/netstat output, then:
sudo kill -9 <PID>
```

### Issue 3: Prometheus not scraping metrics

**Windows (PowerShell):**
```powershell
# Check Prometheus targets
Start-Process "http://localhost:9090/targets"

# Verify pushgateway is accessible
curl http://localhost:9091

# Check prometheus.yml configuration
Get-Content infrastructure/prometheus/prometheus.yml

# Restart prometheus
docker-compose restart prometheus
```

**Linux (Bash):**
```bash
# Check Prometheus targets
xdg-open "http://localhost:9090/targets"
# Or manually navigate to: http://localhost:9090/targets

# Verify pushgateway is accessible
curl http://localhost:9091

# Check prometheus.yml configuration
cat infrastructure/prometheus/prometheus.yml

# Restart prometheus
docker-compose restart prometheus
```

### Issue 4: High failure rate in Locust
**Solutions:**
- Reduce spawn rate: `--spawn-rate 1`
- Increase wait time in locustfile: `wait_time = between(1, 2)`
- Check application logs: `Get-Content data/logs/agent_host.jsonl -Tail 100`
- Verify workload JSON format is correct
- Check if server is overloaded (reduce user count)

### Issue 5: Grafana can't connect to Prometheus
**Solutions:**
1. Use container name: `http://prometheus:9090`
2. Use host IP: `http://host.docker.internal:9090` (Windows/Mac)
3. Use network IP: `http://172.17.0.1:9090`
4. Check if both are on same Docker network:
   ```powershell
   docker network inspect mcp-scalability-analysis_default
   ```

### Issue 6: Python dependencies not found

**Windows (PowerShell):**
```powershell
# Ensure virtual environment is activated
.\venv\Scripts\Activate.ps1

# Verify venv is active (should show venv path)
Get-Command python | Select-Object Source

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

**Linux (Bash):**
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Verify venv is active (should show venv path)
which python

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Issue 7: Workload test returns 422 error
**Solution:** Ensure workload JSON has correct format:
```json
{
  "workload": {
    "name": "test_name",
    "model": "mock",
    "workflow": ["echo"],
    "tool_params": {"delay_ms": 0, "payload_size_kb": 1},
    "payload": {"text": "test"}
  }
}
```

---

## Quick Reference Commands

### Start Everything

**Windows (PowerShell):**
```powershell
# Terminal 1: Start infrastructure
docker-compose up -d

# Terminal 2: Start application
.\venv\Scripts\Activate.ps1
python main.py

# Terminal 3: Start Locust
.\venv\Scripts\Activate.ps1
locust -f benchmarks/locustfiles/locustfile.py --host=http://localhost:8000
```

**Linux (Bash):**
```bash
# Terminal 1: Start infrastructure
docker-compose up -d

# Terminal 2: Start application
source venv/bin/activate
python main.py

# Terminal 3: Start Locust
source venv/bin/activate
locust -f benchmarks/locustfiles/locustfile.py --host=http://localhost:8000
```

### Check Status

**Windows (PowerShell) / Linux (Bash) - Same commands:**
```bash
# Application health
curl http://localhost:8000/health

# Docker services
docker-compose ps

# Prometheus health
curl http://localhost:9090/-/healthy

# Grafana health
curl http://localhost:3000/api/health

# Ollama status
curl http://localhost:11434
```

### View Dashboards

**Windows (PowerShell):**
```powershell
# Prometheus
Start-Process "http://localhost:9090"

# Grafana
Start-Process "http://localhost:3000"

# Locust
Start-Process "http://localhost:8089"
```

**Linux (Bash):**
```bash
# Open in default browser
xdg-open http://localhost:9090  # Prometheus
xdg-open http://localhost:3000  # Grafana
xdg-open http://localhost:8089  # Locust
```

### Stop Everything

**Windows (PowerShell) / Linux (Bash) - Same commands:**
```bash
# Stop application (Ctrl+C in terminals)
# Stop docker services
docker-compose down
```

---

## Performance Tuning Tips

### 1. Optimize Ollama Performance

**Windows (PowerShell) / Linux (Bash) - Same commands:**
```bash
# Use smaller models for faster responses
ollama pull phi3:mini  # ~2GB

# Set context window size
ollama run phi3:mini --num-ctx 2048

# Increase parallel requests (edit Ollama config)
# Set OLLAMA_NUM_PARALLEL=4
```

**Linux (Bash) - Set environment variable permanently:**
```bash
# Add to ~/.bashrc or ~/.profile
echo 'export OLLAMA_NUM_PARALLEL=4' >> ~/.bashrc
source ~/.bashrc
```

**Windows (PowerShell) - Set environment variable permanently:**
```powershell
# Set system-wide environment variable
[Environment]::SetEnvironmentVariable('OLLAMA_NUM_PARALLEL', '4', 'User')
```

### 2. Tune Application Settings
- Increase worker threads/processes
- Enable connection pooling
- Adjust timeout values
- Enable caching for repeated queries

### 3. Optimize Prometheus
- Reduce scrape interval for less storage: `scrape_interval: 30s`
- Set retention time: `--storage.tsdb.retention.time=7d`
- Increase memory: `--storage.tsdb.path=/prometheus --storage.tsdb.retention.time=15d`

### 4. Scale Locust

**Windows (PowerShell) / Linux (Bash) - Same commands:**
```bash
# Run distributed Locust for higher load
# Master node:
locust -f locustfile.py --master

# Worker nodes (run multiple):
locust -f locustfile.py --worker --master-host=localhost
```

---

## Useful Monitoring Queries

### System Resource Usage
```promql
# CPU usage
rate(process_cpu_seconds_total[1m])

# Memory usage
process_resident_memory_bytes / 1024 / 1024

# Open file descriptors
process_open_fds

# Thread count
process_threads
```

### Application Metrics
```promql
# Request throughput
sum(rate(mcp_requests_total[1m]))

# Average response time
avg(rate(mcp_request_duration_seconds_sum[1m]) / rate(mcp_request_duration_seconds_count[1m]))

# Error percentage
sum(rate(mcp_requests_total{status="error"}[1m])) / sum(rate(mcp_requests_total[1m])) * 100

# Tool usage distribution
sum(rate(mcp_tool_calls_total[5m])) by (tool_name)
```

---

## Next Steps

1. **Baseline Testing**: Run single-user tests to establish baseline metrics
2. **Load Testing**: Gradually increase load to find breaking points
3. **Stress Testing**: Push system beyond normal limits
4. **Endurance Testing**: Run sustained load for extended periods
5. **Analysis**: Compare results across different workloads and configurations
6. **Optimization**: Tune parameters based on findings
7. **Documentation**: Record findings in reports/

---

## Additional Resources

- **Locust Documentation**: https://docs.locust.io/
- **Prometheus Queries**: https://prometheus.io/docs/prometheus/latest/querying/basics/
- **Grafana Tutorials**: https://grafana.com/tutorials/
- **Ollama Documentation**: https://github.com/ollama/ollama/blob/main/docs/

---

## Notes

- Always start with small user counts and gradually increase
- Monitor system resources during tests (CPU, memory, disk I/O)
- Save test configurations and results for comparison
- Document any anomalies or unexpected behavior
- Use Grafana annotations to mark significant events during testing
