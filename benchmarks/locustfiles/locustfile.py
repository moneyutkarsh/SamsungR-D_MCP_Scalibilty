from locust import HttpUser, task, between

class MCPStressTestUser(HttpUser):
    wait_time = between(0.1, 0.5)  # Wait 100-500ms between requests

    @task(3)  # 60% of requests - pure MCP test
    def test_pure_mcp(self):
        """Test pure MCP overhead with no delay"""
        payload = {
            "workload": {
                "name": "w1_pure_mcp",
                "description": "Pure MCP overhead, zero delay",
                "model": "mock",
                "workflow": ["echo"],
                "tool_params": {"delay_ms": 0, "payload_size_kb": 1},
                "payload": {"text": "ping"}
            }
        }
        with self.client.post("/run", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status: {response.status_code}, Body: {response.text}")

    @task(2)  # 40% of requests - light tool test
    def test_light_tool(self):
        """Test with 10ms tool delay"""
        payload = {
            "workload": {
                "name": "w2_light_tool",
                "description": "Single tool, 10ms delay",
                "model": "ollama",
                "workflow": ["echo"],
                "tool_params": {"delay_ms": 10, "payload_size_kb": 1},
                "payload": {"text": "hello"}
            }
        }
        with self.client.post("/run", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status: {response.status_code}, Body: {response.text}")

    def on_start(self):
        """Called when a simulated user starts"""
        print("Starting MCP load test user")

