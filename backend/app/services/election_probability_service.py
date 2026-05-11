"""Monte Carlo de probabilidade de eleição (Fase 4 PRD v2).

Compara N candidatos (2-10) usando os 12 fatores eleitorais de cada um
e devolve probabilidade percentual de vitória + intervalo de confiança 95%.

Algoritmo:
1. Converte fatores 0-100 em ``candidacy_strength`` ∈ [0, 1] usando os
   pesos do ``prediction_service`` (mesma fórmula de ``_score_from_factors``,
   reproduzida aqui sem importar para manter a simulação pura/rápida).
2. Calcula share inicial de cada candidato proporcional ao strength.
3. Para cada uma de ``n_iterations`` iterações:
   a. Adiciona ruído gaussiano por candidato com ``σ = (1 - confidence) × base_noise``.
   b. Re-normaliza shares para somarem 1.
   c. Aplica regra do cargo (maioria simples vs 2 turnos).
   d. Conta vitórias.
4. Compila ``win_probability``, ``mean_share_first_round``,
   ``share_ci_95_first_round``, e quando 2 turnos: ``second_round_*``.

Reprodutibilidade: mesmo input + mesmo ``seed`` = mesmo output.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

# Pesos dos fatores eleitorais — espelham _CANDIDACY_STRENGTH_WEIGHTS do
# prediction_service (cópia intencional para isolar a simulação).
_FACTOR_WEIGHTS: dict[str, float] = {
    "vote_intention": 0.14,
    "awareness": 0.10,
    "territorial_strength": 0.10,
    "alliances": 0.08,
    "mobilization": 0.08,
    "digital_sentiment": 0.08,
    "local_agenda_fit": 0.07,
    "operational_efficiency": 0.06,
    "media_coverage": 0.04,
    "declared_funding": 0.03,
}
# Rejection é o único fator invertido — alta rejeição reduz força.
_REJECTION_WEIGHT = 0.15
_REPUTATION_WEIGHT = 0.07

_BASE_NOISE = 0.06  # 6 pontos percentuais quando confidence=0
_TWO_ROUND_OFFICES = {
    "Presidente",
    "Governador",
    "Senador",
}
# Prefeito tem 2 turnos só em municípios > 200k habitantes.
# Heurística do PRD: usuário marca via flag ``two_rounds`` quando aplicável.

DEFAULT_ITERATIONS = 10_000
MAX_ITERATIONS = 50_000
MIN_CANDIDATES = 2
MAX_CANDIDATES = 10


@dataclass
class CandidateInput:
    name: str
    factors: dict[str, float]
    confidence: float = 0.5  # 0..1, usado para escalar o ruído

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CandidateInput":
        return cls(
            name=str(raw.get("name") or "—"),
            factors={
                k: float(v)
                for k, v in (raw.get("factors") or {}).items()
                if isinstance(v, (int, float))
            },
            confidence=max(0.0, min(1.0, float(raw.get("confidence") or 0.5))),
        )


def _candidacy_strength(factors: dict[str, float]) -> float:
    """Score 0..1 a partir dos fatores. Mesma fórmula que
    ``prediction_service._score_from_factors`` (positivos)."""
    if not factors:
        return 0.0
    pos_weighted_sum = 0.0
    pos_total_weight = 0.0
    for k, w in _FACTOR_WEIGHTS.items():
        if k in factors:
            pos_weighted_sum += w * factors[k]
            pos_total_weight += w

    # Penalidade por rejeição/risco reputacional (peso médio).
    neg_value = 0.0
    neg_weight = 0.0
    if "rejection" in factors:
        neg_value += _REJECTION_WEIGHT * factors["rejection"]
        neg_weight += _REJECTION_WEIGHT
    if "reputation_risk" in factors:
        neg_value += _REPUTATION_WEIGHT * factors["reputation_risk"]
        neg_weight += _REPUTATION_WEIGHT

    if pos_total_weight == 0 and neg_weight == 0:
        return 0.0

    pos_norm = (pos_weighted_sum / pos_total_weight / 100.0) if pos_total_weight else 0.5
    neg_norm = (neg_value / neg_weight / 100.0) if neg_weight else 0.0

    # Combinação: força positiva penalizada pela rejeição (até 50% de redução).
    return max(0.0, min(1.0, pos_norm * (1.0 - 0.5 * neg_norm)))


def _normalize(values: list[float]) -> list[float]:
    total = sum(values)
    if total <= 0:
        # fallback uniforme
        n = len(values)
        return [1.0 / n] * n if n else []
    return [v / total for v in values]


def _ci_95(values: list[float]) -> tuple[float, float]:
    """IC 95% percentil (2.5%, 97.5%)."""
    if not values:
        return 0.0, 0.0
    sorted_values = sorted(values)
    n = len(sorted_values)
    lo_idx = max(0, int(round(n * 0.025)) - 1)
    hi_idx = min(n - 1, int(round(n * 0.975)) - 1)
    return sorted_values[lo_idx], sorted_values[hi_idx]


def _aggregated_confidence(candidates: list[CandidateInput]) -> str:
    """Confiança global do experimento — pior dos confidences declarados."""
    if not candidates:
        return "low"
    avg = sum(c.confidence for c in candidates) / len(candidates)
    if avg >= 0.7:
        return "high"
    if avg >= 0.4:
        return "medium"
    return "low"


def _apply_clamps(prob: float) -> float:
    """Clamps semânticos para apresentação: ≥95% e ≤5% (PRD)."""
    if prob >= 0.95:
        return round(prob, 2)
    if prob <= 0.05:
        return round(prob, 2)
    return round(prob, 4)


def simulate_election(
    candidates: list[dict[str, Any]],
    *,
    office: str = "Prefeito",
    two_rounds: bool | None = None,
    iterations: int = DEFAULT_ITERATIONS,
    seed: int | None = None,
) -> dict[str, Any]:
    """Roda o Monte Carlo e devolve o relatório completo.

    Parâmetros
    ----------
    candidates: lista de dicts com ``name``, ``factors`` (12 chaves 0-100),
        ``confidence`` (0..1). Mínimo 2, máximo 10.
    office: usado para inferir 2 turnos quando ``two_rounds`` é None.
    two_rounds: força ON/OFF; quando None, infere por ``office``.
    iterations: número de iterações Monte Carlo (cap em ``MAX_ITERATIONS``).
    seed: seed do RNG; mesmo seed = mesmo resultado.
    """
    if not (MIN_CANDIDATES <= len(candidates) <= MAX_CANDIDATES):
        raise ValueError(
            f"Número de candidatos deve estar entre {MIN_CANDIDATES} e {MAX_CANDIDATES}."
        )
    iterations = max(100, min(MAX_ITERATIONS, int(iterations)))

    parsed = [CandidateInput.from_dict(c) for c in candidates]
    strengths = [_candidacy_strength(c.factors) for c in parsed]
    base_shares = _normalize(strengths)

    if two_rounds is None:
        two_rounds = office in _TWO_ROUND_OFFICES

    rng = random.Random(seed)

    n = len(parsed)
    win_first_round_counts = [0] * n
    win_overall_counts = [0] * n
    second_round_qualifications = [0] * n
    # Vencedor dado que se qualificou — só quando há 2 turnos.
    second_round_wins_given_qualified = [0] * n
    share_samples_first_round: list[list[float]] = [[] for _ in range(n)]

    for _ in range(iterations):
        # Ruído gaussiano por candidato escalado por (1 - confidence).
        noisy = []
        for i, cand in enumerate(parsed):
            sigma = (1.0 - cand.confidence) * _BASE_NOISE
            noise = rng.gauss(0.0, sigma)
            noisy.append(max(0.0, base_shares[i] + noise))
        shares = _normalize(noisy)
        for i, s in enumerate(shares):
            share_samples_first_round[i].append(s)

        first_idx = max(range(n), key=lambda i: shares[i])
        first_share = shares[first_idx]

        if not two_rounds:
            win_first_round_counts[first_idx] += 1
            win_overall_counts[first_idx] += 1
            continue

        # 2 turnos: vence quem >50% no 1º; senão, vai para 2º turno.
        if first_share > 0.5:
            win_first_round_counts[first_idx] += 1
            win_overall_counts[first_idx] += 1
            continue

        # Top 2.
        sorted_idx = sorted(range(n), key=lambda i: shares[i], reverse=True)
        a, b = sorted_idx[0], sorted_idx[1]
        second_round_qualifications[a] += 1
        second_round_qualifications[b] += 1

        # Simulação de 2º turno: shares relativos no top 2 + ruído extra.
        sa = shares[a] / (shares[a] + shares[b])
        # Ruído reduzido (eleitorado já mais polarizado).
        sigma_sr = (
            (1.0 - parsed[a].confidence + 1.0 - parsed[b].confidence)
            * _BASE_NOISE
            * 0.5
        )
        delta = rng.gauss(0.0, sigma_sr)
        sa_final = max(0.0, min(1.0, sa + delta))
        sb_final = 1.0 - sa_final
        if sa_final > sb_final:
            win_overall_counts[a] += 1
            second_round_wins_given_qualified[a] += 1
        else:
            win_overall_counts[b] += 1
            second_round_wins_given_qualified[b] += 1

    results: list[dict[str, Any]] = []
    for i, cand in enumerate(parsed):
        mean_share = sum(share_samples_first_round[i]) / iterations
        ci_lo, ci_hi = _ci_95(share_samples_first_round[i])
        sr_qualifications = second_round_qualifications[i]
        results.append(
            {
                "candidate_name": cand.name,
                "win_probability": _apply_clamps(win_overall_counts[i] / iterations),
                "win_first_round_probability": _apply_clamps(
                    win_first_round_counts[i] / iterations
                ),
                "mean_share_first_round": round(mean_share, 4),
                "share_ci_95_first_round": [round(ci_lo, 4), round(ci_hi, 4)],
                "second_round_qualification_probability": (
                    round(sr_qualifications / iterations, 4) if two_rounds else None
                ),
                "second_round_win_given_qualified": (
                    round(
                        second_round_wins_given_qualified[i] / sr_qualifications, 4
                    )
                    if two_rounds and sr_qualifications > 0
                    else None
                ),
                "input_confidence": cand.confidence,
            }
        )

    return {
        "iterations": iterations,
        "office": office,
        "two_rounds": two_rounds,
        "seed": seed,
        "confidence_level": _aggregated_confidence(parsed),
        "results": results,
    }
