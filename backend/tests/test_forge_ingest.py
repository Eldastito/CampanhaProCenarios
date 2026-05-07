"""Tests for FORGE ingest endpoints: /forge/ingest/events and /forge/ingest/snapshots."""

import uuid

from tests.conftest import forge_secret_headers


def _event_payload(org_id: str = "org_demo_001", request_id: str | None = None) -> dict:
    return {
        "request_id": request_id or str(uuid.uuid4()),
        "source_system": "forge",
        "organization_id": org_id,
        "event_type": "student_enrollment",
        "occurred_at": "2026-04-01T10:00:00",
        "payload_version": "1.0",
        "payload": {"students_enrolled": 150, "school_id": "school_01"},
    }


def _snapshot_payload(org_id: str = "org_demo_001", request_id: str | None = None) -> dict:
    return {
        "request_id": request_id or str(uuid.uuid4()),
        "source_system": "forge",
        "organization_id": org_id,
        "snapshot_type": "adoption_metrics",
        "reference_date": "2026-03-31T00:00:00",
        "payload_version": "1.0",
        "payload": {
            "factors": {
                "training": 72,
                "digital_maturity": 65,
                "teacher_adoption": 78,
                "infrastructure": 80,
                "institutional_support": 70,
                "engagement": 68,
            }
        },
    }


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def test_ingest_event_persists_and_returns_202(client):
    resp = client.post(
        "/api/v1/forge/ingest/events",
        json=_event_payload(),
        headers=forge_secret_headers(),
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "accepted"
    assert "persisted" in body["detail"].lower()


def test_ingest_event_duplicate_request_id_is_idempotent(client):
    rid = str(uuid.uuid4())
    payload = _event_payload(request_id=rid)

    resp1 = client.post("/api/v1/forge/ingest/events", json=payload, headers=forge_secret_headers())
    resp2 = client.post("/api/v1/forge/ingest/events", json=payload, headers=forge_secret_headers())

    assert resp1.status_code == 202
    assert resp2.status_code == 202
    assert "duplicate" in resp2.json()["detail"].lower()


def test_ingest_event_returns_401_without_secret(client):
    resp = client.post("/api/v1/forge/ingest/events", json=_event_payload())
    assert resp.status_code == 401


def test_ingest_event_returns_401_with_wrong_secret(client):
    resp = client.post(
        "/api/v1/forge/ingest/events",
        json=_event_payload(),
        headers={"x-forge-secret": "wrong-secret"},
    )
    assert resp.status_code == 401


def test_ingest_event_rejects_missing_required_fields(client):
    resp = client.post(
        "/api/v1/forge/ingest/events",
        json={"source_system": "forge"},
        headers=forge_secret_headers(),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------


def test_ingest_snapshot_persists_and_returns_202(client):
    resp = client.post(
        "/api/v1/forge/ingest/snapshots",
        json=_snapshot_payload(),
        headers=forge_secret_headers(),
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "accepted"
    assert "persisted" in body["detail"].lower()


def test_ingest_snapshot_duplicate_request_id_is_idempotent(client):
    rid = str(uuid.uuid4())
    payload = _snapshot_payload(request_id=rid)

    resp1 = client.post("/api/v1/forge/ingest/snapshots", json=payload, headers=forge_secret_headers())
    resp2 = client.post("/api/v1/forge/ingest/snapshots", json=payload, headers=forge_secret_headers())

    assert resp1.status_code == 202
    assert resp2.status_code == 202
    assert "duplicate" in resp2.json()["detail"].lower()


def test_ingest_snapshot_returns_401_without_secret(client):
    resp = client.post("/api/v1/forge/ingest/snapshots", json=_snapshot_payload())
    assert resp.status_code == 401


def test_ingest_snapshot_rejects_missing_required_fields(client):
    resp = client.post(
        "/api/v1/forge/ingest/snapshots",
        json={"organization_id": "org_demo_001"},
        headers=forge_secret_headers(),
    )
    assert resp.status_code == 422
