"""Fase 1 do PRD v2 — contrato campanhapro.snapshot.v1.

Cobre:
- Snapshot v1 mínimo válido → 202 + persistido com campaign_id e schema_version.
- Snapshot v1 inválido (sem campaignId) → 422 com apontamento Pydantic.
- Snapshot v1 inválido (snapshotId não-UUID) → 422.
- Idempotência: mesmo snapshotId enviado duas vezes → 1 registro só.
- Compat: payload legado (sem schemaVersion) continua aceito,
  campaign_id fica NULL no banco.
- Headers: ausência do X-CampanhaPro-Secret → 401.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.campanhapro_ingest import CampanhaProSnapshot
from tests.conftest import campanhapro_secret_headers


def _v1_payload(**overrides) -> dict:
    base = {
        "schemaVersion": "campanhapro.snapshot.v1",
        "snapshotId": str(uuid.uuid4()),
        "campaignId": "cmp_pref_recife_2028",
        "organizationId": "org_demo_001",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "campanhapro-web",
        "actor": {"userId": "usr_42", "role": "Admin"},
        "campaign": {
            "details": {
                "nomeUrna": "Maria 13",
                "partido": "PT",
                "office": "Prefeito",
                "municipio": "Recife",
                "uf": "PE",
                "candidatePhotoUrl": None,
                "headerLogo": None,
                "footerLogo": None,
            },
            "settings": {},
            "configs": {},
        },
        "data": {
            "visits": [],
            "pesquisa": [],
            "engagementActions": [],
            "teamMembers": [],
            "locations": [],
            "financial": {"incomes": [], "expenses": []},
            "calculatorSettings": {},
            "scenarios": [],
            "streetReports": [],
            "agentOutputs": [],
            "fieldTickets": [],
            "neighborhoodFlags": [],
            "contentBriefs": [],
            "aiUsage": [],
        },
        "privacyOptions": {
            "includePII": False,
            "anonymizeNames": True,
            "anonymizePhones": True,
            "anonymizeBirthdates": True,
        },
        "metrics": {
            "recordsCount": 0,
            "windowStart": "2027-12-15T00:00:00Z",
            "windowEnd": "2028-03-15T00:00:00Z",
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# v1 happy path
# ---------------------------------------------------------------------------


def test_v1_minimal_valid_snapshot_persists_with_campaign_id(client, db_session):
    payload = _v1_payload()
    resp = client.post(
        "/api/v1/campanhapro/ingest/snapshots",
        json=payload,
        headers=campanhapro_secret_headers(),
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["request_id"] == payload["snapshotId"]
    assert "persisted" in body["detail"].lower()

    rows = db_session.execute(
        select(CampanhaProSnapshot).filter_by(request_id=payload["snapshotId"])
    ).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.campaign_id == "cmp_pref_recife_2028"
    assert row.schema_version == "campanhapro.snapshot.v1"
    assert row.organization_id == "org_demo_001"
    assert row.snapshot_type == "snapshot_v1"


# ---------------------------------------------------------------------------
# v1 validation
# ---------------------------------------------------------------------------


def test_v1_missing_campaign_id_returns_422(client):
    payload = _v1_payload()
    payload.pop("campaignId")
    resp = client.post(
        "/api/v1/campanhapro/ingest/snapshots",
        json=payload,
        headers=campanhapro_secret_headers(),
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert any("campaignId" in str(err) or "campaign_id" in str(err) for err in detail)


def test_v1_missing_snapshot_id_returns_422(client):
    payload = _v1_payload()
    payload.pop("snapshotId")
    resp = client.post(
        "/api/v1/campanhapro/ingest/snapshots",
        json=payload,
        headers=campanhapro_secret_headers(),
    )
    assert resp.status_code == 422


def test_v1_snapshot_id_not_uuid_returns_422(client):
    payload = _v1_payload(snapshotId="not-a-uuid")
    resp = client.post(
        "/api/v1/campanhapro/ingest/snapshots",
        json=payload,
        headers=campanhapro_secret_headers(),
    )
    assert resp.status_code == 422


def test_v1_missing_generated_at_returns_422(client):
    payload = _v1_payload()
    payload.pop("generatedAt")
    resp = client.post(
        "/api/v1/campanhapro/ingest/snapshots",
        json=payload,
        headers=campanhapro_secret_headers(),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Idempotência
# ---------------------------------------------------------------------------


def test_v1_duplicate_snapshot_id_is_idempotent(client, db_session):
    payload = _v1_payload()

    r1 = client.post(
        "/api/v1/campanhapro/ingest/snapshots",
        json=payload,
        headers=campanhapro_secret_headers(),
    )
    r2 = client.post(
        "/api/v1/campanhapro/ingest/snapshots",
        json=payload,
        headers=campanhapro_secret_headers(),
    )

    assert r1.status_code == 202 and r2.status_code == 202
    assert "persisted" in r1.json()["detail"].lower()
    assert "duplicate" in r2.json()["detail"].lower()

    rows = db_session.execute(
        select(CampanhaProSnapshot).filter_by(request_id=payload["snapshotId"])
    ).scalars().all()
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_v1_missing_secret_header_returns_401(client):
    resp = client.post("/api/v1/campanhapro/ingest/snapshots", json=_v1_payload())
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Backward compat — payload legado segue funcionando
# ---------------------------------------------------------------------------


def test_legacy_payload_without_schema_version_still_accepted(client, db_session):
    legacy_payload = {
        "request_id": str(uuid.uuid4()),
        "source_system": "campanhapro",
        "organization_id": "org_demo_001",
        "snapshot_type": "electoral_metrics",
        "reference_date": "2026-03-31T00:00:00",
        "payload_version": "1.0",
        "payload": {"factors": {"vote_intention": 50}},
    }
    resp = client.post(
        "/api/v1/campanhapro/ingest/snapshots",
        json=legacy_payload,
        headers=campanhapro_secret_headers(),
    )
    assert resp.status_code == 202, resp.text

    rows = db_session.execute(
        select(CampanhaProSnapshot).filter_by(request_id=legacy_payload["request_id"])
    ).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.campaign_id is None  # legados não têm campaign_id
    assert row.schema_version is None
    assert row.snapshot_type == "electoral_metrics"
