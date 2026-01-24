from locust import HttpUser, task, between

class MCPStressTestUser(HttpUser):
    wait_time = between(0.05, 0.1)

    @task
    def test_echo_scalability(self):
        payload = {"prompt": "benchmarking_test_string"}
        with self.client.post("/run", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status: {response.status_code}")
