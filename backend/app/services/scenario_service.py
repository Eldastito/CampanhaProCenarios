from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from app.core.scenario_catalog import (
    get_factors_for_type,
    get_factor_keys_for_type,
    get_total_weight_for_type,
)
from app.core.time import utc_now_naive
from app.models.scenario import Scenario, ScenarioRun
from app.repositories.scenario_repository import ScenarioRepository


class ScenarioService:
    def __init__(self, db) -> None:
        self.repository = ScenarioRepository(db)

    def _utcnow(self) -> datetime:
        return utc_now_naive()

    def _normalize_score(self, value: Any) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            score = 0.0

        return max(0.0, min(100.0, score))

    def _has_input_value(self, inputs: dict[str, Any], key: str) -> bool:
        return key in inputs and inputs.get(key) not in (None, "")

    def _classify_score_band(self, score: float | None) -> str:
        if score is None:
            return "unknown"
        if score < 40:
            return "critical"
        if score < 60:
            return "attention"
        if score < 75:
            return "progressing"
        if score < 90:
            return "strong"
        return "advanced"

    def _classify_delta_direction(self, delta: float | None) -> str:
        if delta is None:
            return "unknown"
        if delta >= 15:
            return "strong_gain"
        if delta >= 5:
            return "moderate_gain"
        if delta > 0:
            return "slight_gain"
        if delta == 0:
            return "neutral"
        return "negative"

    def _classify_confidence_level(
        self,
        baseline_coverage_percent: float,
        alternative_coverage_percent: float,
    ) -> str:
        reference = min(baseline_coverage_percent, alternative_coverage_percent)

        if reference >= 85:
            return "high"
        if reference >= 60:
            return "medium"
        return "low"

    def _calculate_score(
        self, inputs: dict[str, Any] | None, scenario_type: str = "electoral"
    ) -> tuple[float, str]:
        inputs = inputs or {}
        scenario_factors = get_factors_for_type(scenario_type)

        weighted_sum = 0.0
        total_weight = 0.0
        factors: list[str] = []

        for factor in scenario_factors:
            value = self._normalize_score(inputs.get(factor.key, 0))
            weighted_sum += value * factor.weight
            total_weight += factor.weight
            factors.append(f"{factor.key}={value:.1f}")

        final_score = round(weighted_sum / total_weight if total_weight else 0.0, 2)
        detail = "Factors used: " + ", ".join(factors)
        return final_score, detail

    def _build_input_profile(
        self, inputs: dict[str, Any] | None, scenario_type: str = "electoral"
    ) -> dict:
        inputs = inputs or {}
        scenario_factors = get_factors_for_type(scenario_type)
        factor_keys = get_factor_keys_for_type(scenario_type)
        total_weight = get_total_weight_for_type(scenario_type)

        weighted_sum = 0.0
        normalized_weighted_sum = 0.0
        provided_weight = 0.0

        provided_factors: list[str] = []
        missing_factors: list[str] = []
        weakest_provided: list[tuple[float, str, str, str]] = []

        for factor in scenario_factors:
            is_present = self._has_input_value(inputs, factor.key)
            value = self._normalize_score(inputs.get(factor.key, 0))

            weighted_sum += value * factor.weight

            if is_present:
                provided_weight += factor.weight
                normalized_weighted_sum += value * factor.weight
                provided_factors.append(factor.key)
                weakest_provided.append(
                    (
                        value,
                        factor.key,
                        factor.label,
                        factor.recommendation_hint,
                    )
                )
            else:
                missing_factors.append(factor.key)

        unknown_factors = sorted(
            [key for key in inputs.keys() if key not in factor_keys]
        )

        conservative_score = round(weighted_sum / total_weight, 2)
        normalized_score = (
            round(normalized_weighted_sum / provided_weight, 2)
            if provided_weight > 0
            else None
        )
        coverage_percent = round((provided_weight / total_weight) * 100, 2)

        weakest_provided.sort(key=lambda item: item[0])

        return {
            "conservative_score": conservative_score,
            "normalized_score": normalized_score,
            "coverage_percent": coverage_percent,
            "provided_factors": provided_factors,
            "missing_factors": missing_factors,
            "unknown_factors": unknown_factors,
            "weakest_provided": weakest_provided[:3],
        }

    def _build_factor_breakdown(
        self,
        baseline_inputs: dict[str, Any] | None,
        alternative_inputs: dict[str, Any] | None,
        scenario_type: str = "electoral",
    ) -> list[dict]:
        baseline_inputs = baseline_inputs or {}
        alternative_inputs = alternative_inputs or {}
        scenario_factors = get_factors_for_type(scenario_type)

        rows: list[dict] = []

        for factor in scenario_factors:
            baseline_present = self._has_input_value(baseline_inputs, factor.key)
            alternative_present = self._has_input_value(alternative_inputs, factor.key)

            baseline_value = (
                self._normalize_score(baseline_inputs.get(factor.key))
                if baseline_present
                else None
            )
            alternative_value = (
                self._normalize_score(alternative_inputs.get(factor.key))
                if alternative_present
                else None
            )

            if baseline_value is not None and alternative_value is not None:
                delta = round(alternative_value - baseline_value, 2)
                if delta > 0:
                    comparison_status = "improved"
                elif delta < 0:
                    comparison_status = "declined"
                else:
                    comparison_status = "unchanged"
            else:
                delta = None
                comparison_status = "insufficient_data"

            rows.append(
                {
                    "factor": factor.key,
                    "label": factor.label,
                    "weight": factor.weight,
                    "baseline_value": baseline_value,
                    "alternative_value": alternative_value,
                    "delta": delta,
                    "baseline_present": baseline_present,
                    "alternative_present": alternative_present,
                    "comparison_status": comparison_status,
                }
            )

        return rows

    def _build_interpretation(
        self,
        *,
        baseline_score: float,
        alternative_score: float,
        delta: float,
        baseline_profile: dict,
        alternative_profile: dict,
    ) -> dict:
        baseline_band = self._classify_score_band(baseline_score)
        alternative_band = self._classify_score_band(alternative_score)
        delta_direction = self._classify_delta_direction(delta)
        confidence_level = self._classify_confidence_level(
            baseline_profile["coverage_percent"],
            alternative_profile["coverage_percent"],
        )

        warnings: list[str] = []
        if baseline_profile["missing_factors"] or alternative_profile["missing_factors"]:
            warnings.append(
                "Raw scores are conservative because missing factors are treated as zero."
            )
        if (
            baseline_profile["unknown_factors"]
            or alternative_profile["unknown_factors"]
        ):
            warnings.append(
                "Some input keys are unknown to the model and were ignored in factor analysis."
            )

        summary = (
            f"Alternative scenario shows {delta_direction} versus baseline. "
            f"Baseline band is {baseline_band}, alternative band is {alternative_band}, "
            f"and evidence confidence is {confidence_level}."
        )

        return {
            "baseline_band": baseline_band,
            "alternative_band": alternative_band,
            "delta_direction": delta_direction,
            "confidence_level": confidence_level,
            "summary": summary,
            "warnings": warnings,
        }

    def _build_recommendations(
        self,
        *,
        baseline_profile: dict,
        alternative_profile: dict,
        delta: float,
    ) -> list[dict]:
        recommendations: list[dict] = []

        combined_missing = sorted(
            set(baseline_profile["missing_factors"])
            | set(alternative_profile["missing_factors"])
        )

        if combined_missing:
            recommendations.append(
                {
                    "priority": "high",
                    "type": "data_quality",
                    "title": "Complete missing factors",
                    "detail": (
                        "Provide values for the missing factors to improve decision confidence: "
                        + ", ".join(combined_missing)
                    ),
                }
            )

        for _, key, label, hint in baseline_profile["weakest_provided"]:
            recommendations.append(
                {
                    "priority": "medium",
                    "type": "improvement",
                    "title": f"Improve {label}",
                    "detail": f"Baseline is weak on {label}; prioritize actions to {hint}.",
                }
            )

        if delta <= 0:
            recommendations.append(
                {
                    "priority": "high",
                    "type": "scenario_design",
                    "title": "Review alternative scenario assumptions",
                    "detail": (
                        "The proposed alternative does not outperform the baseline. "
                        "Review assumptions, sequencing, and execution priorities."
                    ),
                }
            )

        unique: list[dict] = []
        seen_titles: set[str] = set()

        for item in recommendations:
            if item["title"] in seen_titles:
                continue
            seen_titles.add(item["title"])
            unique.append(item)

        return unique[:4]

    def _build_analysis_bundle(self, scenario: Scenario) -> dict:
        stype = getattr(scenario, "scenario_type", "electoral") or "electoral"
        baseline_profile = self._build_input_profile(scenario.baseline_inputs, stype)
        alternative_profile = self._build_input_profile(scenario.alternative_inputs, stype)

        baseline_score = (
            scenario.baseline_score
            if scenario.baseline_score is not None
            else baseline_profile["conservative_score"]
        )
        alternative_score = (
            scenario.alternative_score
            if scenario.alternative_score is not None
            else alternative_profile["conservative_score"]
        )
        delta = (
            scenario.delta
            if scenario.delta is not None
            else round(alternative_score - baseline_score, 2)
        )

        baseline_normalized = baseline_profile["normalized_score"]
        alternative_normalized = alternative_profile["normalized_score"]
        normalized_delta = (
            round(alternative_normalized - baseline_normalized, 2)
            if baseline_normalized is not None and alternative_normalized is not None
            else None
        )

        interpretation = self._build_interpretation(
            baseline_score=baseline_score,
            alternative_score=alternative_score,
            delta=delta,
            baseline_profile=baseline_profile,
            alternative_profile=alternative_profile,
        )

        return {
            "baseline_profile": baseline_profile,
            "alternative_profile": alternative_profile,
            "normalized_result": {
                "baseline_score": baseline_normalized,
                "alternative_score": alternative_normalized,
                "delta": normalized_delta,
                "method": "weighted_average_of_provided_factors",
            },
            "input_quality": {
                "baseline_coverage_percent": baseline_profile["coverage_percent"],
                "alternative_coverage_percent": alternative_profile["coverage_percent"],
                "baseline_missing_factors": baseline_profile["missing_factors"],
                "alternative_missing_factors": alternative_profile["missing_factors"],
                "baseline_unknown_factors": baseline_profile["unknown_factors"],
                "alternative_unknown_factors": alternative_profile["unknown_factors"],
            },
            "interpretation": interpretation,
            "factor_breakdown": self._build_factor_breakdown(
                scenario.baseline_inputs,
                scenario.alternative_inputs,
                stype,
            ),
            "recommendations": self._build_recommendations(
                baseline_profile=baseline_profile,
                alternative_profile=alternative_profile,
                delta=delta,
            ),
        }

    def _has_result_snapshot(self, scenario: Scenario) -> bool:
        return any(
            value is not None
            for value in [
                scenario.baseline_score,
                scenario.alternative_score,
                scenario.delta,
                scenario.result_detail,
            ]
        )

    def _apply_result_snapshot(
        self,
        scenario: Scenario,
        *,
        source_run_id: str | None,
    ) -> Scenario:
        stype = getattr(scenario, "scenario_type", "electoral") or "electoral"
        baseline_score, baseline_detail = self._calculate_score(scenario.baseline_inputs, stype)
        alternative_score, alternative_detail = self._calculate_score(
            scenario.alternative_inputs, stype
        )
        delta = round(alternative_score - baseline_score, 2)

        scenario.baseline_score = baseline_score
        scenario.alternative_score = alternative_score
        scenario.delta = delta
        scenario.result_detail = (
            f"baseline={baseline_score:.2f}; "
            f"alternative={alternative_score:.2f}; "
            f"delta={delta:.2f}. "
            f"Baseline -> {baseline_detail}. "
            f"Alternative -> {alternative_detail}."
        )

        scenario.result_is_stale = False
        scenario.result_stale_reason = None
        scenario.result_stale_at = None
        scenario.result_last_refreshed_at = self._utcnow()
        scenario.result_source_run_id = source_run_id

        return scenario

    def _serialize_datetime(self, value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    def _get_result_status(self, scenario: Scenario) -> str:
        if not self._has_result_snapshot(scenario):
            return "unavailable"

        return "stale" if scenario.result_is_stale else "fresh"

    def _serialize_latest_run(self, latest_run: ScenarioRun | None) -> dict | None:
        if latest_run is None:
            return None

        return {
            "run_id": latest_run.id,
            "status": latest_run.status,
            "label": latest_run.label,
            "error_detail": latest_run.error_detail,
            "created_at": self._serialize_datetime(latest_run.created_at),
            "started_at": self._serialize_datetime(latest_run.started_at),
            "finished_at": self._serialize_datetime(latest_run.finished_at),
        }

    def _serialize_scenario_summary(self, scenario: Scenario) -> dict:
        latest_run = self.repository.get_latest_run_by_scenario_id(scenario.id)
        analysis = self._build_analysis_bundle(scenario)

        return {
            "scenario_id": scenario.id,
            "organization_id": scenario.organization_id,
            "name": scenario.name,
            "description": scenario.description,
            "scenario_type": getattr(scenario, "scenario_type", "electoral") or "electoral",
            "status": scenario.status,
            "result_status": self._get_result_status(scenario),
            "baseline_score": scenario.baseline_score,
            "alternative_score": scenario.alternative_score,
            "delta": scenario.delta,
            "baseline_normalized_score": analysis["normalized_result"]["baseline_score"],
            "alternative_normalized_score": analysis["normalized_result"]["alternative_score"],
            "normalized_delta": analysis["normalized_result"]["delta"],
            "baseline_band": analysis["interpretation"]["baseline_band"],
            "alternative_band": analysis["interpretation"]["alternative_band"],
            "delta_direction": analysis["interpretation"]["delta_direction"],
            "confidence_level": analysis["interpretation"]["confidence_level"],
            "baseline_coverage_percent": analysis["input_quality"]["baseline_coverage_percent"],
            "alternative_coverage_percent": analysis["input_quality"]["alternative_coverage_percent"],
            "result_last_refreshed_at": self._serialize_datetime(
                scenario.result_last_refreshed_at
            ),
            "result_source_run_id": scenario.result_source_run_id,
            "latest_run": self._serialize_latest_run(latest_run),
            "created_at": self._serialize_datetime(scenario.created_at),
            "updated_at": self._serialize_datetime(scenario.updated_at),
        }

    def create_scenario(
        self,
        organization_id: str,
        name: str,
        description: str | None = None,
        baseline_inputs: dict[str, Any] | None = None,
        alternative_inputs: dict[str, Any] | None = None,
        scenario_type: str = "electoral",
    ) -> Scenario:
        organization = self.repository.get_organization_by_id(organization_id)
        if not organization:
            raise ValueError("Organization not found.")

        scenario = Scenario(
            id=str(uuid4()),
            organization_id=organization_id,
            name=name,
            description=description,
            scenario_type=scenario_type,
            baseline_inputs=baseline_inputs or {},
            alternative_inputs=alternative_inputs or {},
            status="draft",
        )

        scenario = self._apply_result_snapshot(scenario, source_run_id=None)
        return self.repository.add(scenario)

    def list_scenarios_view(
        self,
        organization_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        scenarios = self.repository.list_scenarios(
            organization_id=organization_id,
            limit=limit,
            offset=offset,
        )

        return {
            "contract_version": "v2",
            "organization_id": organization_id,
            "count": len(scenarios),
            "items": [self._serialize_scenario_summary(item) for item in scenarios],
        }

    def get_scenario_view(self, scenario_id: str) -> dict:
        scenario = self.repository.get_by_id(scenario_id)
        if not scenario:
            raise ValueError("Scenario not found.")

        return {
            "contract_version": "v2",
            **self._serialize_scenario_summary(scenario),
        }

    def queue_run(self, scenario_id: str, run_label: str | None = None) -> ScenarioRun:
        scenario = self.repository.get_by_id(scenario_id)
        if not scenario:
            raise ValueError("Scenario not found.")

        scenario.status = "queued"
        self.repository.save(scenario)

        scenario_run = ScenarioRun(
            id=str(uuid4()),
            scenario_id=scenario_id,
            status="queued",
            label=run_label,
        )
        return self.repository.add_run(scenario_run)

    def start_run(self, run_id: str) -> ScenarioRun:
        run = self.repository.get_run_by_id(run_id)
        if not run:
            raise ValueError("Run not found.")

        scenario = self.repository.get_by_id(run.scenario_id)
        if not scenario:
            raise ValueError("Scenario not found.")

        run.status = "running"
        run.started_at = self._utcnow()
        self.repository.save(run)

        scenario.status = "running"
        self.repository.save(scenario)

        return run

    def complete_run_success(self, run_id: str) -> ScenarioRun:
        run = self.repository.get_run_by_id(run_id)
        if not run:
            raise ValueError("Run not found.")

        scenario = self.repository.get_by_id(run.scenario_id)
        if not scenario:
            raise ValueError("Scenario not found.")

        scenario = self._apply_result_snapshot(scenario, source_run_id=run.id)
        scenario.status = "completed"
        self.repository.save(scenario)

        run.status = "completed"
        run.error_detail = None
        run.finished_at = self._utcnow()
        self.repository.save(run)

        return run

    def fail_run(self, run_id: str, error_detail: str) -> ScenarioRun:
        run = self.repository.get_run_by_id(run_id)
        if not run:
            raise ValueError("Run not found.")

        scenario = self.repository.get_by_id(run.scenario_id)
        if not scenario:
            raise ValueError("Scenario not found.")

        now = self._utcnow()

        run.status = "failed"
        run.error_detail = error_detail
        run.finished_at = now
        self.repository.save(run)

        if self._has_result_snapshot(scenario):
            scenario.result_is_stale = True
            scenario.result_stale_reason = error_detail
            scenario.result_stale_at = now
            scenario.status = "completed"
        else:
            scenario.status = "failed"

        self.repository.save(scenario)
        return run

    def execute_run(self, run_id: str) -> ScenarioRun:
        run = self.start_run(run_id)

        if run.label == "simulate_failure":
            return self.fail_run(
                run_id=run.id,
                error_detail="Controlled failure: simulated failure requested for homologation.",
            )

        return self.complete_run_success(run_id=run.id)

    def get_results_view(self, scenario_id: str) -> dict:
        scenario = self.repository.get_by_id(scenario_id)
        if not scenario:
            raise ValueError("Scenario not found.")

        latest_run = self.repository.get_latest_run_by_scenario_id(scenario_id)
        analysis = self._build_analysis_bundle(scenario)

        scenario_status = scenario.status
        run_status = latest_run.status if latest_run else None
        result_status = self._get_result_status(scenario)

        legacy_status = run_status if run_status else scenario_status

        return {
            "contract_version": "v2",
            "scenario_id": scenario.id,
            "legacy_status": legacy_status,
            "scenario_status": scenario_status,
            "run_status": run_status,
            "result_status": result_status,
            "result_meta": {
                "is_stale": scenario.result_is_stale,
                "stale_at": self._serialize_datetime(scenario.result_stale_at),
                "stale_reason": scenario.result_stale_reason,
                "last_refreshed_at": self._serialize_datetime(
                    scenario.result_last_refreshed_at
                ),
                "result_source_run_id": scenario.result_source_run_id,
                "latest_run_id": latest_run.id if latest_run else None,
                "latest_run_label": latest_run.label if latest_run else None,
                "latest_run_error_detail": (
                    latest_run.error_detail if latest_run else None
                ),
                "latest_run_started_at": (
                    self._serialize_datetime(latest_run.started_at)
                    if latest_run
                    else None
                ),
                "latest_run_finished_at": (
                    self._serialize_datetime(latest_run.finished_at)
                    if latest_run
                    else None
                ),
                "score_method": "conservative_weighted_score_missing_as_zero",
                "normalized_score_method": "weighted_average_of_provided_factors",
            },
            "result": {
                "baseline_score": scenario.baseline_score,
                "alternative_score": scenario.alternative_score,
                "delta": scenario.delta,
                "detail": scenario.result_detail,
            },
            "normalized_result": analysis["normalized_result"],
            "input_quality": analysis["input_quality"],
            "interpretation": analysis["interpretation"],
            "factor_breakdown": analysis["factor_breakdown"],
            "recommendations": analysis["recommendations"],
        }

    def list_runs_view(self, scenario_id: str, limit: int = 50) -> dict:
        scenario = self.repository.get_by_id(scenario_id)
        if not scenario:
            raise ValueError("Scenario not found.")

        latest_run = self.repository.get_latest_run_by_scenario_id(scenario_id)
        runs = self.repository.list_runs_by_scenario_id(scenario_id, limit=limit)

        result_status = self._get_result_status(scenario)

        serialized_runs: list[dict] = []
        for run in runs:
            serialized_runs.append(
                {
                    "run_id": run.id,
                    "status": run.status,
                    "label": run.label,
                    "error_detail": run.error_detail,
                    "created_at": self._serialize_datetime(run.created_at),
                    "started_at": self._serialize_datetime(run.started_at),
                    "finished_at": self._serialize_datetime(run.finished_at),
                    "is_latest_attempt": latest_run.id == run.id if latest_run else False,
                    "is_current_result_source": scenario.result_source_run_id == run.id,
                }
            )

        return {
            "contract_version": "v2",
            "scenario_id": scenario.id,
            "scenario_status": scenario.status,
            "current_result_status": result_status,
            "current_result_source_run_id": scenario.result_source_run_id,
            "run_count": len(serialized_runs),
            "runs": serialized_runs,
        }

    def get_run_execution_plan(
        self,
        scenario_id: str,
        *,
        force_recalculate: bool,
        run_label: str | None,
    ) -> dict:
        scenario = self.repository.get_by_id(scenario_id)
        if not scenario:
            raise ValueError("Scenario not found.")

        result_status = self._get_result_status(scenario)

        if run_label:
            return {
                "should_execute": True,
                "execution_mode": "executed_new_run",
                "reason": "explicit_run_label",
                "result_status": result_status,
            }

        if force_recalculate:
            return {
                "should_execute": True,
                "execution_mode": "executed_new_run",
                "reason": "force_recalculate_true",
                "result_status": result_status,
            }

        if result_status in ("stale", "unavailable"):
            return {
                "should_execute": True,
                "execution_mode": "executed_new_run",
                "reason": f"result_status_{result_status}",
                "result_status": result_status,
            }

        return {
            "should_execute": False,
            "execution_mode": "reused_current_result",
            "reason": "fresh_result_reused",
            "result_status": result_status,
        }

    def compare_scenarios_view(self, scenario_a_id: str, scenario_b_id: str) -> dict:
        """Return a side-by-side comparison of two scenarios."""
        scenario_a = self.repository.get_by_id(scenario_a_id)
        if not scenario_a:
            raise ValueError(f"Scenario '{scenario_a_id}' not found.")

        scenario_b = self.repository.get_by_id(scenario_b_id)
        if not scenario_b:
            raise ValueError(f"Scenario '{scenario_b_id}' not found.")

        summary_a = self._serialize_scenario_summary(scenario_a)
        summary_b = self._serialize_scenario_summary(scenario_b)

        score_a = summary_a.get("baseline_normalized_score")
        score_b = summary_b.get("baseline_normalized_score")
        alt_a = summary_a.get("alternative_normalized_score")
        alt_b = summary_b.get("alternative_normalized_score")

        def _cross_delta(x: float | None, y: float | None) -> float | None:
            return round(y - x, 4) if (x is not None and y is not None) else None

        def _winner(delta: float | None) -> str:
            if delta is None:
                return "unknown"
            if delta > 1.0:
                return "b"
            if delta < -1.0:
                return "a"
            return "tie"

        base_delta = _cross_delta(score_a, score_b)
        alt_delta = _cross_delta(alt_a, alt_b)

        return {
            "contract_version": "v2",
            "comparison_type": "scenario_vs_scenario",
            "scenario_a": summary_a,
            "scenario_b": summary_b,
            "cross_comparison": {
                "baseline_score_a": score_a,
                "baseline_score_b": score_b,
                "baseline_delta_b_minus_a": base_delta,
                "baseline_winner": _winner(base_delta),
                "alternative_score_a": alt_a,
                "alternative_score_b": alt_b,
                "alternative_delta_b_minus_a": alt_delta,
                "alternative_winner": _winner(alt_delta),
            },
        }