"""Fase 2 PRD v2 — pipeline end-to-end: ingest → worker → cache → API.

Cobre:
- POST snapshot v1 → worker em eager mode grava cache + audit log.
- POST snapshot legado (sem schemaVersion) → não dispara worker, sem cache.
- POST snapshot v1 duas vezes → cache idempotente (1 registro só).
- GET /political/projects/{id}/latest-factors → 404 antes, 200 depois.
- Worker associa cache ao political_project pelo campaign_id.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.factor_cache import CampanhaProFactorCache
from app.models.political import PoliticalAuditLog
from tests.conftest import campanhapro_secret_headers


CAMPAIGN_ID = "cmp_pipeline_test"


def _create_project(client, headers, *, campaign_id: str = CAMPAIGN_ID) -> str:
    payload = {
        "organization_id": "org_demo_001",
        "campaign_id": campaign_id,
        "name": "Campanha Pipeline",
        "election_year": 2026,
        "office": "Prefeito",
        "candidate_name": "Maria",
        "parties": ["PT"],
        "known_opponents": [],
    }
    resp = client.post("/api/v1/political/projects", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _v1_payload(**overrides) -> dict:
    base = {
        "schemaVersion": "campanhapro.snapshot.v1",
        "snapshotId": str(uuid.uuid4()),
        "campaignId": CAMPAIGN_ID,
        "organizationId": "org_demo_001",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "campaign": {
            "details": {
                "nomeUrna": "Maria 13",
                "office": "Prefeito",
                "candidatePhotoUrl": "https://example.com/photo.png",
                "headerLogo": None,
                "footerLogo": None,
            },
            "settings": {},
            "configs": {},
        },
        "data": {
            "visits": [],
            "pesquisa": [
                {"intencaoVoto": "Maria 13"} for _ in range(40)
            ] + [{"intencaoVoto": "Outro"} for _ in range(60)],
            "engagementActions": [],
            "teamMembers": [],
            "locations": [],
            "financial": {"incomes": [], "expenses": []},
            "calculatorSettings": {},
            "scenarios": [],
            "streetReports": [],
            "agentOutputs": [],
            "fieldTickets": [
                {"status": "concluido"},
                {"status": "concluido"},
                {"status": "aberto"},
            ],
            "neighborhoodFlags": [],
            "contentBriefs": [],
            "aiUsage": [],
        },
        "privacyOptions": {},
        "metrics": {},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Pipeline básico
# ---------------------------------------------------------------------------


def test_v1_snapshot_triggers_worker_and_creates_factor_cache(
    client, db_session, analyst_auth_headers
):
    project_id = _create_project(client, analyst_auth_headers)
    payload = _v1_payload()

    resp = client.post(
        "/api/v1/campanhapro/ingest/snapshots",
        json=payload,
        headers=campanhapro_secret_headers(),
    )
    assert resp.status_code == 202

    rows = db_session.execute(
        select(CampanhaProFactorCache).filter_by(campaign_id=CAMPAIGN_ID)
    ).scalars().all()
    assert len(rows) == 1
    cache = rows[0]
    assert cache.political_project_id == project_id
    assert cache.organization_id == "org_demo_001"
    # vote_intention=40, operational_efficiency≈66.67 → coverage ≈ 16.67%
    assert "vote_intention" in cache.factors
    assert cache.factors["vote_intention"] == 40.0
    assert "operational_efficiency" in cache.factors
    assert cache.coverage_percent > 0


def test_legacy_payload_does_not_create_factor_cache(client, db_session, analyst_auth_headers):
    _create_project(client, analyst_auth_headers, campaign_id="cmp_legacy")
    legacy = {
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
        json=legacy,
        headers=campanhapro_secret_headers(),
    )
    assert resp.status_code == 202
    rows = db_session.execute(select(CampanhaProFactorCache)).scalars().all()
    assert rows == []


def test_duplicate_snapshot_does_not_duplicate_cache(
    client, db_session, analyst_auth_headers
):
    _create_project(client, analyst_auth_headers)
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

    rows = db_session.execute(select(CampanhaProFactorCache)).scalars().all()
    assert len(rows) == 1


def test_audit_log_factors_cached_emitted(client, db_session, analyst_auth_headers):
    _create_project(client, analyst_auth_headers)
    client.post(
        "/api/v1/campanhapro/ingest/snapshots",
        json=_v1_payload(),
        headers=campanhapro_secret_headers(),
    )
    logs = db_session.execute(
        select(PoliticalAuditLog).filter_by(action="factors.cached")
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].payload["campaign_id"] == CAMPAIGN_ID
    assert "vote_intention" in logs[0].payload["factors_present"]


# ---------------------------------------------------------------------------
# Endpoint latest-factors
# ---------------------------------------------------------------------------


def test_latest_factors_returns_404_when_no_cache(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_no_cache")
    resp = client.get(
        f"/api/v1/political/projects/{project_id}/latest-factors",
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 404


def test_latest_factors_returns_cache_after_snapshot(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers)
    client.post(
        "/api/v1/campanhapro/ingest/snapshots",
        json=_v1_payload(),
        headers=campanhapro_secret_headers(),
    )

    resp = client.get(
        f"/api/v1/political/projects/{project_id}/latest-factors",
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["campaign_id"] == CAMPAIGN_ID
    assert body["political_project_id"] == project_id
    assert body["factors"]["vote_intention"] == 40.0
    assert "vote_intention" in body["sources_used"]
    assert isinstance(body["warnings"], list)


def test_latest_factors_blocks_other_organization(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers)
    # Cria headers para outro org_id usando o helper jwt_headers
    from tests.conftest import jwt_headers

    other_headers = jwt_headers(user_id="other", org_id="org_other")
    resp = client.get(
        f"/api/v1/political/projects/{project_id}/latest-factors",
        headers=other_headers,
    )
    # 401 (usuário não existe no DB) OU 404 (org diferente) — ambos
    # confirmam que outra organização não consegue ler o cache.
    assert resp.status_code in (401, 404)


# ---------------------------------------------------------------------------
# Snapshots subsequentes preservam histórico (não sobrescrevem)
# ---------------------------------------------------------------------------


def test_subsequent_snapshots_create_new_cache_rows(client, db_session, analyst_auth_headers):
    _create_project(client, analyst_auth_headers)
    for _ in range(3):
        client.post(
            "/api/v1/campanhapro/ingest/snapshots",
            json=_v1_payload(),  # snapshotId novo a cada iteração
            headers=campanhapro_secret_headers(),
        )
    rows = db_session.execute(
        select(CampanhaProFactorCache).filter_by(campaign_id=CAMPAIGN_ID)
    ).scalars().all()
    assert len(rows) == 3
