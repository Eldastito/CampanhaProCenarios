"""Endpoints de grafo político (Fase 3).

Constrói grafo a partir das evidências de um projeto eleitoral usando
o motor de extração existente (GraphService) com a ontologia política
expandida no scenario_catalog. O grafo resultante é vinculado ao
projeto via graph_projects.political_project_id.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps.auth import require_analyst
from app.models.user import User
from app.repositories.political_repository import PoliticalProjectRepository
from app.services.political_graph_service import PoliticalGraphService

logger = logging.getLogger(__name__)
router = APIRouter()


def _ensure_project(project_id: str, db: Session, user: User):
    project = PoliticalProjectRepository(db).get_by_id(project_id)
    if project is None or project.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projeto não encontrado.")
    return project


@router.post(
    "/projects/{project_id}/graph/build",
    summary="Construir/atualizar grafo político a partir das evidências",
)
def build_political_graph(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> dict:
    project = _ensure_project(project_id, db, user)
    service = PoliticalGraphService(db)
    try:
        graph = service.build_graph(project=project, actor_user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logger.exception("political_graph_build_failed project_id=%s", project_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha ao construir grafo. Verifique se a chave da LLM está configurada.",
        )

    return {
        "graph_project_id": graph.id,
        "name": graph.name,
        "status": graph.status,
        "node_count": graph.node_count,
        "edge_count": graph.edge_count,
        "political_project_id": graph.political_project_id,
    }


@router.get(
    "/projects/{project_id}/graph",
    summary="Obter grafo político vinculado a um projeto eleitoral",
)
def get_political_graph(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> dict:
    _ensure_project(project_id, db, user)
    service = PoliticalGraphService(db)
    graph = service.get_graph_project_for(project_id)
    if graph is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum grafo construído para este projeto ainda.",
        )

    full = service._graph.get_project_graph(graph.id)  # noqa: SLF001 — reaproveita método existente
    full["political_project_id"] = project_id
    return full
