"""Fase 2 PRD v2 — unit tests do mapper snapshot v1 → 12 fatores.

Princípios validados:
- Fatores sem dado real ficam fora do dict (não preencher com 0).
- Coverage_percent reflete a fração dos 12 fatores totais que foram preenchidos.
- sources_used aponta as origens consultadas.
- Schema diferente de v1 → mapper retorna estrutura vazia com warning.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.campanhapro_factor_mapper import (
    ALL_FACTOR_KEYS,
    map_snapshot_to_factors,
)


def _empty_v1_payload(**overrides) -> dict:
    base = {
        "schemaVersion": "campanhapro.snapshot.v1",
        "snapshotId": "00000000-0000-0000-0000-000000000001",
        "campaignId": "cmp_test",
        "organizationId": "org_demo_001",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "campaign": {
            "details": {"nomeUrna": "Maria 13", "office": "Prefeito"},
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
        "privacyOptions": {},
        "metrics": {},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Estrutura geral
# ---------------------------------------------------------------------------


def test_empty_snapshot_yields_empty_factors_and_zero_coverage():
    result = map_snapshot_to_factors(_empty_v1_payload())
    assert result["factors"] == {}
    assert result["coverage_percent"] == 0.0
    assert result["sources_used"] == {}
    assert isinstance(result["warnings"], list)


def test_legacy_payload_returns_warning_and_empty():
    legacy = {"snapshot_type": "electoral_metrics", "payload": {}}
    result = map_snapshot_to_factors(legacy)
    assert result["factors"] == {}
    assert "campanhapro.snapshot.v1" in " ".join(result["warnings"]).lower()


def test_factors_present_never_zero_for_missing_data():
    """Fatores sem dado fonte NUNCA aparecem no dict — nem como 0."""
    result = map_snapshot_to_factors(_empty_v1_payload())
    for key in ALL_FACTOR_KEYS:
        assert key not in result["factors"]


# ---------------------------------------------------------------------------
# Pesquisa: vote_intention, rejection, awareness
# ---------------------------------------------------------------------------


def test_vote_intention_calculates_proportion_against_own_candidate():
    pesquisa = (
        [{"intencaoVoto": "Maria 13"} for _ in range(40)]
        + [{"intencaoVoto": "Joao 22"} for _ in range(60)]
    )
    payload = _empty_v1_payload()
    payload["data"]["pesquisa"] = pesquisa
    result = map_snapshot_to_factors(payload)
    assert result["factors"]["vote_intention"] == 40.0


def test_rejection_calculates_proportion_against_own_candidate():
    pesquisa = [{"fatorRejeicao": "Maria 13"} for _ in range(15)] + [{} for _ in range(85)]
    payload = _empty_v1_payload()
    payload["data"]["pesquisa"] = pesquisa
    result = map_snapshot_to_factors(payload)
    assert result["factors"]["rejection"] == 15.0


def test_awareness_inverts_dont_know_ratio():
    # 30 não conhecem, 70 conhecem → awareness = 70.
    pesquisa = (
        [{"conheceCandidato": False} for _ in range(30)]
        + [{"conheceCandidato": True} for _ in range(70)]
    )
    payload = _empty_v1_payload()
    payload["data"]["pesquisa"] = pesquisa
    result = map_snapshot_to_factors(payload)
    assert result["factors"]["awareness"] == 70.0


def test_pesquisa_without_own_name_skips_vote_factors():
    payload = _empty_v1_payload()
    payload["campaign"]["details"]["nomeUrna"] = ""
    payload["data"]["pesquisa"] = [{"intencaoVoto": "Maria 13"}] * 50
    result = map_snapshot_to_factors(payload)
    assert "vote_intention" not in result["factors"]
    assert "rejection" not in result["factors"]
    assert any("nomeUrna" in w for w in result["warnings"])


def test_small_sample_emits_warning_but_still_calculates():
    payload = _empty_v1_payload()
    payload["data"]["pesquisa"] = [{"intencaoVoto": "Maria 13"}] * 10
    result = map_snapshot_to_factors(payload)
    assert "vote_intention" in result["factors"]
    assert any("amostra" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# Território, alianças
# ---------------------------------------------------------------------------


def test_territorial_strength_counts_locations_with_active_leader_in_bairro():
    payload = _empty_v1_payload()
    payload["data"]["locations"] = [
        {"id": "loc1", "bairro": "Centro", "ativo": True},
        {"id": "loc2", "bairro": "Boa Viagem", "ativo": True},
        {"id": "loc3", "bairro": "Sul", "ativo": True},
        {"id": "loc4", "bairro": "Sul", "ativo": True},
    ]
    payload["data"]["teamMembers"] = [
        {"role": "lider", "bairro": "Centro", "ativo": True},
        {"role": "lider", "bairro": "Boa Viagem", "ativo": False},  # inativo
        {"role": "voluntario", "bairro": "Sul", "ativo": True},  # role errada
    ]
    result = map_snapshot_to_factors(payload)
    # 1 location de 4 com líder ativo → 25%
    assert result["factors"]["territorial_strength"] == 25.0


def test_alliances_uses_lider_politico_count_capped_at_100():
    payload = _empty_v1_payload()
    payload["data"]["teamMembers"] = [
        {"role": "liderPolitico", "ativo": True} for _ in range(15)
    ]
    result = map_snapshot_to_factors(payload)
    # 15 * 10 = 150, cap em 100
    assert result["factors"]["alliances"] == 100.0


def test_alliances_skipped_when_no_political_leaders():
    payload = _empty_v1_payload()
    payload["data"]["teamMembers"] = [{"role": "voluntario", "ativo": True}]
    result = map_snapshot_to_factors(payload)
    assert "alliances" not in result["factors"]


# ---------------------------------------------------------------------------
# Mobilização (visits + engagement vs metaVisitas)
# ---------------------------------------------------------------------------


def test_mobilization_uses_30day_window_and_meta_visitas():
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    payload = _empty_v1_payload(generatedAt=now.isoformat())
    payload["data"]["calculatorSettings"] = {"metaVisitas": 100}
    # 25 dentro da janela, 5 fora.
    in_window = (now - timedelta(days=10)).isoformat()
    out_window = (now - timedelta(days=45)).isoformat()
    payload["data"]["visits"] = [{"data": in_window} for _ in range(20)] + [
        {"data": out_window} for _ in range(5)
    ]
    payload["data"]["engagementActions"] = [{"data": in_window} for _ in range(5)]
    result = map_snapshot_to_factors(payload)
    # 25 dentro / 100 meta = 25%
    assert result["factors"]["mobilization"] == 25.0


def test_mobilization_skipped_without_meta():
    payload = _empty_v1_payload()
    payload["data"]["visits"] = [{"data": "2026-05-01T00:00:00Z"}] * 50
    result = map_snapshot_to_factors(payload)
    assert "mobilization" not in result["factors"]


# ---------------------------------------------------------------------------
# Reportes de rua e bandeiras
# ---------------------------------------------------------------------------


def test_local_agenda_fit_inverts_negative_reports():
    payload = _empty_v1_payload()
    payload["data"]["streetReports"] = (
        [{"climaPredominante": "negativo"} for _ in range(20)]
        + [{"climaPredominante": "positivo"} for _ in range(80)]
    )
    result = map_snapshot_to_factors(payload)
    # 100 - 20% negativos = 80
    assert result["factors"]["local_agenda_fit"] == 80.0


def test_reputation_risk_combines_negatives_and_alerts():
    payload = _empty_v1_payload()
    payload["data"]["streetReports"] = [
        {"climaPredominante": "negativo"} for _ in range(10)
    ] + [{"climaPredominante": "positivo"} for _ in range(40)]
    payload["data"]["neighborhoodFlags"] = [{"tipo": "alerta"}] * 5 + [
        {"tipo": "oportunidade"}
    ] * 5
    result = map_snapshot_to_factors(payload)
    # negativos=10, alertas=5, denom=50+10=60 → 25%
    assert result["factors"]["reputation_risk"] == 25.0


# ---------------------------------------------------------------------------
# Field tickets, financial
# ---------------------------------------------------------------------------


def test_operational_efficiency_proportion_done():
    payload = _empty_v1_payload()
    payload["data"]["fieldTickets"] = (
        [{"status": "concluido"} for _ in range(7)]
        + [{"status": "aberto"} for _ in range(3)]
    )
    result = map_snapshot_to_factors(payload)
    assert result["factors"]["operational_efficiency"] == 70.0


def test_declared_funding_proportion_against_target():
    payload = _empty_v1_payload()
    payload["data"]["calculatorSettings"] = {"metaArrecadacao": 200000}
    payload["data"]["financial"]["incomes"] = [
        {"valor": 50000},
        {"valor": 30000},
        {"valor": 20000},
    ]
    result = map_snapshot_to_factors(payload)
    # 100k / 200k = 50%
    assert result["factors"]["declared_funding"] == 50.0


def test_declared_funding_capped_at_100():
    payload = _empty_v1_payload()
    payload["data"]["calculatorSettings"] = {"metaArrecadacao": 100000}
    payload["data"]["financial"]["incomes"] = [{"valor": 250000}]
    result = map_snapshot_to_factors(payload)
    assert result["factors"]["declared_funding"] == 100.0


# ---------------------------------------------------------------------------
# Coverage e sources_used
# ---------------------------------------------------------------------------


def test_coverage_percent_reflects_factors_filled():
    payload = _empty_v1_payload()
    payload["data"]["fieldTickets"] = [{"status": "concluido"}]
    result = map_snapshot_to_factors(payload)
    # 1 fator de 12 → ~8.33%
    assert 8.0 < result["coverage_percent"] < 9.0


def test_sources_used_lists_origins_for_each_filled_factor():
    payload = _empty_v1_payload()
    payload["data"]["calculatorSettings"] = {"metaArrecadacao": 1000}
    payload["data"]["financial"]["incomes"] = [{"valor": 500}]
    result = map_snapshot_to_factors(payload)
    assert "declared_funding" in result["sources_used"]
    assert any("incomes" in s for s in result["sources_used"]["declared_funding"])
