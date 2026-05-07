from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class ScenarioFactor:
    key: str
    label: str
    weight: float
    recommendation_hint: str


# ---------------------------------------------------------------------------
# Electoral factors — pesos sugeridos pelo PRD (somam 1.0)
# ---------------------------------------------------------------------------

ELECTORAL_FACTORS: Final[tuple[ScenarioFactor, ...]] = (
    ScenarioFactor(
        key="rejection",
        label="Rejeição",
        weight=0.15,
        recommendation_hint="reduzir rejeição com escuta ativa, agenda positiva e correção de narrativa",
    ),
    ScenarioFactor(
        key="vote_intention",
        label="Intenção de Voto / Apoio Inicial",
        weight=0.14,
        recommendation_hint="ampliar conversão de simpatizantes em apoiadores declarados",
    ),
    ScenarioFactor(
        key="awareness",
        label="Conhecimento do Candidato",
        weight=0.10,
        recommendation_hint="investir em presença orgânica e mídia para reduzir desconhecimento",
    ),
    ScenarioFactor(
        key="territorial_strength",
        label="Força Territorial",
        weight=0.10,
        recommendation_hint="reforçar lideranças locais e capilaridade por município/zona",
    ),
    ScenarioFactor(
        key="alliances",
        label="Força de Alianças",
        weight=0.08,
        recommendation_hint="formalizar coligações e diálogos com partidos compatíveis",
    ),
    ScenarioFactor(
        key="mobilization",
        label="Mobilização de Base",
        weight=0.08,
        recommendation_hint="ativar voluntariado, comitês e multiplicadores em território",
    ),
    ScenarioFactor(
        key="digital_sentiment",
        label="Sentimento Digital",
        weight=0.08,
        recommendation_hint="monitorar redes, responder rapidamente e qualificar engajamento",
    ),
    ScenarioFactor(
        key="local_agenda_fit",
        label="Aderência a Pautas Locais",
        weight=0.07,
        recommendation_hint="adaptar mensagem e propostas à realidade do território disputado",
    ),
    ScenarioFactor(
        key="reputation_risk",
        label="Risco Reputacional",
        weight=0.07,
        recommendation_hint="mapear vulnerabilidades, reforçar compliance e plano de gestão de crise",
    ),
    ScenarioFactor(
        key="operational_efficiency",
        label="Eficiência Operacional",
        weight=0.06,
        recommendation_hint="profissionalizar coordenação, agenda, jurídico e comunicação interna",
    ),
    ScenarioFactor(
        key="media_coverage",
        label="Cobertura de Mídia",
        weight=0.04,
        recommendation_hint="cultivar relacionamento com imprensa local e nacional com pautas próprias",
    ),
    ScenarioFactor(
        key="declared_funding",
        label="Capacidade Financeira Declarada",
        weight=0.03,
        recommendation_hint="diversificar arrecadação dentro dos limites e prazos do TSE",
    ),
)


# ---------------------------------------------------------------------------
# Catalog registry (domínio único: electoral)
# ---------------------------------------------------------------------------

SCENARIO_CATALOG: Final[dict[str, tuple[ScenarioFactor, ...]]] = {
    "electoral": ELECTORAL_FACTORS,
}

SCENARIO_TYPE_LABELS: Final[dict[str, str]] = {
    "electoral": "Eleitoral",
}

SCENARIO_SOURCE_SYSTEMS: Final[dict[str, str]] = {
    "electoral": "CAMPANHAPRO",
}


def get_factors_for_type(scenario_type: str) -> tuple[ScenarioFactor, ...]:
    return SCENARIO_CATALOG.get(scenario_type, ELECTORAL_FACTORS)


def get_factor_map_for_type(scenario_type: str) -> dict[str, ScenarioFactor]:
    return {f.key: f for f in get_factors_for_type(scenario_type)}


def get_factor_keys_for_type(scenario_type: str) -> tuple[str, ...]:
    return tuple(f.key for f in get_factors_for_type(scenario_type))


def get_total_weight_for_type(scenario_type: str) -> float:
    return round(sum(f.weight for f in get_factors_for_type(scenario_type)), 2)


# ---------------------------------------------------------------------------
# Aliases used by prediction_service / tests (electoral é o único domínio)
# ---------------------------------------------------------------------------

SCENARIO_FACTORS = ELECTORAL_FACTORS
SCENARIO_FACTOR_MAP = get_factor_map_for_type("electoral")
SCENARIO_FACTOR_KEYS = get_factor_keys_for_type("electoral")
TOTAL_FACTOR_WEIGHT = get_total_weight_for_type("electoral")
