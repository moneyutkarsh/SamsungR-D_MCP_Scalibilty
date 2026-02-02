# Quick Start Guide

## 🚀 Run with Docker

### 1. Start Ollama and Pull Model
```powershell
# Start Ollama
docker-compose up -d ollama

# Wait for Ollama to start
Start-Sleep -Seconds 5

# Pull model
docker exec -it ollama ollama pull phi3:mini

# Verify model is available
docker exec -it ollama ollama list
```

### 2. Start All Services
```powershell
# Build and start all services (agent_host, echo_tool, ollama, prometheus, grafana)
docker-compose up --build -d

# Verify all containers are running
docker-compose ps
```

### 3. Test
```powershell
# Health check
curl http://localhost:8000/health

# Run workload
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/run" -ContentType "application/json" -InFile "benchmarks/workloads/w1_pure_mcp.json"
```

### 4. Access Dashboards
- **Application**: http://localhost:8000/health
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (login: admin/admin)

---

## 🧪 Run Load Tests

### Setup Locust (on your local machine)
```powershell
# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install Locust
pip install locust

# Start Locust
locust -f benchmarks/locustfiles/locustfile.py --host=http://localhost:8000
```

Open http://localhost:8089 and configure:
- Users: 10
- Spawn rate: 2
- Click "Start Swarming"

---

## 🛑 Stop Everything

```powershell
# Stop and remove all containers
docker-compose down

# Stop and remove containers + volumes
docker-compose down -v
```

---

## 📊 View Results

- **Logs**: Check with `docker-compose logs -f agent_host`
- **Prometheus metrics**: http://localhost:9090
- **Grafana dashboards**: http://localhost:3000

---

## 🐛 Troubleshooting

**Check container status:**
```powershell
docker-compose ps
docker-compose logs agent_host
docker-compose logs echo_tool
docker-compose logs ollama
```

**"Connection refused" to Ollama:**
```powershell
docker-compose restart ollama
docker exec -it ollama ollama list
```

**"Internal Server Error" on /run:**
```powershell
# Check if echo_tool is healthy
docker-compose logs echo_tool

# Restart services
docker-compose restart agent_host echo_tool
```

**Port already in use:**
```powershell
# Find process using port (e.g., 8000)
netstat -ano | findstr "8000"

# Stop it
Stop-Process -Id <PID> -Force
```

**Rebuild after code changes:**
```powershell
docker-compose up --build -d
```

For complete documentation, see [EXECUTION_STEPS.md](EXECUTION_STEPS.md)
