from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.models.scenario import Scenario, ScenarioRun
from app.repositories.scenario_repository import ScenarioRepository
from app.services.scenario_service import ScenarioService


class FakeScenarioRepository(ScenarioRepository):
    def __init__(self) -> None:
        self.scenarios: dict[str, Scenario] = {}
        self.runs: dict[str, ScenarioRun] = {}

    def save(self, instance):
        if isinstance(instance, Scenario):
            self.scenarios[instance.id] = instance
        else:
            self.runs[instance.id] = instance
        return instance

    def add(self, scenario: Scenario) -> Scenario:
        self.scenarios[scenario.id] = scenario
        return scenario

    def get_by_id(self, scenario_id: str) -> Scenario | None:
        return self.scenarios.get(scenario_id)

    def add_run(self, scenario_run: ScenarioRun) -> ScenarioRun:
        self.runs[scenario_run.id] = scenario_run
        return scenario_run

    def get_run_by_id(self, run_id: str) -> ScenarioRun | None:
        return self.runs.get(run_id)

    def get_latest_run_by_scenario_id(self, scenario_id: str) -> ScenarioRun | None:
        items = [r for r in self.runs.values() if r.scenario_id == scenario_id]
        if not items:
            return None
        return sorted(items, key=lambda r: (r.created_at, r.id), reverse=True)[0]

    def list_runs_by_scenario_id(self, scenario_id: str, limit: int = 50) -> list[ScenarioRun]:
        items = [r for r in self.runs.values() if r.scenario_id == scenario_id]
        return sorted(items, key=lambda r: (r.created_at, r.id), reverse=True)[:limit]


def build_scenario(*, fresh: bool = True) -> Scenario:
    return Scenario(
        id=str(uuid4()),
        organization_id="org_demo_001",
        name="Scenario Test",
        description="Scenario for tests",
        baseline_inputs={
            "rejection": 40,
            "vote_intention": 35,
            "awareness": 30,
            "territorial_strength": 50,
            "alliances": 45,
            "mobilization": 38,
        },
        alternative_inputs={
            "rejection": 25,
            "vote_intention": 70,
            "awareness": 68,
            "territorial_strength": 72,
            "alliances": 74,
            "mobilization": 69,
        },
        baseline_score=39.05,
        alternative_score=71.4,
        delta=32.35,
        result_detail="cached result",
        status="completed",
        result_is_stale=not fresh,
        result_stale_reason=None if fresh else "older failure",
        result_stale_at=None if fresh else datetime(2026, 4, 7, 1, 14, 2),
        result_last_refreshed_at=datetime(2026, 4, 7, 0, 51, 21),
        result_source_run_id="run-success-001",
        created_at=datetime(2026, 4, 7, 0, 50, 0),
        updated_at=datetime(2026, 4, 7, 0, 51, 21),
    )


def build_run(
    *,
    scenario_id: str,
    run_id: str,
    status: str,
    created_at: datetime,
    label: str | None = None,
    error_detail: str | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> ScenarioRun:
    return ScenarioRun(
        id=run_id,
        scenario_id=scenario_id,
        status=status,
        label=label,
        error_detail=error_detail,
        created_at=created_at,
        started_at=started_at,
        finished_at=finished_at,
    )


def make_service() -> tuple[ScenarioService, FakeScenarioRepository]:
    service = ScenarioService(db=None)
    repo = FakeScenarioRepository()
    service.repository = repo
    return service, repo


def test_get_run_execution_plan_reuses_fresh_result_without_new_run() -> None:
    service, repo = make_service()
    scenario = build_scenario(fresh=True)
    repo.add(scenario)

    plan = service.get_run_execution_plan(
        scenario_id=scenario.id,
        force_recalculate=False,
        run_label=None,
    )

    assert plan["should_execute"] is False
    assert plan["execution_mode"] == "reused_current_result"
    assert plan["reason"] == "fresh_result_reused"
    assert plan["result_status"] == "fresh"


def test_get_run_execution_plan_forces_new_run_when_requested() -> None:
    service, repo = make_service()
    scenario = build_scenario(fresh=True)
    repo.add(scenario)

    plan = service.get_run_execution_plan(
        scenario_id=scenario.id,
        force_recalculate=True,
        run_label=None,
    )

    assert plan["should_execute"] is True
    assert plan["execution_mode"] == "executed_new_run"
    assert plan["reason"] == "force_recalculate_true"
    assert plan["result_status"] == "fresh"


def test_execute_run_with_simulate_failure_marks_result_stale() -> None:
    service, repo = make_service()
    scenario = build_scenario(fresh=True)
    repo.add(scenario)

    run = build_run(
        scenario_id=scenario.id,
        run_id="run-failure-001",
        status="queued",
        label="simulate_failure",
        created_at=datetime(2026, 4, 7, 1, 14, 2),
    )
    repo.add_run(run)

    result = service.execute_run(run.id)
    updated_scenario = repo.get_by_id(scenario.id)

    assert result.status == "failed"
    assert result.error_detail == "Controlled failure: simulated failure requested for homologation."
    assert updated_scenario is not None
    assert updated_scenario.status == "completed"
    assert updated_scenario.result_is_stale is True
    assert updated_scenario.result_stale_reason == "Controlled failure: simulated failure requested for homologation."
    assert updated_scenario.result_source_run_id == "run-success-001"


def test_list_runs_view_identifies_latest_attempt_and_current_result_source() -> None:
    service, repo = make_service()
    scenario = build_scenario(fresh=False)
    scenario.result_source_run_id = "run-success-001"
    repo.add(scenario)

    success_run = build_run(
        scenario_id=scenario.id,
        run_id="run-success-001",
        status="completed",
        created_at=datetime(2026, 4, 7, 0, 51, 21),
        started_at=datetime(2026, 4, 7, 0, 51, 21),
        finished_at=datetime(2026, 4, 7, 0, 51, 21),
    )
    failed_run = build_run(
        scenario_id=scenario.id,
        run_id="run-failure-002",
        status="failed",
        label="simulate_failure",
        error_detail="Controlled failure: simulated failure requested for homologation.",
        created_at=datetime(2026, 4, 7, 1, 14, 2),
        started_at=datetime(2026, 4, 7, 1, 14, 2),
        finished_at=datetime(2026, 4, 7, 1, 14, 2),
    )

    repo.add_run(success_run)
    repo.add_run(failed_run)

    view = service.list_runs_view(scenario.id, limit=50)

    assert view["contract_version"] == "v2"
    assert view["scenario_status"] == "completed"
    assert view["current_result_status"] == "stale"
    assert view["current_result_source_run_id"] == "run-success-001"
    assert view["run_count"] == 2
    assert view["runs"][0]["run_id"] == "run-failure-002"
    assert view["runs"][0]["is_latest_attempt"] is True
    assert view["runs"][0]["is_current_result_source"] is False
    assert view["runs"][1]["run_id"] == "run-success-001"
    assert view["runs"][1]["is_latest_attempt"] is False
    assert view["runs"][1]["is_current_result_source"] is True