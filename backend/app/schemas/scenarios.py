from pydantic import BaseModel, Field


class ScenarioCreateRequest(BaseModel):
    organization_id: str
    name: str
    description: str | None = None
    baseline_inputs: dict = Field(default_factory=dict)
    alternative_inputs: dict = Field(default_factory=dict)


class ScenarioRunRequest(BaseModel):
    run_label: str | None = None
    force_recalculate: bool = False


class ScenarioResponse(BaseModel):
    scenario_id: str
    organization_id: str
    name: str
    description: str | None = None
    status: str


class ScenarioRunResponse(BaseModel):
    scenario_id: str
    run_id: str
    status: str
    detail: str
    force_recalculate: bool = False
    run_label: str | None = None
