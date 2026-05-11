"""Endpoint Claude Managed (Fase 6 PRD v2).

POST /api/v1/political/projects/{project_id}/scenarios/generate
body: { prompt, agents_to_consult?: [string] }
→ 200 com cenário + análises por agente, audit log persistido.

Erros possíveis:
- 404: projeto não encontrado / outra org.
- 422: prompt vazio ou alternative_inputs vazio após validação.
- 429: rate limit (10/h/projeto).
- 502: LLM não retornou JSON parseável.
- 503: nenhuma chave LLM configurada.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps.auth import require_analyst
from app.models.political import PoliticalAuditLog
from app.models.scenario_orchestrator import ScenarioOrchestratorCall
from app.models.user import User
from app.repositories.political_repository import PoliticalProjectRepository
from app.services.political_agents_catalog import FIXED_SPECIALISTS
from app.services.scenario_orchestrator_service import (
    OrchestratorError,
    RATE_LIMIT_PER_PROJECT_PER_HOUR,
    generate_scenario_from_prompt,
)
from uuid import uuid4

router = APIRouter()


class OrchestratorRequest(BaseModel):
    prompt: str = Field(..., min_length=10, max_length=4000)
    agents_to_consult: list[str] = Field(default_factory=list)


class AgentAnalysis(BaseModel):
    agent_role: str
    agent_synthetic_name: str | None = None
    category: str | None = None
    confidence_level: str | None = None
    analysis: str | None
    status: str


class OrchestratorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    political_project_id: str
    requested_by: str | None
    prompt: str
    agents_consulted: list[str]
    scenario_id: str | None
    scenario_payload: dict
    agents_analyses: list[AgentAnalysis]
    rationale: str | None
    llm_model_used: str | None
    status: str
    error_message: str | None
    created_at: datetime


class RateLimitInfo(BaseModel):
    limit_per_hour: int
    used_last_hour: int
    remaining: int


class AvailableAgent(BaseModel):
    role: str
    category: str
    synthetic_name: str
    biography: str
    biases_declared: list[str]
    limitations: list[str]
    confidence_level: str
    tools_available: list[str]


def _audit(db: Session, *, organization_id, project_id, actor_user_id, action, payload):
    db.add(
        PoliticalAuditLog(
            id=str(uuid4()),
            organization_id=organization_id,
            project_id=project_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type="scenario_orchestrator_call",
            target_id=payload.get("call_id"),
            payload=payload,
        )
    )
    db.commit()


@router.get(
    "/agents",
    response_model=list[AvailableAgent],
    summary="Catálogo de especialistas disponíveis para multi-agent",
)
def list_available_agents(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> list[AvailableAgent]:
    # Garantia mínima de isolamento: projeto precisa pertencer à org.
    project = PoliticalProjectRepository(db).get_by_id(project_id)
    if project is None or project.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Projeto não encontrado."
        )
    return [
        AvailableAgent(
            role=s.role,
            category=s.category,
            synthetic_name=s.synthetic_name,
            biography=s.biography,
            biases_declared=list(s.biases_declared),
            limitations=list(s.limitations),
            confidence_level=s.confidence_level,
            tools_available=list(s.tools_available),
        )
        for s in FIXED_SPECIALISTS
    ]


@router.get(
    "/rate-limit",
    response_model=RateLimitInfo,
    summary="Consulta do rate limit atual",
)
def get_rate_limit(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> RateLimitInfo:
    project = PoliticalProjectRepository(db).get_by_id(project_id)
    if project is None or project.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Projeto não encontrado."
        )
    cutoff = datetime.utcnow() - timedelta(hours=1)
    used = (
        db.query(ScenarioOrchestratorCall)
        .filter(
            ScenarioOrchestratorCall.political_project_id == project.id,
            ScenarioOrchestratorCall.created_at >= cutoff,
            ScenarioOrchestratorCall.status != "rate_limited",
        )
        .count()
    )
    return RateLimitInfo(
        limit_per_hour=RATE_LIMIT_PER_PROJECT_PER_HOUR,
        used_last_hour=used,
        remaining=max(0, RATE_LIMIT_PER_PROJECT_PER_HOUR - used),
    )


@router.post(
    "/generate",
    response_model=OrchestratorResponse,
    status_code=status.HTTP_200_OK,
    summary="Gera cenário + análise multi-agent a partir de prompt PT-BR",
)
def generate(
    project_id: str,
    body: OrchestratorRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> OrchestratorResponse:
    project = PoliticalProjectRepository(db).get_by_id(project_id)
    if project is None or project.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Projeto não encontrado."
        )

    try:
        call = generate_scenario_from_prompt(
            db,
            project=project,
            prompt=body.prompt,
            agents_to_consult=body.agents_to_consult,
            requested_by=user.id,
        )
    except OrchestratorError as exc:
        # 429 / 422 / 502 / 503 vêm com status_code embutido.
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    _audit(
        db,
        organization_id=project.organization_id,
        project_id=project.id,
        actor_user_id=user.id,
        action="scenario_orchestrator.completed",
        payload={
            "call_id": call.id,
            "scenario_id": call.scenario_id,
            "agents_count": len(call.agents_consulted),
            "llm_model": call.llm_model_used,
        },
    )
    return OrchestratorResponse.model_validate(call)


@router.get(
    "",
    response_model=list[OrchestratorResponse],
    summary="Histórico das chamadas do orquestrador para este projeto",
)
def list_calls(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> list[OrchestratorResponse]:
    project = PoliticalProjectRepository(db).get_by_id(project_id)
    if project is None or project.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Projeto não encontrado."
        )
    rows = (
        db.query(ScenarioOrchestratorCall)
        .filter(ScenarioOrchestratorCall.political_project_id == project.id)
        .order_by(ScenarioOrchestratorCall.created_at.desc())
        .limit(50)
        .all()
    )
    return [OrchestratorResponse.model_validate(r) for r in rows]
