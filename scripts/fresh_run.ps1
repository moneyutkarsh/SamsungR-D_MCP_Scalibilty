param(
    [ValidateSet("baseline", "task2", "both")]
    [string]$Mode = "baseline",
    [int[]]$Users = @(1, 10, 50, 100, 200, 500),
    [int[]]$Task2Users = @(10, 50, 100),
    [int]$Repeats = 1,
    [int]$RequestsPerUser = 5,
    [int]$Task2RequestsPerUser = 5,
    [string]$Task2Model = "llama3.2:3b",
    [string]$AgentHost = "http://localhost:8000",
    [string]$PrometheusUrl = "http://localhost:9090",
    [switch]$KeepLogs,
    [switch]$KeepBaseline,
    [switch]$Build,
    [switch]$PruneDockerCache
)

$ErrorActionPreference = "Stop"

function Remove-Contents {
    param([string]$Path)
    if (Test-Path $Path) {
        Get-ChildItem -Path $Path -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Wait-ForHealth {
    param(
        [string]$BaseUrl,
        [int]$MaxAttempts = 40
    )

    $healthy = $false
    for ($i = 1; $i -le $MaxAttempts; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "$BaseUrl/health" -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200) {
                $healthy = $true
                break
            }
        } catch {
            Start-Sleep -Seconds 3
        }
    }

    if (-not $healthy) {
        throw "Agent health check failed after $MaxAttempts attempts."
    }
}

Write-Host "=== Fresh MCP Scalability Run ===" -ForegroundColor Cyan
Write-Host "Mode: $Mode"
Write-Host "Build images: $Build"
Write-Host "Baseline users: $($Users -join ', ')"
Write-Host "Task2 users: $($Task2Users -join ', ')"
Write-Host "Repeats: $Repeats"

Write-Host "[1/7] Stopping existing stack..." -ForegroundColor Yellow
docker-compose down | Out-Host

if ($PruneDockerCache) {
    Write-Host "[2/7] Pruning Docker cache/images (space cleanup)..." -ForegroundColor Yellow
    docker builder prune -af | Out-Host
    docker image prune -af | Out-Host
} else {
    Write-Host "[2/7] Skipping Docker cache prune..." -ForegroundColor DarkYellow
}

Write-Host "[3/7] Cleaning data folders for a fresh run..." -ForegroundColor Yellow
Remove-Contents "data/prometheus"
if ($KeepBaseline) {
    Write-Host "  (keeping existing baseline results)" -ForegroundColor DarkYellow
} else {
    Remove-Contents "data/results/baseline_mockadapter"
}
Remove-Contents "data/results/task2_initial_real_model"
if (-not $KeepLogs) {
    Remove-Contents "data/logs"
}

Write-Host "[4/7] Starting services..." -ForegroundColor Yellow
if ($Build) {
    docker-compose up --build -d | Out-Host
} else {
    docker-compose up -d | Out-Host
}
docker-compose ps | Out-Host

Write-Host "[5/7] Waiting for agent health..." -ForegroundColor Yellow
Wait-ForHealth -BaseUrl $AgentHost

if ($Mode -eq "baseline" -or $Mode -eq "both") {
    Write-Host "[6/7] Running baseline dataset script..." -ForegroundColor Yellow
    $baselineArgs = @(
        "scripts/run_baseline_dataset.py",
        "--host", $AgentHost,
        "--prometheus-url", $PrometheusUrl,
        "--users"
    )
    $baselineArgs += $Users | ForEach-Object { "$_" }
    $baselineArgs += @(
        "--repeats", "$Repeats",
        "--requests-per-user", "$RequestsPerUser"
    )
    python @baselineArgs | Out-Host
}

if ($Mode -eq "task2" -or $Mode -eq "both") {
    Write-Host "[6/7] Running Task 2 (Mock vs Ollama comparison)..." -ForegroundColor Yellow
    $task2Args = @(
        "scripts/run_task2_real_model_dataset.py",
        "--model", $Task2Model,
        "--users"
    )
    $task2Args += $Task2Users | ForEach-Object { "$_" }
    $task2Args += @(
        "--repeats", "$Repeats",
        "--requests-per-user", "$Task2RequestsPerUser",
        "--host", $AgentHost,
        "--prometheus-url", $PrometheusUrl
    )
    python @task2Args | Out-Host
}

Write-Host "[7/7] Verifying outputs..." -ForegroundColor Yellow
if (Test-Path "data/results/baseline_mockadapter") {
    Write-Host "Baseline CSVs:" -ForegroundColor Cyan
    Get-ChildItem "data/results/baseline_mockadapter" -Filter *.csv -ErrorAction SilentlyContinue |
        Select-Object Name, Length | Format-Table -AutoSize | Out-Host
}

if (Test-Path "data/results/task2_initial_real_model") {
    Write-Host "Task2 CSVs:" -ForegroundColor Cyan
    Get-ChildItem "data/results/task2_initial_real_model" -Filter *.csv -ErrorAction SilentlyContinue |
        Select-Object Name, Length | Format-Table -AutoSize | Out-Host
}

Write-Host ""
Write-Host "Fresh run complete." -ForegroundColor Green
Write-Host "Grafana: http://localhost:3000"
Write-Host "Prometheus: http://localhost:9090"
Write-Host "Baseline results: data/results/baseline_mockadapter"
Write-Host "Task2 results: data/results/task2_initial_real_model"
Write-Host ""
Write-Host "Examples:" -ForegroundColor Cyan
Write-Host "  .\scripts\fresh_run.ps1 -Mode baseline -Repeats 1"
Write-Host "  .\scripts\fresh_run.ps1 -Mode task2 -Repeats 1 -Task2Model llama3.2:3b -KeepBaseline"
Write-Host "  .\scripts\fresh_run.ps1 -Mode both -Repeats 1 -Build"
Write-Host "  .\scripts\fresh_run.ps1 -Mode task2 -PruneDockerCache -KeepBaseline"
