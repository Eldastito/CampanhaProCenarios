"""Testes da Fase 2 — ingestão de evidências políticas.

Cobre:
- POST manual (texto colado, link)
- Upload de arquivo (TXT)
- Dedup por content_hash
- Classificação de confiabilidade (oficial vs social)
- Alerta de compliance para fonte fraca
- Listagem
"""

import io

from sqlalchemy import select

from app.models.political import PoliticalComplianceAlert
from app.services.source_verification_service import classify_reliability


# ---------------------------------------------------------------------------
# Reliability classification (unit, sem DB)
# ---------------------------------------------------------------------------


def test_classify_reliability_official_domain():
    cls = classify_reliability(source_type="link", source_url="https://www.tse.jus.br/eleicoes/2026")
    assert cls.level == "official"


def test_classify_reliability_press_domain():
    cls = classify_reliability(source_type="link", source_url="https://g1.globo.com/politica/x")
    assert cls.level == "press"


def test_classify_reliability_social_domain():
    cls = classify_reliability(source_type="link", source_url="https://twitter.com/foo/status/1")
    assert cls.level == "social"


def test_classify_reliability_internal_for_manual():
    cls = classify_reliability(source_type="manual")
    assert cls.level == "internal"


def test_classify_reliability_unverified_default():
    cls = classify_reliability(source_type="md", source_url=None)
    assert cls.level == "unverified"


def test_classify_reliability_registered_poll_text_hint():
    sample = "Pesquisa registrada no TSE-12345/2026 — Instituto X, amostra 1200."
    cls = classify_reliability(source_type="md", raw_text_sample=sample)
    assert cls.level == "registered_poll"


# ---------------------------------------------------------------------------
# Helper local: cria projeto usando o usuário analyst registrado
# ---------------------------------------------------------------------------


def _create_project(client, headers, *, organization_id: str = "org_demo_001") -> str:
    payload = {
        "organization_id": organization_id,
        "name": "Campanha Teste",
        "election_year": 2026,
        "office": "Prefeito",
        "candidate_name": "Fulano",
        "parties": ["Partido X"],
        "known_opponents": [],
    }
    resp = client.post("/api/v1/political/projects", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Endpoints manuais (sem upload binário)
# ---------------------------------------------------------------------------


def test_manual_evidence_creation_official_url(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers)

    body = {
        "title": "Calendário Eleitoral 2026",
        "source_type": "link",
        "source_url": "https://www.tse.jus.br/eleicoes/2026/calendario",
        "source_name": "TSE",
    }
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/evidence/manual",
        json=body,
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["source_type"] == "link"
    assert data["reliability_level"] == "official"
    assert data["processing_status"] == "ready"
    assert data["content_hash"]


def test_manual_evidence_dedup_by_hash(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers)

    body = {
        "title": "Documento interno",
        "source_type": "manual",
        "raw_text": "Estratégia de campanha — versão 1",
    }
    r1 = client.post(
        f"/api/v1/political/projects/{project_id}/evidence/manual",
        json=body,
        headers=analyst_auth_headers,
    )
    r2 = client.post(
        f"/api/v1/political/projects/{project_id}/evidence/manual",
        json=body,
        headers=analyst_auth_headers,
    )
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]  # dedup


def test_manual_evidence_emits_weak_source_alert(client, db_session, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers)

    body = {
        "title": "Tweet sobre adversário",
        "source_type": "link",
        "source_url": "https://twitter.com/alguem/status/123",
    }
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/evidence/manual",
        json=body,
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["reliability_level"] == "social"

    alerts = db_session.execute(
        select(PoliticalComplianceAlert).filter_by(project_id=project_id)
    ).scalars().all()
    assert any(a.alert_type == "weak_source" for a in alerts)


# ---------------------------------------------------------------------------
# Upload de arquivo (multipart)
# ---------------------------------------------------------------------------


def test_upload_txt_evidence(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers)

    file_bytes = b"Pauta principal: educacao, seguranca, saude."
    files = {"file": ("plano.txt", io.BytesIO(file_bytes), "text/plain")}
    form = {"title": "Plano de governo"}
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/evidence",
        files=files,
        data=form,
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["source_type"] == "txt"
    assert data["title"] == "Plano de governo"
    assert data["processing_status"] == "ready"


def test_upload_unsupported_filetype_rejected(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers)

    files = {"file": ("foto.png", io.BytesIO(b"fake-png"), "image/png")}
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/evidence",
        files=files,
        data={"title": "Imagem"},
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 415


def test_list_evidence_returns_ingested_records(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers)

    for i in range(3):
        client.post(
            f"/api/v1/political/projects/{project_id}/evidence/manual",
            json={
                "title": f"Doc {i}",
                "source_type": "manual",
                "raw_text": f"conteúdo {i}",
            },
            headers=analyst_auth_headers,
        )

    resp = client.get(
        f"/api/v1/political/projects/{project_id}/evidence",
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 3
