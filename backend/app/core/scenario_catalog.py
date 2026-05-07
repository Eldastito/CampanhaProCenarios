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
# Education — FORGE platform (escolas públicas/privadas)
# ---------------------------------------------------------------------------

EDUCATION_FACTORS: Final[tuple[ScenarioFactor, ...]] = (
    ScenarioFactor(
        key="training",
        label="Treinamento",
        weight=0.20,
        recommendation_hint="fortalecer planos de treinamento e ciclos de prática guiada",
    ),
    ScenarioFactor(
        key="digital_maturity",
        label="Maturidade Digital",
        weight=0.20,
        recommendation_hint="melhorar digitalização de processos, governança e prontidão operacional",
    ),
    ScenarioFactor(
        key="teacher_adoption",
        label="Adoção por Professores",
        weight=0.20,
        recommendation_hint="aumentar adesão com onboarding, suporte e incentivos",
    ),
    ScenarioFactor(
        key="infrastructure",
        label="Infraestrutura",
        weight=0.15,
        recommendation_hint="reforçar dispositivos, conectividade e suporte técnico",
    ),
    ScenarioFactor(
        key="institutional_support",
        label="Suporte Institucional",
        weight=0.15,
        recommendation_hint="garantir patrocínio da liderança e governança de execução",
    ),
    ScenarioFactor(
        key="engagement",
        label="Engajamento",
        weight=0.10,
        recommendation_hint="melhorar comunicação e rotinas de engajamento dos stakeholders",
    ),
)

# ---------------------------------------------------------------------------
# Political / Elections — CampanhaPro platform
# ---------------------------------------------------------------------------

POLITICAL_FACTORS: Final[tuple[ScenarioFactor, ...]] = (
    ScenarioFactor(
        key="public_opinion",
        label="Opinião Pública",
        weight=0.25,
        recommendation_hint="intensificar ações de campo e presença nas pesquisas de intenção de voto",
    ),
    ScenarioFactor(
        key="legislative_support",
        label="Apoio Legislativo",
        weight=0.20,
        recommendation_hint="ampliar coalizões e alianças no parlamento",
    ),
    ScenarioFactor(
        key="media_sentiment",
        label="Sentimento na Mídia",
        weight=0.20,
        recommendation_hint="melhorar estratégia de comunicação e assessoria de imprensa",
    ),
    ScenarioFactor(
        key="party_unity",
        label="Unidade Partidária",
        weight=0.15,
        recommendation_hint="fortalecer coesão interna e reduzir dissidências",
    ),
    ScenarioFactor(
        key="economic_perception",
        label="Percepção Econômica",
        weight=0.10,
        recommendation_hint="vincular agenda econômica a propostas concretas para o eleitorado",
    ),
    ScenarioFactor(
        key="voter_turnout",
        label="Comparecimento do Eleitorado",
        weight=0.10,
        recommendation_hint="investir em mobilização de base e transporte para zonas eleitorais",
    ),
)

# ---------------------------------------------------------------------------
# Business / Products — BackOffice / banco de dados da empresa
# ---------------------------------------------------------------------------

BUSINESS_FACTORS: Final[tuple[ScenarioFactor, ...]] = (
    ScenarioFactor(
        key="market_demand",
        label="Demanda de Mercado",
        weight=0.25,
        recommendation_hint="analisar tendências e ajustar oferta ao volume demandado",
    ),
    ScenarioFactor(
        key="target_audience_fit",
        label="Alinhamento com Público-Alvo",
        weight=0.20,
        recommendation_hint="refinar persona e comunicação para o segmento prioritário",
    ),
    ScenarioFactor(
        key="trend_alignment",
        label="Alinhamento com Tendências",
        weight=0.20,
        recommendation_hint="monitorar tendências de moda/comportamento e antecipar mudanças",
    ),
    ScenarioFactor(
        key="competitive_position",
        label="Posição Competitiva",
        weight=0.15,
        recommendation_hint="diferenciar produto/serviço frente à concorrência direta",
    ),
    ScenarioFactor(
        key="brand_sentiment",
        label="Sentimento de Marca",
        weight=0.10,
        recommendation_hint="investir em branding, reputação e gestão de redes sociais",
    ),
    ScenarioFactor(
        key="distribution_reach",
        label="Alcance de Distribuição",
        weight=0.10,
        recommendation_hint="ampliar canais de venda e logística para novos mercados",
    ),
)

# ---------------------------------------------------------------------------
# Catalog registry
# ---------------------------------------------------------------------------

SCENARIO_CATALOG: Final[dict[str, tuple[ScenarioFactor, ...]]] = {
    "education": EDUCATION_FACTORS,
    "political": POLITICAL_FACTORS,
    "business": BUSINESS_FACTORS,
}

SCENARIO_TYPE_LABELS: Final[dict[str, str]] = {
    "education": "Educação",
    "political": "Político (Eleições)",
    "business": "Empresas e Produtos",
}

SCENARIO_SOURCE_SYSTEMS: Final[dict[str, str]] = {
    "education": "FORGE",
    "political": "CAMPANHAPRO",
    "business": "BACKOFFICE",
}


def get_factors_for_type(scenario_type: str) -> tuple[ScenarioFactor, ...]:
    return SCENARIO_CATALOG.get(scenario_type, EDUCATION_FACTORS)


def get_factor_map_for_type(scenario_type: str) -> dict[str, ScenarioFactor]:
    return {f.key: f for f in get_factors_for_type(scenario_type)}


def get_factor_keys_for_type(scenario_type: str) -> tuple[str, ...]:
    return tuple(f.key for f in get_factors_for_type(scenario_type))


def get_total_weight_for_type(scenario_type: str) -> float:
    return round(sum(f.weight for f in get_factors_for_type(scenario_type)), 2)


# ---------------------------------------------------------------------------
# Backwards-compatibility aliases (used by prediction_service / tests)
# ---------------------------------------------------------------------------

SCENARIO_FACTORS = EDUCATION_FACTORS
SCENARIO_FACTOR_MAP = get_factor_map_for_type("education")
SCENARIO_FACTOR_KEYS = get_factor_keys_for_type("education")
TOTAL_FACTOR_WEIGHT = get_total_weight_for_type("education")
