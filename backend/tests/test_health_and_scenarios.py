from tests.conftest import api_key_headers as auth_headers  # noqa: F401


# Fatores eleitorais (Fase 1) — chaves do scenario_catalog "electoral".
def full_payload() -> dict:
    return {
        "organization_id": "org_demo_001",
        "name": "Cenário Eleitoral Demo",
        "description": "Primeiro fluxo vertical testado (domínio eleitoral)",
        "baseline_inputs": {
            "rejection": 30,
            "vote_intention": 60,
            "awareness": 70,
            "territorial_strength": 65,
            "alliances": 60,
            "mobilization": 60,
            "digital_sentiment": 55,
            "local_agenda_fit": 60,
            "reputation_risk": 35,
            "operational_efficiency": 65,
            "media_coverage": 50,
            "declared_funding": 55,
        },
        "alternative_inputs": {
            "rejection": 25,
            "vote_intention": 75,
            "awareness": 80,
            "territorial_strength": 75,
            "alliances": 70,
            "mobilization": 75,
            "digital_sentiment": 70,
            "local_agenda_fit": 75,
            "reputation_risk": 30,
            "operational_efficiency": 75,
            "media_coverage": 65,
            "declared_funding": 65,
        },
    }


def sparse_payload() -> dict:
    return {
        "organization_id": "org_demo_001",
        "name": "Cenário Eleitoral Esparso",
        "description": "Cenário com poucos fatores informados",
        "baseline_inputs": {
            "rejection": 70,
        },
        "alternative_inputs": {
            "rejection": 85,
        },
    }


def test_health_check(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "ok"
    assert payload["service"] == "campanhapro-cenarios-api"


def test_readiness_check(client):
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "ready"
    assert payload["dependencies"]["database"] == "ok"


def test_create_list_and_get_scenario_exposes_enriched_summary(client):
    create_response = client.post(
        "/api/v1/scenarios",
        json=full_payload(),
        headers=auth_headers(),
    )

    assert create_response.status_code == 200
    create_body = create_response.json()

    scenario_id = create_body["scenario_id"]

    list_response = client.get(
        "/api/v1/scenarios",
        headers=auth_headers(),
    )

    assert list_response.status_code == 200
    list_body = list_response.json()

    assert list_body["count"] == 1
    assert len(list_body["items"]) == 1

    item = list_body["items"][0]
    assert item["scenario_id"] == scenario_id
    assert item["organization_id"] == "org_demo_001"
    assert item["baseline_normalized_score"] is not None
    assert item["alternative_normalized_score"] is not None
    assert item["normalized_delta"] is not None
    assert item["baseline_band"] in {
        "critical",
        "attention",
        "progressing",
        "strong",
        "advanced",
    }
    assert item["alternative_band"] in {
        "critical",
        "attention",
        "progressing",
        "strong",
        "advanced",
    }
    assert item["delta_direction"] in {
        "strong_gain",
        "moderate_gain",
        "slight_gain",
        "neutral",
        "negative",
    }
    assert item["confidence_level"] == "high"
    assert item["baseline_coverage_percent"] == 100.0
    assert item["alternative_coverage_percent"] == 100.0

    get_response = client.get(
        f"/api/v1/scenarios/{scenario_id}",
        headers=auth_headers(),
    )

    assert get_response.status_code == 200
    get_body = get_response.json()

    assert get_body["scenario_id"] == scenario_id
    assert get_body["baseline_score"] is not None
    assert get_body["alternative_score"] is not None
    assert get_body["delta"] is not None
    assert get_body["baseline_normalized_score"] == get_body["baseline_score"]
    assert get_body["alternative_normalized_score"] == get_body["alternative_score"]
    assert get_body["confidence_level"] == "high"


def test_sparse_input_returns_coverage_and_normalized_scores(client):
    create_response = client.post(
        "/api/v1/scenarios",
        json=sparse_payload(),
        headers=auth_headers(),
    )

    assert create_response.status_code == 200
    scenario_id = create_response.json()["scenario_id"]

    results_response = client.get(
        f"/api/v1/scenarios/{scenario_id}/results",
        headers=auth_headers(),
    )

    assert results_response.status_code == 200
    body = results_response.json()

    # rejection peso = 0.15; baseline=70 → 10.5; alt=85 → 12.75; delta=2.25
    assert body["result"]["baseline_score"] == 10.5
    assert body["result"]["alternative_score"] == 12.75
    assert round(body["result"]["delta"], 2) == 2.25

    # Normalizado pelo peso fornecido (0.15) → volta à escala 0-100
    assert body["normalized_result"]["baseline_score"] == 70.0
    assert body["normalized_result"]["alternative_score"] == 85.0
    assert body["normalized_result"]["delta"] == 15.0

    # Cobertura por peso: 0.15 / 1.00 = 15%
    assert body["input_quality"]["baseline_coverage_percent"] == 15.0
    assert body["input_quality"]["alternative_coverage_percent"] == 15.0
    # vote_intention é o segundo maior peso e está ausente
    assert "vote_intention" in body["input_quality"]["baseline_missing_factors"]
    assert body["interpretation"]["confidence_level"] == "low"
    # Domínio eleitoral tem 12 fatores
    assert len(body["factor_breakdown"]) == 12
    assert len(body["recommendations"]) >= 1
    assert any(
        "missing factors" in warning.lower()
        for warning in body["interpretation"]["warnings"]
    )


def test_create_scenario_returns_404_when_organization_does_not_exist(client):
    payload = {
        "organization_id": "org_inexistente",
        "name": "Scenario inválido",
        "description": "Deve falhar",
        "baseline_inputs": {},
        "alternative_inputs": {},
    }

    response = client.post(
        "/api/v1/scenarios",
        json=payload,
        headers=auth_headers(),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Organization not found."
