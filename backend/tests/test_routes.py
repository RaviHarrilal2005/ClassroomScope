"""API endpoints: start a run in the background, poll its status."""
import threading

from helpers import build_client
from orchestrator import build_default_registry
from orchestrator.agents import StubAgent
from orchestrator.stages import COLLECTION, PIPELINE_ORDER, RunStatus, StageStatus


def test_start_run_returns_immediately_then_completes():
    client, runner = build_client()

    response = client.post("/api/v1/runs", json={"trigger_type": "manual"})
    assert response.status_code == 202
    started = response.get_json()
    assert started["status"] == RunStatus.RUNNING
    assert [s["stage_name"] for s in started["stages"]] == list(PIPELINE_ORDER)

    assert runner.wait(timeout=5)
    finished = client.get(f"/api/v1/runs/{started['id']}").get_json()
    assert finished["status"] == RunStatus.COMPLETED
    assert finished["finished_at"] is not None
    assert all(s["status"] == StageStatus.SUCCEEDED for s in finished["stages"])


def test_only_one_run_at_a_time():
    gate = threading.Event()

    def slow_collection(ctx):
        gate.wait(timeout=5)   # hold the run open until the test releases it
        return {"article_ids": [1, 2]}

    registry = build_default_registry()
    registry.register(COLLECTION, StubAgent("slow_collection", output=slow_collection))
    client, runner = build_client(registry)

    first = client.post("/api/v1/runs").get_json()
    second = client.post("/api/v1/runs")
    assert second.status_code == 409
    assert second.get_json()["active_run_id"] == first["id"]

    gate.set()
    assert runner.wait(timeout=5)
    assert client.post("/api/v1/runs").status_code == 202   # allowed once the first finishes
    assert runner.wait(timeout=5)


def test_invalid_trigger_type_is_rejected():
    client, _ = build_client()
    response = client.post("/api/v1/runs", json={"trigger_type": "cron"})
    assert response.status_code == 400


def test_unknown_run_returns_404():
    client, _ = build_client()
    assert client.get("/api/v1/runs/999").status_code == 404
