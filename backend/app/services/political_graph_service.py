"""Construção de grafo político a partir das evidências de um projeto eleitoral.

Fluxo (PRD §RF-04, RF-05):
1. Recebe political_project_id
2. Agrega raw_text de todas as evidências processadas (status=ready)
3. Cria um GraphProject linkado e usa o GraphService.build_graph_from_text
4. Retorna o GraphProject pronto

A extração em si (LLM + ontologia política) já está implementada em
GraphService — aqui apenas adaptamos o input para o domínio eleitoral
e mantemos o vínculo bidirecional.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.graph import GraphProject
from app.models.political import (
    PoliticalAuditLog,
    PoliticalEvidenceSource,
    PoliticalProject,
)
from app.repositories.political_repository import PoliticalAuditLogRepository
from app.services.graph_service import GraphService

logger = logging.getLogger(__name__)


_MAX_TOTAL_CHARS = 45_000  # margem dentro do limite de 50k do build_graph_from_text


class PoliticalGraphService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._graph = GraphService(db)
        self._audit = PoliticalAuditLogRepository(db)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def build_graph(
        self,
        *,
        project: PoliticalProject,
        actor_user_id: str | None = None,
    ) -> GraphProject:
        """Cria (se necessário) e popula o grafo político do projeto.

        Se já existe um GraphProject vinculado, REUSA o mesmo registro
        (rebuild) — assim o usuário não acumula grafos órfãos a cada clique.
        """
        evidences = self._collect_ready_evidences(project.id)
        if not evidences:
            raise ValueError(
                "Nenhuma evidência processada disponível para este projeto. "
                "Suba documentos ou cadastre fontes antes de construir o grafo."
            )

        aggregated_text = self._aggregate_text(evidences)

        graph_project = self._get_or_create_graph_project(project)

        # Delega para o motor existente (LLM + ontologia política)
        self._graph.build_graph_from_text(graph_project.id, aggregated_text)

        # Recarrega para refletir node/edge counts e status
        self.db.refresh(graph_project)

        # Audit
        self._audit.add(
            PoliticalAuditLog(
                id=str(uuid4()),
                organization_id=project.organization_id,
                project_id=project.id,
                actor_user_id=actor_user_id,
                action="political_graph.built",
                target_type="graph_project",
                target_id=graph_project.id,
                payload={
                    "evidence_count": len(evidences),
                    "node_count": graph_project.node_count,
                    "edge_count": graph_project.edge_count,
                    "graph_status": graph_project.status,
                },
            )
        )

        return graph_project

    def get_graph_project_for(self, political_project_id: str) -> GraphProject | None:
        """Retorna o GraphProject vinculado (mais recente, se existir mais de um)."""
        return (
            self.db.query(GraphProject)
            .filter(GraphProject.political_project_id == political_project_id)
            .order_by(GraphProject.updated_at.desc())
            .first()
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _collect_ready_evidences(self, political_project_id: str) -> list[PoliticalEvidenceSource]:
        return (
            self.db.query(PoliticalEvidenceSource)
            .filter(
                PoliticalEvidenceSource.project_id == political_project_id,
                PoliticalEvidenceSource.processing_status == "ready",
                PoliticalEvidenceSource.raw_text.isnot(None),
            )
            .order_by(PoliticalEvidenceSource.collected_at.desc())
            .all()
        )

    def _aggregate_text(self, evidences: list[PoliticalEvidenceSource]) -> str:
        """Concatena os textos preservando proveniência para a IA enxergar a fonte."""
        parts: list[str] = []
        running_total = 0
        for ev in evidences:
            text = (ev.raw_text or "").strip()
            if not text:
                continue
            header = (
                f"=== FONTE: {ev.title} ({ev.reliability_level})"
                + (f" — {ev.source_url}" if ev.source_url else "")
                + " ==="
            )
            chunk = f"{header}\n{text}\n"
            if running_total + len(chunk) > _MAX_TOTAL_CHARS:
                # Trunca o chunk para caber no orçamento e para a iteração
                remaining = max(0, _MAX_TOTAL_CHARS - running_total)
                if remaining > 200:  # vale a pena incluir parcial
                    parts.append(chunk[:remaining] + "\n[...trecho truncado por limite de contexto...]")
                break
            parts.append(chunk)
            running_total += len(chunk)
        return "\n".join(parts)

    def _get_or_create_graph_project(self, project: PoliticalProject) -> GraphProject:
        existing = self.get_graph_project_for(project.id)
        if existing is not None:
            existing.status = "building"
            self.db.commit()
            self.db.refresh(existing)
            return existing

        # Cria novo GraphProject linkado
        graph = self._graph.create_project(
            organization_id=project.organization_id,
            name=f"Grafo — {project.name}",
            scenario_type="electoral",
            description=(
                f"Grafo político gerado das evidências de {project.candidate_name} "
                f"({project.office} {project.election_year})."
            ),
        )
        graph.political_project_id = project.id
        self.db.commit()
        self.db.refresh(graph)
        return graph
