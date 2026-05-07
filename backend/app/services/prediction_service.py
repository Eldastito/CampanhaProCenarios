"""Prediction scoring engine.

Computes acceptance probability and evasion risk based on scenario factor
values.  Factor values use a 0–100 scale (same as ScenarioFactor inputs).

When factors are not provided directly, the engine attempts to read them
from the latest CampanhaPro snapshot for the organisation.  If no data is
available, it returns a low-confidence default.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.prediction import Prediction
from app.repositories.campanhapro_ingest_repository import CampanhaProIngestRepository
from app.repositories.prediction_repository import PredictionRepository

# ---------------------------------------------------------------------------
# Candidacy strength prediction (substitui acceptance)
# ---------------------------------------------------------------------------
# Higher factor values → higher candidacy strength.
# Pesos do PRD eleitoral. Rejeição é o único fator invertido aqui (alta
# rejeição reduz a força da candidatura) — invertemos na hora de pontuar.
_CANDIDACY_STRENGTH_WEIGHTS: dict[str, float] = {
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

# ---------------------------------------------------------------------------
# Rejection-risk prediction (substitui evasion-risk)
# ---------------------------------------------------------------------------
# Mede o risco de rejeição/desgaste reputacional.
# Aqui valores ALTOS de cada fator significam MAIS risco. O scoring NÃO inverte.
_REJECTION_RISK_WEIGHTS: dict[str, float] = {
    "rejection": 0.55,
    "reputation_risk": 0.45,
}

# Aliases para retrocompatibilidade com código que ainda referencia os nomes antigos.
_ACCEPTANCE_WEIGHTS = _CANDIDACY_STRENGTH_WEIGHTS
_EVASION_WEIGHTS = _REJECTION_RISK_WEIGHTS

_NO_DATA_VALUE = 0.50
_NO_DATA_CONFIDENCE = 0.05


def _score_from_factors(
    factors: dict[str, float],
    weights: dict[str, float],
    invert: bool = False,
) -> tuple[float, float, list[str]]:
    """Return (value, confidence, explanation_lines) for *factors* against *weights*.

    confidence is the sum of the weights of provided factors, capped at 1.0.
    value is the weighted-average normalised to [0, 1] (inverted if requested).
    """
    relevant = {k: float(v) for k, v in factors.items() if k in weights}

    if not relevant:
        return (
            _NO_DATA_VALUE,
            _NO_DATA_CONFIDENCE,
            ["None of the provided factors are relevant to this prediction type."],
        )

    total_weight = sum(weights[k] for k in relevant)
    weighted_sum = sum(weights[k] * v for k, v in relevant.items())
    normalised = (weighted_sum / total_weight) / 100.0

    value = round(1.0 - normalised if invert else normalised, 4)
    confidence = round(min(total_weight, 1.0), 4)

    explanation: list[str] = []

    missing = [k for k in weights if k not in relevant]
    if missing:
        explanation.append(
            f"Partial data ({len(relevant)}/{len(weights)} factors supplied). "
            f"Missing: {', '.join(missing)}."
        )

    return value, confidence, explanation


def _interpret_acceptance(value: float) -> str:
    """Interpretação de força da candidatura (acceptance == candidacy strength)."""
    if value >= 0.80:
        return "Candidatura forte — fatores eleitorais favoráveis e bem distribuídos."
    if value >= 0.60:
        return "Candidatura competitiva — atuar nos fatores mais fracos para consolidar."
    if value >= 0.40:
        return "Candidatura intermediária — lacunas relevantes exigem plano de ação."
    return "Candidatura frágil — gaps significativos em fatores eleitorais centrais."


def _interpret_evasion(value: float) -> str:
    """Interpretação de risco de rejeição (evasion == rejection risk)."""
    if value >= 0.60:
        return "Risco alto de rejeição — intervenção urgente em narrativa, reputação e mídia."
    if value >= 0.40:
        return "Risco moderado de rejeição — atuação direcionada pode mitigar desgaste."
    if value >= 0.20:
        return "Risco baixo-moderado de rejeição — monitorar sentimento e crises potenciais."
    return "Risco baixo de rejeição — campanha demonstra blindagem reputacional adequada."


def _extract_factors_from_snapshot(snapshot_payload: dict) -> dict[str, float]:
    """Best-effort extraction of factor values from a CampanhaPro snapshot payload.

    CampanhaPro snapshots may include a top-level ``factors`` dict or individual
    numeric keys matching scenario factor names.  Unknown keys are ignored.
    """
    from app.core.scenario_catalog import SCENARIO_FACTOR_KEYS

    factors: dict[str, float] = {}

    # Attempt 1: payload has a nested "factors" dict
    raw = snapshot_payload.get("factors", {})
    if isinstance(raw, dict):
        for key in SCENARIO_FACTOR_KEYS:
            if key in raw:
                try:
                    factors[key] = float(raw[key])
                except (TypeError, ValueError):
                    pass

    # Attempt 2: factor keys at the top level of payload
    if not factors:
        for key in SCENARIO_FACTOR_KEYS:
            if key in snapshot_payload:
                try:
                    factors[key] = float(snapshot_payload[key])
                except (TypeError, ValueError):
                    pass

    return factors


class PredictionService:
    def __init__(self, db: Session) -> None:
        self._pred_repo = PredictionRepository(db)
        self._ingest_repo = CampanhaProIngestRepository(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict_acceptance(
        self,
        organization_id: str,
        scope_type: str,
        scope_id: str,
        factors: dict[str, float] | None,
    ) -> tuple[float, float, list[str]]:
        """Compute acceptance probability and persist the result."""
        effective_factors = self._resolve_factors(organization_id, factors, "acceptance")

        if effective_factors is None:
            value, confidence, explanation = (
                _NO_DATA_VALUE,
                _NO_DATA_CONFIDENCE,
                [
                    "No factor data provided and no CampanhaPro snapshot found for this organisation.",
                    "Pass factor values in the request body for an immediate prediction.",
                ],
            )
        else:
            value, confidence, explanation = _score_from_factors(
                effective_factors, _ACCEPTANCE_WEIGHTS, invert=False
            )
            explanation.append(_interpret_acceptance(value))

        self.save_prediction(
            organization_id=organization_id,
            prediction_type="acceptance",
            scope_type=scope_type,
            scope_id=scope_id,
            value=value,
            confidence=confidence,
        )
        return value, confidence, explanation

    def predict_evasion_risk(
        self,
        organization_id: str,
        scope_type: str,
        scope_id: str,
        factors: dict[str, float] | None,
    ) -> tuple[float, float, list[str]]:
        """Compute evasion risk and persist the result."""
        effective_factors = self._resolve_factors(organization_id, factors, "evasion_risk")

        if effective_factors is None:
            value, confidence, explanation = (
                _NO_DATA_VALUE,
                _NO_DATA_CONFIDENCE,
                [
                    "No factor data provided and no CampanhaPro snapshot found for this organisation.",
                    "Pass factor values in the request body for an immediate prediction.",
                ],
            )
        else:
            # Para risco de rejeição, valores altos = mais risco. Sem inverter.
            value, confidence, explanation = _score_from_factors(
                effective_factors, _EVASION_WEIGHTS, invert=False
            )
            explanation.append(_interpret_evasion(value))

        self.save_prediction(
            organization_id=organization_id,
            prediction_type="evasion-risk",
            scope_type=scope_type,
            scope_id=scope_id,
            value=value,
            confidence=confidence,
        )
        return value, confidence, explanation

    def save_prediction(
        self,
        organization_id: str,
        prediction_type: str,
        scope_type: str,
        scope_id: str,
        value: float,
        confidence: float,
    ) -> Prediction:
        prediction = Prediction(
            id=str(uuid4()),
            organization_id=organization_id,
            prediction_type=prediction_type,
            scope_type=scope_type,
            scope_id=scope_id,
            value=value,
            confidence=confidence,
        )
        return self._pred_repo.add(prediction)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_factors(
        self,
        organization_id: str,
        factors: dict[str, float] | None,
        prediction_type: str,
    ) -> dict[str, float] | None:
        """Return factor dict to use for scoring.

        Priority:
        1. Factors provided explicitly in the request.
        2. Latest CampanhaPro snapshot for the organisation.
        3. None → caller returns a low-confidence default.
        """
        if factors:
            return factors

        snapshot = self._ingest_repo.get_latest_snapshot_for_org(
            organization_id=organization_id,
            snapshot_type=None,
        )
        if snapshot is not None:
            extracted = _extract_factors_from_snapshot(snapshot.payload)
            if extracted:
                return extracted

        return None
