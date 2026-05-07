from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.scenario import Scenario, ScenarioRun


class ScenarioRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, instance):
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def add(self, scenario: Scenario) -> Scenario:
        return self.save(scenario)

    def get_by_id(self, scenario_id: str) -> Scenario | None:
        return self.db.query(Scenario).filter(Scenario.id == scenario_id).first()

    def list_scenarios(
        self,
        organization_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Scenario]:
        query = self.db.query(Scenario)

        if organization_id:
            query = query.filter(Scenario.organization_id == organization_id)

        return (
            query.order_by(Scenario.created_at.desc(), Scenario.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_organization_by_id(self, organization_id: str) -> Organization | None:
        return (
            self.db.query(Organization)
            .filter(Organization.id == organization_id)
            .first()
        )

    def add_run(self, scenario_run: ScenarioRun) -> ScenarioRun:
        return self.save(scenario_run)

    def get_run_by_id(self, run_id: str) -> ScenarioRun | None:
        return self.db.query(ScenarioRun).filter(ScenarioRun.id == run_id).first()

    def get_latest_run_by_scenario_id(self, scenario_id: str) -> ScenarioRun | None:
        return (
            self.db.query(ScenarioRun)
            .filter(ScenarioRun.scenario_id == scenario_id)
            .order_by(ScenarioRun.created_at.desc(), ScenarioRun.id.desc())
            .first()
        )

    def list_runs_by_scenario_id(
        self,
        scenario_id: str,
        limit: int = 50,
    ) -> list[ScenarioRun]:
        return (
            self.db.query(ScenarioRun)
            .filter(ScenarioRun.scenario_id == scenario_id)
            .order_by(ScenarioRun.created_at.desc(), ScenarioRun.id.desc())
            .limit(limit)
            .all()
        )