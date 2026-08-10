import json
import os
import random
from pathlib import Path

from locust import HttpUser, between, task


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_workloads() -> list[dict]:
    workload_dir = Path(os.getenv("WORKLOAD_DIR", _project_root() / "benchmarks" / "workloads"))
    selected = os.getenv("WORKLOADS")
    if selected:
        names = [item.strip() for item in selected.split(",") if item.strip()]
        files = [
            workload_dir / (name if name.endswith(".json") else f"{name}.json")
            for name in names
        ]
    else:
        files = sorted(workload_dir.glob("w*.json"))

    workloads = []
    for file_path in files:
        if file_path.name == "schema.json":
            continue
        with file_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if "workload" not in payload:
            payload = {"workload": payload}
        workloads.append(payload)

    if not workloads:
        raise RuntimeError(f"No workload JSON files found in {workload_dir}")
    return workloads


WORKLOADS = _load_workloads()


class MCPStressTestUser(HttpUser):
    wait_time = between(
        float(os.getenv("LOCUST_WAIT_MIN", "0.1")),
        float(os.getenv("LOCUST_WAIT_MAX", "0.5")),
    )

    @task
    def run_workload(self):
        payload = random.choice(WORKLOADS)
        workload_name = payload["workload"]["name"]
        with self.client.post(
            "/run",
            json=payload,
            name=f"/run/{workload_name}",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status: {response.status_code}, Body: {response.text[:500]}")
