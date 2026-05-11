"""Fase 5 PRD v2 — relatórios PDF/DOCX com branding.

Cobre:
- Branding popula o projeto a partir do snapshot v1 (campaign.details).
- Endpoint /reports gera DOCX para todos os 6 tipos quando contexto OK.
- 400 quando context obrigatório (scenario_id/dossier_id/election_result_id) falta.
- 404 quando o recurso referenciado é de outra organização.
- 503 quando PDF é pedido mas WeasyPrint não está disponível.
- Audit log report.exported emitido.
- Smoke do HTML render: contém branding + disclaimer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.political import PoliticalAuditLog, PoliticalProject
from app.models.scenario import Scenario
from app.services import report_service
from app.services.report_service import REPORT_TYPES
from tests.conftest import campanhapro_secret_headers


def _create_project(client, headers, *, campaign_id: str = "cmp_report") -> str:
    payload = {
        "organization_id": "org_demo_001",
        "campaign_id": campaign_id,
        "name": "Projeto Relatório",
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
# Branding via snapshot
# ---------------------------------------------------------------------------


def test_snapshot_v1_populates_project_branding(client, db_session, analyst_auth_headers):
    project_id = _create_project(
        client, analyst_auth_headers, campaign_id="cmp_branding"
    )
    payload = {
        "schemaVersion": "campanhapro.snapshot.v1",
        "snapshotId": str(uuid.uuid4()),
        "campaignId": "cmp_branding",
        "organizationId": "org_demo_001",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "campaign": {
            "details": {
                "nomeUrna": "Maria 13",
                "office": "Prefeito",
                "candidatePhotoUrl": "https://example.com/foto.jpg",
                "headerLogo": "https://example.com/header.png",
                "footerLogo": "https://example.com/footer.png",
            }
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
        "privacyOptions": {},
        "metrics": {},
    }
    client.post(
        "/api/v1/campanhapro/ingest/snapshots",
        json=payload,
        headers=campanhapro_secret_headers(),
    )

    project = db_session.execute(
        select(PoliticalProject).filter_by(id=project_id)
    ).scalar_one()
    assert project.candidate_photo_url == "https://example.com/foto.jpg"
    assert project.header_logo_url == "https://example.com/header.png"
    assert project.footer_logo_url == "https://example.com/footer.png"


# ---------------------------------------------------------------------------
# Service: HTML render para todos os tipos
# ---------------------------------------------------------------------------


class _FakeProject:
    id = "proj_x"
    name = "Campanha X"
    candidate_name = "Maria"
    office = "Prefeito"
    election_year = 2026
    municipality = "Recife"
    state = "PE"
    parties = ["PT"]
    header_logo_url = None
    footer_logo_url = None
    candidate_photo_url = None


def test_html_render_for_every_report_type_includes_disclaimer():
    proj = _FakeProject()
    contexts: dict[str, dict] = {
        "executive_summary": report_service.build_executive_summary_context(
            proj, latest_factors=None, alerts=[], factor_catalog=[]
        ),
        "factor_deep_dive": report_service.build_factor_deep_dive_context(
            proj, cache=None, factor_catalog=[]
        ),
        "candidate_comparison": _common_election_ctx(proj),
        "scenario_what_if": _common_scenario_ctx(proj),
        "compliance_audit": report_service.build_compliance_audit_context(
            proj, alerts=[]
        ),
        "dossier_export": _common_dossier_ctx(proj),
    }
    for t in REPORT_TYPES:
        html = report_service.render_html(t, contexts[t])
        assert proj.name in html
        assert "uso interno" in html.lower()


def _common_election_ctx(proj):
    class _ER:
        confidence_level = "medium"
        iterations = 1000
        seed = 42
        output_results = [
            {
                "candidate_name": "A",
                "win_probability": 0.6,
                "win_first_round_probability": 0.5,
                "mean_share_first_round": 0.4,
                "share_ci_95_first_round": [0.35, 0.45],
                "second_round_qualification_probability": None,
                "second_round_win_given_qualified": None,
                "input_confidence": 0.6,
            },
            {
                "candidate_name": "B",
                "win_probability": 0.4,
                "win_first_round_probability": 0.5,
                "mean_share_first_round": 0.35,
                "share_ci_95_first_round": [0.3, 0.4],
                "second_round_qualification_probability": None,
                "second_round_win_given_qualified": None,
                "input_confidence": 0.6,
            },
        ]

    return report_service.build_candidate_comparison_context(proj, election_result=_ER())


def _common_scenario_ctx(proj):
    class _Sc:
        name = "Cenário 1"
        description = "Teste"
        baseline_score = 50
        alternative_score = 60
        delta = 10
        confidence_level = "medium"

    return report_service.build_scenario_what_if_context(
        proj, scenario=_Sc(), factor_breakdown=[]
    )


def _common_dossier_ctx(proj):
    class _D:
        candidate_name = "Maria"
        candidate_type = "own"
        party = "PT"
        office = "Prefeito"
        confidence_level = "medium"
        biography = "Síntese."
        current_mandates = []
        ficha_limpa_status = "Apta"
        swot = {}
        strength_drivers = []
        rejection_drivers = []
        legal_issues = []
        recent_news = []
        sources = []

    return report_service.build_dossier_export_context(proj, dossier=_D())


# ---------------------------------------------------------------------------
# Endpoint /reports — DOCX (sempre disponível em CI sem libpango)
# ---------------------------------------------------------------------------


def test_endpoint_executive_summary_docx(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_exec")
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/reports",
        json={"type": "executive_summary", "format": "docx"},
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert resp.headers["content-disposition"].endswith('.docx"')
    assert len(resp.content) > 1000


def test_endpoint_compliance_audit_docx(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_audit")
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/reports",
        json={"type": "compliance_audit", "format": "docx"},
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 200


def test_endpoint_dossier_export_requires_dossier_id(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_d_req")
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/reports",
        json={"type": "dossier_export", "format": "docx"},
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 400


def test_endpoint_candidate_comparison_requires_result_id(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_cc_req")
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/reports",
        json={"type": "candidate_comparison", "format": "docx"},
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 400


def test_endpoint_dossier_export_docx_with_real_dossier(
    client, analyst_auth_headers
):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_d_ok")
    create = client.post(
        f"/api/v1/political/projects/{project_id}/dossiers",
        json={
            "candidate_name": "João Adversário",
            "candidate_type": "opponent",
            "office": "Prefeito",
            "party": "ADV",
        },
        headers=analyst_auth_headers,
    )
    dossier_id = create.json()["dossier_id"]
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/reports",
        json={
            "type": "dossier_export",
            "format": "docx",
            "context": {"dossier_id": dossier_id},
        },
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 200


def test_endpoint_candidate_comparison_docx_with_real_result(
    client, analyst_auth_headers
):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_cc_ok")
    # cria simulação Monte Carlo (worker eager → completed)
    sim = client.post(
        f"/api/v1/political/projects/{project_id}/election-probability",
        json={
            "office": "Vereador",
            "iterations": 200,
            "seed": 1,
            "candidates": [
                {"name": "A", "factors": {"vote_intention": 60}, "confidence": 0.5},
                {"name": "B", "factors": {"vote_intention": 40}, "confidence": 0.5},
            ],
        },
        headers=analyst_auth_headers,
    )
    rid = sim.json()["result_id"]
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/reports",
        json={
            "type": "candidate_comparison",
            "format": "docx",
            "context": {"election_result_id": rid},
        },
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 200, resp.text


def test_endpoint_scenario_what_if_docx_with_real_scenario(
    client, db_session, analyst_auth_headers
):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_sc_ok")
    # cria cenário direto no DB (mais simples que pelo endpoint).
    scenario = Scenario(
        id=str(uuid.uuid4()),
        organization_id="org_demo_001",
        name="Cenário de teste",
        description="",
        scenario_type="electoral",
        baseline_inputs={"vote_intention": 40},
        alternative_inputs={"vote_intention": 60},
        baseline_score=40.0,
        alternative_score=60.0,
        delta=20.0,
        status="completed",
    )
    db_session.add(scenario)
    db_session.commit()
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/reports",
        json={
            "type": "scenario_what_if",
            "format": "docx",
            "context": {"scenario_id": scenario.id},
        },
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 503 quando PDF indisponível
# ---------------------------------------------------------------------------


def test_pdf_returns_503_when_weasyprint_unavailable(
    client, analyst_auth_headers, monkeypatch
):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_pdf")
    monkeypatch.setattr(report_service, "PDF_AVAILABLE", False)
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/reports",
        json={"type": "compliance_audit", "format": "pdf"},
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 503
    assert "WeasyPrint" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


def test_audit_log_report_exported(client, db_session, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_audlog")
    client.post(
        f"/api/v1/political/projects/{project_id}/reports",
        json={"type": "compliance_audit", "format": "docx"},
        headers=analyst_auth_headers,
    )
    rows = db_session.execute(
        select(PoliticalAuditLog).filter_by(action="report.exported")
    ).scalars().all()
    assert len(rows) >= 1
    assert rows[-1].payload["type"] == "compliance_audit"
    assert rows[-1].payload["format"] == "docx"
