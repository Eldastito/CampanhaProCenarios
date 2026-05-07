"""Prediction scoring engine.

Computes acceptance probability and evasion risk based on scenario factor
values.  Factor values use a 0–100 scale (same as ScenarioFactor inputs).

When factors are not provided directly, the engine attempts to read them
from the latest FORGE snapshot for the organisation.  If no data is
available, it returns a low-confidence default.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.prediction import Prediction
from app.repositories.forge_ingest_repository import ForgeIngestRepository
from app.repositories.prediction_repository import PredictionRepository

# ---------------------------------------------------------------------------
# Acceptance prediction
# ---------------------------------------------------------------------------
# Higher factor values → higher acceptance probability.
_ACCEPTANCE_WEIGHTS: dict[str, float] = {
    "training": 0.25,
    "digital_maturity": 0.20,
    "teacher_adoption": 0.25,
    "institutional_support": 0.20,
    "engagement": 0.10,
}

# ---------------------------------------------------------------------------
# Evasion-risk prediction
# ---------------------------------------------------------------------------
# Higher factor values → lower evasion risk  (score is inverted at the end).
_EVASION_WEIGHTS: dict[str, float] = {
    "engagement": 0.35,
    "infrastructure": 0.25,
    "institutional_support": 0.20,
    "teacher_adoption": 0.20,
}

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
    if value >= 0.80:
        return "High acceptance probability — strong organisational readiness detected."
    if value >= 0.60:
        return "Moderate acceptance probability — focus on weaker factors to improve."
    if value >= 0.40:
        return "Low-moderate acceptance — significant gaps require attention."
    return "Low acceptance probability — major organisational readiness gaps detected."


def _interpret_evasion(value: float) -> str:
    if value >= 0.60:
        return "High evasion risk — urgent intervention required in low-scored areas."
    if value >= 0.40:
        return "Moderate evasion risk — targeted improvements can reduce dropout."
    if value >= 0.20:
        return "Low-moderate evasion risk — monitor engagement and infrastructure gaps."
    return "Low evasion risk — organisation shows strong student retention indicators."


def _extract_factors_from_snapshot(snapshot_payload: dict) -> dict[str, float]:
    """Best-effort extraction of factor values from a FORGE snapshot payload.

    FORGE snapshots may include a top-level ``factors`` dict or individual
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
        self._ingest_repo = ForgeIngestRepository(db)

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
                    "No factor data provided and no FORGE snapshot found for this organisation.",
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
                    "No factor data provided and no FORGE snapshot found for this organisation.",
                    "Pass factor values in the request body for an immediate prediction.",
                ],
            )
        else:
            value, confidence, explanation = _score_from_factors(
                effective_factors, _EVASION_WEIGHTS, invert=True
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
        2. Latest FORGE snapshot for the organisation.
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
