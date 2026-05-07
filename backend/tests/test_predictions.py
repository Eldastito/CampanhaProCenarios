"""Tests for prediction endpoints: /predictions/acceptance e /predictions/evasion-risk.

Após Fase 1 do replatform político-eleitoral, as previsões usam fatores eleitorais
(rejection, vote_intention, awareness, etc.) em vez dos antigos fatores educacionais.
"""

import uuid

from tests.conftest import api_key_headers, campanhapro_secret_headers

# Conjunto de fatores eleitorais "fortes" (candidatura forte → acceptance alta;
# rejeição/risco baixos → evasion-risk baixo).
_STRONG_CANDIDATE_FACTORS = {
    "vote_intention": 80,
    "awareness": 85,
    "territorial_strength": 80,
    "alliances": 75,
    "mobilization": 80,
    "digital_sentiment": 75,
    "local_agenda_fit": 80,
    "operational_efficiency": 80,
    "media_coverage": 70,
    "declared_funding": 65,
    "rejection": 15,
    "reputation_risk": 20,
}

_WEAK_CANDIDATE_FACTORS = {
    "vote_intention": 15,
    "awareness": 20,
    "territorial_strength": 18,
    "alliances": 25,
    "mobilization": 15,
    "digital_sentiment": 25,
    "local_agenda_fit": 15,
    "operational_efficiency": 20,
    "media_coverage": 10,
    "declared_funding": 12,
    "rejection": 80,
    "reputation_risk": 75,
}


def _acceptance_payload(factors=None) -> dict:
    body = {"organization_id": "org_demo_001", "scope_type": "network", "scope_id": "org_demo_001"}
    if factors is not None:
        body["factors"] = factors
    return body


def _evasion_payload(factors=None) -> dict:
    body = {"organization_id": "org_demo_001", "scope_type": "network", "scope_id": "org_demo_001"}
    if factors is not None:
        body["factors"] = factors
    return body


# ---------------------------------------------------------------------------
# Acceptance (força da candidatura)
# ---------------------------------------------------------------------------


def test_acceptance_with_full_factors_returns_high_confidence(client):
    resp = client.post(
        "/api/v1/predictions/acceptance",
        json=_acceptance_payload(_STRONG_CANDIDATE_FACTORS),
        headers=api_key_headers(),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["prediction_type"] == "acceptance"
    assert 0.0 <= body["value"] <= 1.0
    # Pelo menos os 10 fatores de força foram fornecidos → confidence ≥ 0.78
    assert body["confidence"] >= 0.75
    assert len(body["explanation"]) >= 1


def test_acceptance_with_high_factors_returns_high_value(client):
    resp = client.post(
        "/api/v1/predictions/acceptance",
        json=_acceptance_payload({
            "vote_intention": 95, "awareness": 95, "territorial_strength": 90,
            "alliances": 90, "mobilization": 92, "digital_sentiment": 88,
            "local_agenda_fit": 90, "operational_efficiency": 90,
            "media_coverage": 85, "declared_funding": 80,
        }),
        headers=api_key_headers(),
    )
    body = resp.json()
    assert body["value"] >= 0.80, f"Expected high candidacy strength, got {body['value']}"


def test_acceptance_with_low_factors_returns_low_value(client):
    resp = client.post(
        "/api/v1/predictions/acceptance",
        json=_acceptance_payload(_WEAK_CANDIDATE_FACTORS),
        headers=api_key_headers(),
    )
    body = resp.json()
    assert body["value"] < 0.40, f"Expected weak candidacy, got {body['value']}"


def test_acceptance_without_factors_returns_low_confidence(client):
    resp = client.post(
        "/api/v1/predictions/acceptance",
        json=_acceptance_payload(None),
        headers=api_key_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["confidence"] <= 0.10
    assert any(
        "no factor" in line.lower() or "no campanhapro" in line.lower()
        for line in body["explanation"]
    )


def test_acceptance_uses_campanhapro_snapshot_when_no_factors_provided(client):
    """Após ingestão de snapshot eleitoral, predição sem fatores deve usar o snapshot."""
    client.post(
        "/api/v1/campanhapro/ingest/snapshots",
        json={
            "request_id": str(uuid.uuid4()),
            "source_system": "campanhapro",
            "organization_id": "org_demo_001",
            "snapshot_type": "electoral_metrics",
            "reference_date": "2026-03-31T00:00:00",
            "payload_version": "1.0",
            "payload": {
                "factors": {
                    "vote_intention": 90,
                    "awareness": 88,
                    "territorial_strength": 85,
                    "alliances": 82,
                    "mobilization": 88,
                    "digital_sentiment": 80,
                    "local_agenda_fit": 85,
                    "operational_efficiency": 82,
                    "media_coverage": 75,
                    "declared_funding": 70,
                }
            },
        },
        headers=campanhapro_secret_headers(),
    )

    resp = client.post(
        "/api/v1/predictions/acceptance",
        json=_acceptance_payload(None),
        headers=api_key_headers(),
    )
    body = resp.json()
    assert body["confidence"] > 0.10, f"Expected higher confidence from snapshot, got {body['confidence']}"
    assert body["value"] >= 0.75


def test_acceptance_returns_401_without_api_key(client):
    resp = client.post(
        "/api/v1/predictions/acceptance",
        json=_acceptance_payload(_STRONG_CANDIDATE_FACTORS),
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Evasion risk (risco de rejeição)
# ---------------------------------------------------------------------------


def test_evasion_risk_with_full_factors_returns_high_confidence(client):
    resp = client.post(
        "/api/v1/predictions/evasion-risk",
        json=_evasion_payload(_STRONG_CANDIDATE_FACTORS),
        headers=api_key_headers(),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["prediction_type"] == "evasion-risk"
    assert 0.0 <= body["value"] <= 1.0
    assert body["confidence"] >= 1.0  # todos os 5 fatores de risco fornecidos


def test_evasion_low_rejection_returns_low_risk(client):
    resp = client.post(
        "/api/v1/predictions/evasion-risk",
        json=_evasion_payload({
            "rejection": 10,
            "reputation_risk": 15,
            "digital_sentiment": 90,
            "media_coverage": 85,
            "operational_efficiency": 88,
        }),
        headers=api_key_headers(),
    )
    body = resp.json()
    assert body["value"] < 0.30, f"Expected low rejection risk, got {body['value']}"


def test_evasion_high_rejection_returns_high_risk(client):
    resp = client.post(
        "/api/v1/predictions/evasion-risk",
        json=_evasion_payload({
            "rejection": 90,
            "reputation_risk": 85,
            "digital_sentiment": 15,
            "media_coverage": 20,
            "operational_efficiency": 25,
        }),
        headers=api_key_headers(),
    )
    body = resp.json()
    assert body["value"] >= 0.70, f"Expected high rejection risk, got {body['value']}"


def test_evasion_without_factors_returns_low_confidence(client):
    resp = client.post(
        "/api/v1/predictions/evasion-risk",
        json=_evasion_payload(None),
        headers=api_key_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["confidence"] <= 0.10


def test_evasion_returns_401_without_api_key(client):
    resp = client.post(
        "/api/v1/predictions/evasion-risk",
        json=_evasion_payload(_STRONG_CANDIDATE_FACTORS),
    )
    assert resp.status_code == 401
