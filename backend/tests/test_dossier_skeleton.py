"""Fase 3a PRD v2 — contratos dos skeletons do dossiê.

A Fase 3a só introduz infraestrutura (modelos + assinatura dos serviços +
tools_available). Estes testes garantem que:
- Todos os serviços retornam ``DossierServiceResult`` válido.
- Skeletons retornam estrutura vazia sem lançar exceção.
- ``tools_available`` foi populado nos especialistas relevantes
  (adversários, mídia, crise) e fica vazio nos demais.
- Modelos podem ser criados e persistidos.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.models.dossier import CandidateDossier, DossierSocialSnapshot
from app.services.dossier import (
    DossierServiceResult,
    empty_result,
    facebook_service,
    instagram_service,
    legal_search_service,
    news_service,
    tiktok_service,
    tse_service,
    twitter_service,
    web_research_service,
)
from app.services.political_agents_catalog import FIXED_SPECIALISTS


# ---------------------------------------------------------------------------
# Contrato DossierServiceResult
# ---------------------------------------------------------------------------


REQUIRED_KEYS = {"data", "sources", "confidence", "errors"}


def _assert_contract(result: DossierServiceResult) -> None:
    assert set(result.keys()) == REQUIRED_KEYS, f"chaves faltando: {set(result.keys())}"
    assert isinstance(result["sources"], list)
    assert isinstance(result["errors"], list)
    assert result["confidence"] in {"high", "medium", "low"}


def test_empty_result_matches_contract():
    _assert_contract(empty_result())
    _assert_contract(empty_result(confidence="medium"))


def test_web_research_skeleton_contract():
    r = web_research_service.research_candidate("Maria 13", "PT", "Prefeito")
    _assert_contract(r)
    assert r["confidence"] == "low"  # skeleton ainda sem dado real


def test_news_skeleton_contract():
    r = news_service.fetch_recent_news("Maria 13")
    _assert_contract(r)
    # news/legal retornam list em data; outros, dict.
    assert isinstance(r["data"], list)


def test_tse_skeleton_contract():
    r = tse_service.lookup_candidate("Maria", election_year=2026, office="Prefeito")
    _assert_contract(r)


def test_legal_search_skeleton_contract():
    r = legal_search_service.search_legal_issues("Maria 13", party="PT")
    _assert_contract(r)
    assert isinstance(r["data"], list)


def test_instagram_skeleton_contract():
    _assert_contract(instagram_service.fetch_own_metrics("@maria13"))
    _assert_contract(instagram_service.parse_manual_entry({"handle": "@maria13"}))


def test_facebook_skeleton_contract():
    _assert_contract(facebook_service.fetch_own_page_metrics("page_123"))
    _assert_contract(facebook_service.parse_manual_entry({}))


def test_twitter_skeleton_contract():
    _assert_contract(twitter_service.parse_manual_entry({}))
    _assert_contract(twitter_service.estimate_via_llm("@adversario"))


def test_tiktok_skeleton_contract():
    _assert_contract(tiktok_service.parse_manual_entry({}))
    _assert_contract(tiktok_service.estimate_via_llm("@adversario"))


# ---------------------------------------------------------------------------
# tools_available nos especialistas
# ---------------------------------------------------------------------------


CATEGORIES_WITH_DOSSIER_TOOLS = {"midia", "crise", "adversarios"}


def test_relevant_specialists_have_dossier_tools():
    for spec in FIXED_SPECIALISTS:
        if spec.category in CATEGORIES_WITH_DOSSIER_TOOLS:
            assert "dossier_lookup" in spec.tools_available, (
                f"{spec.category} deveria ter dossier_lookup"
            )
            assert "web_search" in spec.tools_available, (
                f"{spec.category} deveria ter web_search"
            )


def test_other_specialists_have_no_tools():
    """Default vazio nas demais categorias — comportamento legado intacto."""
    for spec in FIXED_SPECIALISTS:
        if spec.category not in CATEGORIES_WITH_DOSSIER_TOOLS:
            assert spec.tools_available == (), (
                f"{spec.category} ganhou tools sem motivo: {spec.tools_available}"
            )


# ---------------------------------------------------------------------------
# Modelos persistem
# ---------------------------------------------------------------------------


def test_candidate_dossier_model_can_be_persisted(db_session):
    # Cria projeto via ORM (sem passar pelo endpoint para simplificar).
    from app.models.political import PoliticalProject

    project = PoliticalProject(
        id="proj_test",
        organization_id="org_demo_001",
        campaign_id="cmp_test",
        name="Campanha Teste",
        election_year=2026,
        office="Prefeito",
        candidate_name="Maria",
        parties=[],
        known_opponents=[],
        status="draft",
    )
    db_session.add(project)
    db_session.commit()

    dossier = CandidateDossier(
        id=str(uuid4()),
        organization_id="org_demo_001",
        political_project_id="proj_test",
        candidate_name="João Adversário",
        candidate_type="opponent",
        party="ADV",
        office="Prefeito",
        status="queued",
    )
    db_session.add(dossier)
    db_session.commit()
    db_session.refresh(dossier)

    assert dossier.id
    assert dossier.status == "queued"
    assert dossier.generated_by_ai is True  # default
    assert dossier.confidence_level == "medium"
    assert dossier.political_history == {}
    assert dossier.sources == []


def test_dossier_social_snapshot_persists_with_source_marker(db_session):
    from app.models.political import PoliticalProject

    db_session.add(
        PoliticalProject(
            id="proj_social",
            organization_id="org_demo_001",
            campaign_id="cmp_social",
            name="Social Test",
            election_year=2026,
            office="Prefeito",
            candidate_name="Maria",
            parties=[],
            known_opponents=[],
            status="draft",
        )
    )
    dossier = CandidateDossier(
        id="dossier_test_1",
        organization_id="org_demo_001",
        political_project_id="proj_social",
        candidate_name="Adv",
        candidate_type="opponent",
        office="Prefeito",
    )
    db_session.add(dossier)
    db_session.commit()

    snap = DossierSocialSnapshot(
        id=str(uuid4()),
        dossier_id="dossier_test_1",
        platform="twitter",
        handle="@adversario",
        followers=12345,
        source="manual",
        collected_at=datetime.utcnow(),
    )
    db_session.add(snap)
    db_session.commit()
    db_session.refresh(snap)

    assert snap.source == "manual"
    assert snap.followers == 12345
    assert snap.sentiment_distribution == {}
