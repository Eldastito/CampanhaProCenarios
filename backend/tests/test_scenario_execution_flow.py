from tests.conftest import api_key_headers as auth_headers  # noqa: F401


def create_scenario_payload() -> dict:
    return {
        "organization_id": "org_demo_001",
        "name": "Scenario Execution Integration",
        "description": "Integration test for execution flow",
        "baseline_inputs": {
            "training": 70,
            "digital_maturity": 60,
            "teacher_adoption": 65,
            "infrastructure": 80,
            "institutional_support": 75,
            "engagement": 68,
        },
        "alternative_inputs": {
            "training": 85,
            "digital_maturity": 78,
            "teacher_adoption": 82,
            "infrastructure": 88,
            "institutional_support": 84,
            "engagement": 79,
        },
    }


def create_scenario(client) -> str:
    response = client.post(
        "/api/v1/scenarios",
        json=create_scenario_payload(),
        headers=auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    return body["scenario_id"]


def test_run_endpoint_reuses_fresh_result_without_creating_run(client):
    scenario_id = create_scenario(client)

    response = client.post(
        f"/api/v1/scenarios/{scenario_id}/run",
        json={"force_recalculate": False},
        headers=auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()

    assert body["contract_version"] == "v2"
    assert body["execution_mode"] == "reused_current_result"
    assert body["run_created"] is False
    assert body["run_status"] is None
    assert body["run_decision_reason"] == "fresh_result_reused"
    assert body["results"]["scenario_status"] == "draft"
    assert body["results"]["result_status"] == "fresh"
    assert body["results"]["normalized_result"]["baseline_score"] is not None
    assert body["results"]["normalized_result"]["alternative_score"] is not None
    assert body["results"]["interpretation"]["confidence_level"] == "high"
    assert len(body["results"]["factor_breakdown"]) == 6
    assert len(body["results"]["recommendations"]) >= 1

    runs_response = client.get(
        f"/api/v1/scenarios/{scenario_id}/runs",
        headers=auth_headers(),
    )

    assert runs_response.status_code == 200
    runs_body = runs_response.json()
    assert runs_body["run_count"] == 0
    assert runs_body["runs"] == []


def test_run_endpoint_executes_and_persists_run_history(client):
    scenario_id = create_scenario(client)

    run_response = client.post(
        f"/api/v1/scenarios/{scenario_id}/run",
        json={
            "force_recalculate": False,
            "run_label": "integration_run",
        },
        headers=auth_headers(),
    )

    assert run_response.status_code == 200
    run_body = run_response.json()

    run_id = run_body["run_id"]

    assert run_body["contract_version"] == "v2"
    assert run_body["execution_mode"] == "executed_new_run"
    assert run_body["run_created"] is True
    assert run_body["run_status"] == "completed"
    assert run_body["run_label"] == "integration_run"
    assert run_body["run_decision_reason"] == "explicit_run_label"

    results_response = client.get(
        f"/api/v1/scenarios/{scenario_id}/results",
        headers=auth_headers(),
    )

    assert results_response.status_code == 200
    results_body = results_response.json()

    assert results_body["scenario_status"] == "completed"
    assert results_body["run_status"] == "completed"
    assert results_body["result_status"] == "fresh"
    assert results_body["result_meta"]["result_source_run_id"] == run_id
    assert results_body["result_meta"]["latest_run_id"] == run_id
    assert results_body["result_meta"]["latest_run_label"] == "integration_run"
    assert results_body["normalized_result"]["baseline_score"] is not None
    assert results_body["normalized_result"]["alternative_score"] is not None
    assert results_body["interpretation"]["confidence_level"] == "high"
    assert results_body["interpretation"]["delta_direction"] in {
        "strong_gain",
        "moderate_gain",
        "slight_gain",
        "neutral",
        "negative",
    }
    assert len(results_body["factor_breakdown"]) == 6
    assert len(results_body["recommendations"]) >= 1

    runs_response = client.get(
        f"/api/v1/scenarios/{scenario_id}/runs",
        headers=auth_headers(),
    )

    assert runs_response.status_code == 200
    runs_body = runs_response.json()

    assert runs_body["scenario_status"] == "completed"
    assert runs_body["current_result_status"] == "fresh"
    assert runs_body["current_result_source_run_id"] == run_id
    assert runs_body["run_count"] == 1
    assert runs_body["runs"][0]["run_id"] == run_id
    assert runs_body["runs"][0]["status"] == "completed"
    assert runs_body["runs"][0]["label"] == "integration_run"
    assert runs_body["runs"][0]["is_latest_attempt"] is True
    assert runs_body["runs"][0]["is_current_result_source"] is True