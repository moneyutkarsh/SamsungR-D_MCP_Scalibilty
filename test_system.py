#!/usr/bin/env python3
"""
Quick Test Script for MCP Scalability Analysis
Tests all major components of the system
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_health():
    """Check if all services are healthy"""
    print("\n[INFO] Testing Service Health...")
    
    services = {
        "Agent Host": "http://localhost:8000/metrics",
        "Echo Tool": "http://localhost:8001/health",
        "Prometheus": "http://localhost:9090/-/healthy",
        "Grafana": "http://localhost:3000/api/health",
    }
    
    for name, url in services.items():
        try:
            if "health" in url or "healthy" in url:
                response = requests.get(url, timeout=5)
            else:
                response = requests.get(url, timeout=5)
            print(f"  [PASS] {name}: {response.status_code}")
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")

def test_mock_adapter():
    """Test with MockAdapter (zero-latency baseline)"""
    print("\n[TEST] Testing with MockAdapter...")
    
    workload = {
        "workload": {
            "name": "test_mock",
            "description": "Minimal validated echo workload",
            "model": "mock",
            "execution_mode": "sequential",
            "workflow": ["echo"],
            "tool_params": {"delay_ms": 0, "payload_size_kb": 1},
            "payload": {"text": "hello world"}
        }
    }
    
    try:
        start = time.time()
        response = requests.post(f"{BASE_URL}/run", json=workload, timeout=10)
        elapsed = (time.time() - start) * 1000
        
        if response.status_code == 200:
            data = response.json()
            print(f"  [PASS] Success! Latency: {elapsed:.2f}ms")
            print(f"  [METRICES] Metrics: {json.dumps(data.get('result', {}).get('metrics', {}), indent=2)}")
        else:
            print(f"  [FAIL] Failed: {response.status_code}")
            print(f"  Error: {response.text}")
    except Exception as e:
        print(f"  [FAIL] Exception: {e}")

def test_workload_w1():
    """Test W1: Pure MCP Overhead"""
    print("\n[TEST] Testing W1: Pure MCP Overhead...")
    
    try:
        with open("benchmarks/workloads/w1_pure_mcp.json", "r") as f:
            workload = json.load(f)
        
        start = time.time()
        response = requests.post(f"{BASE_URL}/run", json=workload, timeout=10)
        elapsed = (time.time() - start) * 1000
        
        if response.status_code == 200:
            data = response.json()
            metrics = data.get('result', {}).get('metrics', {})
            print(f"  [PASS] Success! Total latency: {elapsed:.2f}ms")
            print(f"  [METRICES] MCP Protocol Overhead: {metrics.get('mcp_protocol_overhead_ms', 0):.2f}ms")
            print(f"  [METRICES] Tool Processing: {metrics.get('tool_processing_ms', 0):.2f}ms")
            print(f"  [METRICES] Pipeline Overhead: {metrics.get('pipeline_overhead_ms', 0):.2f}ms")
        else:
            print(f"  [FAIL] Failed: {response.status_code}")
            print(f"  Error: {response.text}")
    except Exception as e:
        print(f"  [FAIL] Exception: {e}")

def test_logs():
    """Check if JSONL logs are being written"""
    print("\n[LOG] Checking JSONL Logs...")
    
    import os
    log_files = [
        "data/logs/agent_host.jsonl",
        "data/logs/tool_executor.jsonl",
        "data/logs/echo_tool.jsonl"
    ]
    
    for log_file in log_files:
        if os.path.exists(log_file):
            size = os.path.getsize(log_file)
            if size > 0:
                print(f"  [PASS] {log_file}: {size} bytes")
                # Read last line
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        last = json.loads(lines[-1])
                        print(f"     Last entry: trace_id={last.get('trace_id', 'N/A')}")
            else:
                print(f"  [WARN] {log_file}: empty")
        else:
            print(f"  [FAIL] {log_file}: not found")

def test_prometheus_metrics():
    """Check if Prometheus is scraping metrics"""
    print("\n[METRICS] Checking Prometheus Metrics...")
    
    try:
        response = requests.get("http://localhost:9090/api/v1/query?query=mcp_requests_total", timeout=5)
        if response.status_code == 200:
            data = response.json()
            result = data.get('data', {}).get('result', [])
            if result:
                value = result[0].get('value', [0, 0])[1]
                print(f"  [PASS] mcp_requests_total: {value}")
            else:
                print(f"  [WARN] No metrics collected yet")
        else:
            print(f"  [FAIL] Failed: {response.status_code}")
    except Exception as e:
        print(f"  [FAIL] Exception: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("MCP Scalability Analysis - Quick Test Suite")
    print("=" * 60)
    
    test_health()
    test_mock_adapter()
    test_workload_w1()
    test_logs()
    test_prometheus_metrics()
    
    print("\n" + "=" * 60)
    print("[PASS] Test suite complete!")
    print("=" * 60)
    print("\nNext Steps:")
    print("  1. Check logs: docker logs agent_host")
    print("  2. View metrics: http://localhost:9090")
    print("  3. Run load test: locust -f benchmarks/locustfiles/locustfile.py")
    print("  4. View Grafana: http://localhost:3000 (admin/admin)")
