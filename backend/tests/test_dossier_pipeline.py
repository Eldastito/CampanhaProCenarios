"""Fase 3b PRD v2 — testes do pipeline e endpoints do Dossiê.

Sem chave LLM (configuração padrão dos testes), o orquestrador roda
o pipeline com skeletons vazios e marca status='ready' + confidence='low'.
Isso valida o graceful fallback. Testes específicos validam:

- POST /dossiers cria + dispatcha worker (eager) → dossiê fica ready.
- GET /dossiers lista com sumário.
- GET /dossiers/{id} traz detalhe completo.
- POST /dossiers/{id}/refresh re-roda e atualiza last_refreshed_at.
- DELETE /dossiers/{id} apaga.
- POST /dossiers/{id}/social-snapshots aceita entrada manual
  (caminho oficial para adversários sem APIs pagas).
- Mapper Fase 2 deriva digital_sentiment e media_coverage quando
  existe dossiê 'own' pronto com snapshots e recent_news.
- Audit log dossier.queued + dossier.generated.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.models.dossier import CandidateDossier, DossierSocialSnapshot
from app.models.political import PoliticalAuditLog


def _create_project(client, headers, *, campaign_id: str = "cmp_dossier") -> str:
    payload = {
        "organization_id": "org_demo_001",
        "campaign_id": campaign_id,
        "name": "Projeto Dossiê",
        "election_year": 2026,
        "office": "Prefeito",
        "candidate_name": "Maria",
        "parties": ["PT"],
        "known_opponents": [],
    }
    resp = client.post("/api/v1/political/projects", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Pipeline básico (graceful fallback sem LLM)
# ---------------------------------------------------------------------------


def test_create_dossier_dispatches_worker_and_reaches_ready(
    client, db_session, analyst_auth_headers
):
    project_id = _create_project(client, analyst_auth_headers)
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/dossiers",
        json={
            "candidate_name": "João Adversário",
            "candidate_type": "opponent",
            "office": "Prefeito",
            "party": "ADV",
        },
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    dossier_id = body["dossier_id"]

    # Worker rodou eager → status final deve ser ready.
    fresh = db_session.execute(
        select(CandidateDossier).filter_by(id=dossier_id)
    ).scalar_one()
    assert fresh.status == "ready"
    assert fresh.confidence_level == "low"  # skeletons sem dado real
    assert fresh.last_refreshed_at is not None
    assert fresh.generated_by_ai is True


def test_dossier_list_and_detail_endpoints(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_list")
    client.post(
        f"/api/v1/political/projects/{project_id}/dossiers",
        json={
            "candidate_name": "Maria 13",
            "candidate_type": "own",
            "office": "Prefeito",
            "party": "PT",
        },
        headers=analyst_auth_headers,
    )

    listing = client.get(
        f"/api/v1/political/projects/{project_id}/dossiers",
        headers=analyst_auth_headers,
    )
    assert listing.status_code == 200
    items = listing.json()
    assert len(items) == 1
    assert items[0]["candidate_name"] == "Maria 13"

    dossier_id = items[0]["id"]
    detail = client.get(
        f"/api/v1/political/projects/{project_id}/dossiers/{dossier_id}",
        headers=analyst_auth_headers,
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["candidate_type"] == "own"
    assert body["status"] == "ready"
    assert isinstance(body["sources"], list)
    assert isinstance(body["swot"], dict)


def test_refresh_dossier_reruns_pipeline(client, db_session, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_refresh")
    create = client.post(
        f"/api/v1/political/projects/{project_id}/dossiers",
        json={
            "candidate_name": "Maria",
            "candidate_type": "own",
            "office": "Prefeito",
        },
        headers=analyst_auth_headers,
    )
    dossier_id = create.json()["dossier_id"]
    fresh = db_session.execute(
        select(CandidateDossier).filter_by(id=dossier_id)
    ).scalar_one()
    first_refresh = fresh.last_refreshed_at
    assert first_refresh is not None

    refresh = client.post(
        f"/api/v1/political/projects/{project_id}/dossiers/{dossier_id}/refresh",
        headers=analyst_auth_headers,
    )
    assert refresh.status_code == 202

    db_session.expire_all()
    after = db_session.execute(
        select(CandidateDossier).filter_by(id=dossier_id)
    ).scalar_one()
    assert after.status == "ready"
    assert after.last_refreshed_at is not None
    assert after.last_refreshed_at >= first_refresh


def test_delete_dossier(client, db_session, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_del")
    create = client.post(
        f"/api/v1/political/projects/{project_id}/dossiers",
        json={
            "candidate_name": "Adversário",
            "candidate_type": "opponent",
            "office": "Prefeito",
        },
        headers=analyst_auth_headers,
    )
    dossier_id = create.json()["dossier_id"]
    resp = client.delete(
        f"/api/v1/political/projects/{project_id}/dossiers/{dossier_id}",
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 204

    rows = db_session.execute(
        select(CandidateDossier).filter_by(id=dossier_id)
    ).scalars().all()
    assert rows == []


def test_audit_log_records_queued_and_generated(
    client, db_session, analyst_auth_headers
):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_audit")
    client.post(
        f"/api/v1/political/projects/{project_id}/dossiers",
        json={
            "candidate_name": "Adv",
            "candidate_type": "opponent",
            "office": "Prefeito",
        },
        headers=analyst_auth_headers,
    )
    logs = db_session.execute(
        select(PoliticalAuditLog).filter(
            PoliticalAuditLog.action.in_(["dossier.queued", "dossier.generated"])
        )
    ).scalars().all()
    actions = {log.action for log in logs}
    assert "dossier.queued" in actions
    assert "dossier.generated" in actions


# ---------------------------------------------------------------------------
# Social snapshots manuais
# ---------------------------------------------------------------------------


def test_manual_social_snapshot_for_opponent(client, db_session, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_social")
    create = client.post(
        f"/api/v1/political/projects/{project_id}/dossiers",
        json={
            "candidate_name": "Adversário X",
            "candidate_type": "opponent",
            "office": "Prefeito",
        },
        headers=analyst_auth_headers,
    )
    dossier_id = create.json()["dossier_id"]

    resp = client.post(
        f"/api/v1/political/projects/{project_id}/dossiers/{dossier_id}/social-snapshots",
        json={
            "platform": "twitter",
            "handle": "@adversariox",
            "followers": 50000,
            "posts_last_30d": 80,
            "engagement_rate": 1.4,
        },
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["source"] == "manual"
    assert body["platform"] == "twitter"
    assert body["followers"] == 50000

    rows = db_session.execute(
        select(DossierSocialSnapshot).filter_by(dossier_id=dossier_id)
    ).scalars().all()
    assert len(rows) == 1

    listing = client.get(
        f"/api/v1/political/projects/{project_id}/dossiers/{dossier_id}/social-snapshots",
        headers=analyst_auth_headers,
    )
    assert listing.status_code == 200
    assert len(listing.json()) == 1


# ---------------------------------------------------------------------------
# Integração com mapper Fase 2 — digital_sentiment + media_coverage
# ---------------------------------------------------------------------------


def test_mapper_uses_own_dossier_to_fill_digital_sentiment_and_media_coverage(
    client, db_session, analyst_auth_headers
):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_mapper_int")

    # Cria dossiê 'own' (worker o leva a ready em eager) e injeta dados.
    create = client.post(
        f"/api/v1/political/projects/{project_id}/dossiers",
        json={
            "candidate_name": "Maria",
            "candidate_type": "own",
            "office": "Prefeito",
        },
        headers=analyst_auth_headers,
    )
    dossier_id = create.json()["dossier_id"]

    dossier = db_session.execute(
        select(CandidateDossier).filter_by(id=dossier_id)
    ).scalar_one()
    # Injeta diretamente recent_news com sentimento positivo recente.
    dossier.recent_news = [
        {"published_at": datetime.now(timezone.utc).isoformat(), "sentiment": "positive"},
        {"published_at": datetime.now(timezone.utc).isoformat(), "sentiment": "neutral"},
    ]
    db_session.add(dossier)
    # Adiciona snapshot social positivo.
    db_session.add(
        DossierSocialSnapshot(
            id="ssn_1",
            dossier_id=dossier_id,
            platform="instagram",
            handle="@maria",
            sentiment_distribution={"positive": 70, "neutral": 20, "negative": 10},
            source="manual",
        )
    )
    db_session.commit()

    # Agora envia snapshot v1 — o mapper deve enxergar o dossiê e
    # preencher digital_sentiment + media_coverage.
    import uuid

    from tests.conftest import campanhapro_secret_headers

    payload = {
        "schemaVersion": "campanhapro.snapshot.v1",
        "snapshotId": str(uuid.uuid4()),
        "campaignId": "cmp_mapper_int",
        "organizationId": "org_demo_001",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "campaign": {"details": {"nomeUrna": "Maria 13", "office": "Prefeito"}},
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
        "privacyOptions": {},
        "metrics": {},
    }
    resp = client.post(
        "/api/v1/campanhapro/ingest/snapshots",
        json=payload,
        headers=campanhapro_secret_headers(),
    )
    assert resp.status_code == 202

    factors_resp = client.get(
        f"/api/v1/political/projects/{project_id}/latest-factors",
        headers=analyst_auth_headers,
    )
    assert factors_resp.status_code == 200, factors_resp.text
    factors = factors_resp.json()["factors"]
    assert "digital_sentiment" in factors
    # (positive=70, negative=10, total=100) → 50 + 50*60/100 = 80
    assert factors["digital_sentiment"] == 80.0
    assert "media_coverage" in factors
    # 1 positivo de 2 itens recentes = 50%
    assert factors["media_coverage"] == 50.0
