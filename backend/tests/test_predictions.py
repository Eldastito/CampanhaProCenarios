"""Tests for prediction endpoints: /predictions/acceptance and /predictions/evasion-risk."""

import uuid

from tests.conftest import api_key_headers, forge_secret_headers

_FULL_FACTORS = {
    "training": 80,
    "digital_maturity": 70,
    "teacher_adoption": 85,
    "infrastructure": 75,
    "institutional_support": 90,
    "engagement": 65,
}

_LOW_FACTORS = {
    "training": 20,
    "digital_maturity": 15,
    "teacher_adoption": 10,
    "infrastructure": 25,
    "institutional_support": 18,
    "engagement": 12,
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
# Acceptance
# ---------------------------------------------------------------------------


def test_acceptance_with_full_factors_returns_high_confidence(client):
    resp = client.post(
        "/api/v1/predictions/acceptance",
        json=_acceptance_payload(_FULL_FACTORS),
        headers=api_key_headers(),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["prediction_type"] == "acceptance"
    assert 0.0 <= body["value"] <= 1.0
    assert body["confidence"] > 0.9  # all 5 relevant factors supplied → high confidence
    assert len(body["explanation"]) >= 1


def test_acceptance_with_high_factors_returns_high_value(client):
    resp = client.post(
        "/api/v1/predictions/acceptance",
        json=_acceptance_payload({"training": 95, "teacher_adoption": 95, "institutional_support": 95, "digital_maturity": 90, "engagement": 88}),
        headers=api_key_headers(),
    )
    body = resp.json()
    assert body["value"] >= 0.80, f"Expected high acceptance, got {body['value']}"


def test_acceptance_with_low_factors_returns_low_value(client):
    resp = client.post(
        "/api/v1/predictions/acceptance",
        json=_acceptance_payload(_LOW_FACTORS),
        headers=api_key_headers(),
    )
    body = resp.json()
    assert body["value"] < 0.40, f"Expected low acceptance, got {body['value']}"


def test_acceptance_without_factors_returns_low_confidence(client):
    resp = client.post(
        "/api/v1/predictions/acceptance",
        json=_acceptance_payload(None),
        headers=api_key_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["confidence"] <= 0.10
    assert any("no factor" in line.lower() or "no forge" in line.lower() for line in body["explanation"])


def test_acceptance_uses_forge_snapshot_when_no_factors_provided(client):
    """After ingesting a snapshot, prediction without factors should use it."""
    # Ingest a snapshot with known factors
    client.post(
        "/api/v1/forge/ingest/snapshots",
        json={
            "request_id": str(uuid.uuid4()),
            "source_system": "forge",
            "organization_id": "org_demo_001",
            "snapshot_type": "adoption_metrics",
            "reference_date": "2026-03-31T00:00:00",
            "payload_version": "1.0",
            "payload": {
                "factors": {
                    "training": 90,
                    "digital_maturity": 88,
                    "teacher_adoption": 92,
                    "institutional_support": 85,
                    "engagement": 80,
                }
            },
        },
        headers=forge_secret_headers(),
    )

    resp = client.post(
        "/api/v1/predictions/acceptance",
        json=_acceptance_payload(None),
        headers=api_key_headers(),
    )
    body = resp.json()
    # Should now have higher confidence since FORGE snapshot was found
    assert body["confidence"] > 0.10, f"Expected higher confidence from snapshot, got {body['confidence']}"
    assert body["value"] >= 0.80


def test_acceptance_returns_401_without_api_key(client):
    resp = client.post("/api/v1/predictions/acceptance", json=_acceptance_payload(_FULL_FACTORS))
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Evasion risk
# ---------------------------------------------------------------------------


def test_evasion_risk_with_full_factors_returns_high_confidence(client):
    resp = client.post(
        "/api/v1/predictions/evasion-risk",
        json=_evasion_payload(_FULL_FACTORS),
        headers=api_key_headers(),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["prediction_type"] == "evasion-risk"
    assert 0.0 <= body["value"] <= 1.0
    assert body["confidence"] >= 1.0  # all 4 relevant factors supplied → max confidence


def test_evasion_high_engagement_returns_low_risk(client):
    resp = client.post(
        "/api/v1/predictions/evasion-risk",
        json=_evasion_payload({"engagement": 95, "infrastructure": 90, "institutional_support": 88, "teacher_adoption": 85}),
        headers=api_key_headers(),
    )
    body = resp.json()
    assert body["value"] < 0.20, f"Expected low evasion risk, got {body['value']}"


def test_evasion_low_engagement_returns_high_risk(client):
    resp = client.post(
        "/api/v1/predictions/evasion-risk",
        json=_evasion_payload({"engagement": 10, "infrastructure": 15, "institutional_support": 12, "teacher_adoption": 8}),
        headers=api_key_headers(),
    )
    body = resp.json()
    assert body["value"] >= 0.80, f"Expected high evasion risk, got {body['value']}"


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
    resp = client.post("/api/v1/predictions/evasion-risk", json=_evasion_payload(_FULL_FACTORS))
    assert resp.status_code == 401
