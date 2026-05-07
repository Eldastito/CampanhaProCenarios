from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.deps.auth import require_scenario_access
from app.main import app
import app.api.v1.endpoints.scenarios as scenarios_endpoint


class FakeScenarioService:
    def __init__(self, db) -> None:
        self.db = db

    def create_scenario(self, **kwargs):
        class ScenarioObj:
            id = "scenario-001"
            organization_id = kwargs["organization_id"]
            name = kwargs["name"]
            description = kwargs["description"]
            status = "draft"

        return ScenarioObj()

    def get_run_execution_plan(self, scenario_id: str, *, force_recalculate: bool, run_label: str | None):
        if run_label:
            return {
                "should_execute": True,
                "execution_mode": "executed_new_run",
                "reason": "explicit_run_label",
                "result_status": "stale",
            }

        if force_recalculate:
            return {
                "should_execute": True,
                "execution_mode": "executed_new_run",
                "reason": "force_recalculate_true",
                "result_status": "fresh",
            }

        return {
            "should_execute": False,
            "execution_mode": "reused_current_result",
            "reason": "fresh_result_reused",
            "result_status": "fresh",
        }

    def queue_run(self, scenario_id: str, run_label: str | None = None):
        class RunObj:
            id = "run-new-001"
            status = "queued"
            label = run_label

        return RunObj()

    def execute_run(self, run_id: str):
        class RunObj:
            id = run_id
            status = "completed"

        return RunObj()

    def get_results_view(self, scenario_id: str):
        return {
            "contract_version": "v2",
            "scenario_id": scenario_id,
            "legacy_status": "completed",
            "scenario_status": "completed",
            "run_status": "completed",
            "result_status": "fresh",
            "result_meta": {
                "is_stale": False,
                "stale_at": None,
                "stale_reason": None,
                "last_refreshed_at": "2026-04-08T00:01:55.883584",
                "result_source_run_id": "run-success-001",
                "latest_run_id": "run-success-001",
                "latest_run_label": None,
                "latest_run_error_detail": None,
                "latest_run_started_at": "2026-04-08T00:01:55.883584",
                "latest_run_finished_at": "2026-04-08T00:01:55.883584",
            },
            "result": {
                "baseline_score": 39.05,
                "alternative_score": 71.4,
                "delta": 32.35,
                "detail": "cached result",
            },
        }

    def list_runs_view(self, scenario_id: str, limit: int = 50):
        return {
            "contract_version": "v2",
            "scenario_id": scenario_id,
            "scenario_status": "completed",
            "current_result_status": "fresh",
            "current_result_source_run_id": "run-success-001",
            "run_count": 1,
            "runs": [
                {
                    "run_id": "run-success-001",
                    "status": "completed",
                    "label": None,
                    "error_detail": None,
                    "created_at": "2026-04-08T00:01:55.883584",
                    "started_at": "2026-04-08T00:01:55.883584",
                    "finished_at": "2026-04-08T00:01:55.883584",
                    "is_latest_attempt": True,
                    "is_current_result_source": True,
                }
            ],
        }


def override_get_db():
    yield None


def override_api_key():
    return "LOCAL_DEV_12345"


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[require_scenario_access] = override_api_key


def test_create_scenario_returns_contract_v2(monkeypatch) -> None:
    monkeypatch.setattr(scenarios_endpoint, "ScenarioService", FakeScenarioService)
    client = TestClient(app)

    response = client.post(
        "/api/v1/scenarios",
        headers={"x-api-key": "LOCAL_DEV_12345"},
        json={
            "organization_id": "org_demo_001",
            "name": "Scenario API Test",
            "description": "create test",
            "baseline_inputs": {},
            "alternative_inputs": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_version"] == "v2"
    assert payload["scenario_id"] == "scenario-001"
    assert payload["status"] == "draft"


def test_run_scenario_reuses_fresh_result(monkeypatch) -> None:
    monkeypatch.setattr(scenarios_endpoint, "ScenarioService", FakeScenarioService)
    client = TestClient(app)

    response = client.post(
        "/api/v1/scenarios/scenario-001/run",
        headers={"x-api-key": "LOCAL_DEV_12345"},
        json={"force_recalculate": False},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_version"] == "v2"
    assert payload["execution_mode"] == "reused_current_result"
    assert payload["run_created"] is False
    assert payload["run_status"] is None
    assert payload["force_recalculate_received"] is False
    assert payload["force_recalculate_applied"] is False
    assert payload["run_decision_reason"] == "fresh_result_reused"


def test_run_scenario_force_recalculate_executes_new_run(monkeypatch) -> None:
    monkeypatch.setattr(scenarios_endpoint, "ScenarioService", FakeScenarioService)
    client = TestClient(app)

    response = client.post(
        "/api/v1/scenarios/scenario-001/run",
        headers={"x-api-key": "LOCAL_DEV_12345"},
        json={"force_recalculate": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_version"] == "v2"
    assert payload["execution_mode"] == "executed_new_run"
    assert payload["run_created"] is True
    assert payload["run_status"] == "completed"
    assert payload["force_recalculate_received"] is True
    assert payload["force_recalculate_applied"] is True
    assert payload["run_decision_reason"] == "force_recalculate_true"


def test_results_endpoint_returns_v2_payload(monkeypatch) -> None:
    monkeypatch.setattr(scenarios_endpoint, "ScenarioService", FakeScenarioService)
    client = TestClient(app)

    response = client.get(
        "/api/v1/scenarios/scenario-001/results",
        headers={"x-api-key": "LOCAL_DEV_12345"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_version"] == "v2"
    assert payload["scenario_status"] == "completed"
    assert payload["result_status"] == "fresh"


def test_runs_endpoint_returns_history(monkeypatch) -> None:
    monkeypatch.setattr(scenarios_endpoint, "ScenarioService", FakeScenarioService)
    client = TestClient(app)

    response = client.get(
        "/api/v1/scenarios/scenario-001/runs?limit=50",
        headers={"x-api-key": "LOCAL_DEV_12345"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_version"] == "v2"
    assert payload["run_count"] == 1
    assert payload["runs"][0]["run_id"] == "run-success-001"
    assert payload["runs"][0]["is_current_result_source"] is True