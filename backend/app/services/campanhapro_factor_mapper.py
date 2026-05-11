"""Mapper snapshot CampanhaPro v1 → 12 fatores eleitorais (Fase 2 PRD v2).

Princípio firme: **fatores sem dado real ficam fora do dict retornado**.
Coverage baixo é informação, não problema a esconder. Nunca preencher
com 0 só para "completar" a tabela.

Tabela de mapeamento (resumo do PRD §2.1):

| Fator                 | Fonte                                | Cálculo                                                                      |
|-----------------------|--------------------------------------|------------------------------------------------------------------------------|
| vote_intention        | data.pesquisa[].intencaoVoto         | % de respostas que apontam o candidato próprio (cap 100)                     |
| rejection             | data.pesquisa[].fatorRejeicao        | % de respostas que rejeitam o candidato próprio                              |
| awareness             | data.pesquisa[].conheceCandidato     | 100 − % de "não conhece"                                                     |
| territorial_strength  | teamMembers + locations              | (locations com líder ativo / total locations) × 100                          |
| alliances             | teamMembers (role=liderPolitico)     | nº líderes políticos ativos × 10 (cap 100)                                   |
| mobilization          | visits + engagementActions (30d)     | (eventos + visitas + ações) / meta declarada × 100 (cap 100)                 |
| digital_sentiment     | dossiê (Fase 3)                      | **fora deste mapper na v1** — ver dossier_orchestrator                       |
| local_agenda_fit      | streetReports                        | 100 − (negativos / total × 100)                                              |
| reputation_risk       | streetReports + neighborhoodFlags    | (negativos + alertas) / total × 100                                          |
| operational_efficiency| fieldTickets                         | (concluídos / total) × 100                                                   |
| media_coverage        | dossiê (Fase 3)                      | **fora deste mapper na v1**                                                  |
| declared_funding      | financial.incomes vs metaArrecadacao | (arrecadado / meta) × 100 (cap 100)                                          |

Identidade do candidato próprio: assume-se ``campaign.details.nomeUrna``
como string canônica para casar com ``intencaoVoto`` / ``fatorRejeicao``.
Comparação case-insensitive e tolerante a espaços. Se ``nomeUrna`` está
vazio, fatores derivados de pesquisa são pulados com warning.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

from app.core.scenario_catalog import ELECTORAL_FACTORS

ALL_FACTOR_KEYS: frozenset[str] = frozenset(f.key for f in ELECTORAL_FACTORS)
MIN_POLL_SAMPLE_SIZE = 30


def _norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clip(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        # Aceita "2026-03-15T00:00:00Z" e ISO completo
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except (TypeError, ValueError):
        return None


def _generated_at(payload: dict) -> datetime:
    parsed = _parse_iso(payload.get("generatedAt"))
    return parsed or datetime.utcnow()


# ---------------------------------------------------------------------------
# Cálculos por fator
# ---------------------------------------------------------------------------


def _factor_vote_intention(
    pesquisa: list[dict], own_name_norm: str, warnings: list[str]
) -> float | None:
    if not pesquisa or not own_name_norm:
        return None
    total = len(pesquisa)
    if total < MIN_POLL_SAMPLE_SIZE:
        warnings.append(
            f"vote_intention: amostra de pesquisa pequena ({total} < {MIN_POLL_SAMPLE_SIZE})"
        )
    favoraveis = sum(1 for r in pesquisa if _norm(r.get("intencaoVoto")) == own_name_norm)
    return _clip(100.0 * favoraveis / total)


def _factor_rejection(
    pesquisa: list[dict], own_name_norm: str, warnings: list[str]
) -> float | None:
    if not pesquisa or not own_name_norm:
        return None
    total = len(pesquisa)
    rejeicoes = sum(
        1 for r in pesquisa if _norm(r.get("fatorRejeicao")) == own_name_norm
    )
    return _clip(100.0 * rejeicoes / total)


def _factor_awareness(pesquisa: list[dict], warnings: list[str]) -> float | None:
    if not pesquisa:
        return None
    answered = [r for r in pesquisa if r.get("conheceCandidato") is not None]
    if not answered:
        warnings.append("awareness: nenhuma resposta com 'conheceCandidato' preenchido")
        return None
    desconhecem = sum(1 for r in answered if r.get("conheceCandidato") is False)
    return _clip(100.0 - (100.0 * desconhecem / len(answered)))


def _factor_territorial_strength(
    locations: list[dict], team_members: list[dict]
) -> float | None:
    if not locations:
        return None
    active_lider_loc_ids: set[str] = set()
    for member in team_members:
        if not member.get("ativo"):
            continue
        if _norm(member.get("role")) not in {"lider", "coordenador", "liderpolitico"}:
            continue
        # Casa por bairro (simplificação aceitável v1: associação por bairro,
        # já que CampanhaPro não tem FK explícita líder→location).
        bairro = _norm(member.get("bairro"))
        if not bairro:
            continue
        for loc in locations:
            if _norm(loc.get("bairro")) == bairro and loc.get("ativo"):
                active_lider_loc_ids.add(loc.get("id"))
    return _clip(100.0 * len(active_lider_loc_ids) / len(locations))


def _factor_alliances(team_members: list[dict]) -> float | None:
    if not team_members:
        return None
    politicos_ativos = sum(
        1
        for m in team_members
        if _norm(m.get("role")) == "liderpolitico" and m.get("ativo")
    )
    if politicos_ativos == 0:
        return None
    return _clip(politicos_ativos * 10.0)


def _factor_mobilization(
    visits: list[dict],
    engagement: list[dict],
    calculator_settings: dict,
    generated_at: datetime,
) -> float | None:
    meta_visitas = _safe_int(calculator_settings.get("metaVisitas"), 0)
    if meta_visitas <= 0:
        return None  # sem meta declarada não dá pra normalizar
    cutoff = generated_at - timedelta(days=30)

    def _within(items: Iterable[dict]) -> int:
        c = 0
        for it in items:
            d = _parse_iso(it.get("data"))
            if d and d >= cutoff:
                c += 1
        return c

    realizado = _within(visits) + _within(engagement)
    return _clip(100.0 * realizado / meta_visitas)


def _factor_local_agenda_fit(street_reports: list[dict]) -> float | None:
    if not street_reports:
        return None
    total = len(street_reports)
    negativos = sum(
        1
        for r in street_reports
        if _norm(r.get("climaPredominante")) == "negativo"
    )
    return _clip(100.0 - (100.0 * negativos / total))


def _factor_reputation_risk(
    street_reports: list[dict], neighborhood_flags: list[dict]
) -> float | None:
    base = len(street_reports)
    if base == 0 and not neighborhood_flags:
        return None
    negativos = sum(
        1
        for r in street_reports
        if _norm(r.get("climaPredominante")) == "negativo"
    )
    alertas = sum(
        1 for f in neighborhood_flags if _norm(f.get("tipo")) == "alerta"
    )
    denom = max(base + len(neighborhood_flags), 1)
    return _clip(100.0 * (negativos + alertas) / denom)


def _factor_operational_efficiency(field_tickets: list[dict]) -> float | None:
    if not field_tickets:
        return None
    concluidos = sum(
        1 for t in field_tickets if _norm(t.get("status")) == "concluido"
    )
    return _clip(100.0 * concluidos / len(field_tickets))


def _factor_declared_funding(
    incomes: list[dict], calculator_settings: dict
) -> float | None:
    meta = _safe_float(calculator_settings.get("metaArrecadacao"), 0.0)
    if meta <= 0:
        return None
    arrecadado = sum(_safe_float(i.get("valor")) for i in incomes)
    return _clip(100.0 * arrecadado / meta)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def map_snapshot_to_factors(snapshot_payload: dict[str, Any]) -> dict[str, Any]:
    """Transforma um snapshot v1 nos 12 fatores eleitorais.

    Retorna ``{factors, coverage_percent, sources_used, warnings}``.
    Apenas fatores com dado real entram em ``factors``. ``coverage_percent``
    é a fração desses fatores sobre os 12 totais.
    """
    if snapshot_payload.get("schemaVersion") != "campanhapro.snapshot.v1":
        return {
            "factors": {},
            "coverage_percent": 0.0,
            "sources_used": {},
            "warnings": ["schema_version diferente de campanhapro.snapshot.v1 — mapper não aplicável"],
        }

    data = snapshot_payload.get("data") or {}
    campaign = snapshot_payload.get("campaign") or {}
    details = campaign.get("details") or {}
    own_name = _norm(details.get("nomeUrna"))

    pesquisa = data.get("pesquisa") or []
    visits = data.get("visits") or []
    engagement = data.get("engagementActions") or []
    team_members = data.get("teamMembers") or []
    locations = data.get("locations") or []
    street_reports = data.get("streetReports") or []
    neighborhood_flags = data.get("neighborhoodFlags") or []
    field_tickets = data.get("fieldTickets") or []
    financial = data.get("financial") or {}
    incomes = financial.get("incomes") or []
    calculator_settings = data.get("calculatorSettings") or {}
    generated_at = _generated_at(snapshot_payload)

    warnings: list[str] = []
    if not own_name:
        warnings.append(
            "campaign.details.nomeUrna ausente — vote_intention e rejection ignorados"
        )

    candidates: list[tuple[str, float | None, list[str]]] = [
        ("vote_intention", _factor_vote_intention(pesquisa, own_name, warnings), ["pesquisa.intencaoVoto", "campaign.details.nomeUrna"]),
        ("rejection", _factor_rejection(pesquisa, own_name, warnings), ["pesquisa.fatorRejeicao", "campaign.details.nomeUrna"]),
        ("awareness", _factor_awareness(pesquisa, warnings), ["pesquisa.conheceCandidato"]),
        ("territorial_strength", _factor_territorial_strength(locations, team_members), ["locations", "teamMembers"]),
        ("alliances", _factor_alliances(team_members), ["teamMembers.role=liderPolitico"]),
        ("mobilization", _factor_mobilization(visits, engagement, calculator_settings, generated_at), ["visits", "engagementActions", "calculatorSettings.metaVisitas"]),
        ("local_agenda_fit", _factor_local_agenda_fit(street_reports), ["streetReports.climaPredominante"]),
        ("reputation_risk", _factor_reputation_risk(street_reports, neighborhood_flags), ["streetReports", "neighborhoodFlags"]),
        ("operational_efficiency", _factor_operational_efficiency(field_tickets), ["fieldTickets.status"]),
        ("declared_funding", _factor_declared_funding(incomes, calculator_settings), ["financial.incomes", "calculatorSettings.metaArrecadacao"]),
        # digital_sentiment e media_coverage só são preenchidos pela Fase 3 (dossiê).
    ]

    factors: dict[str, float] = {}
    sources_used: dict[str, list[str]] = {}

    for key, value, sources in candidates:
        if value is None:
            continue
        factors[key] = round(value, 2)
        sources_used[key] = sources

    coverage_percent = round(100.0 * len(factors) / len(ALL_FACTOR_KEYS), 2)

    return {
        "factors": factors,
        "coverage_percent": coverage_percent,
        "sources_used": sources_used,
        "warnings": warnings,
    }
