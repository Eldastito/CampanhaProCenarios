"""Serviço da bancada de agentes políticos (Fase 4).

Dois modos:
1. ``seed_fixed_specialists(project)`` — instancia o catálogo estático
   de 17 especialistas (jurídico, fact-check, mídia, território, etc.)
   se ainda não existirem para o projeto. Idempotente: re-executar não
   duplica, só preenche o que falta.

2. ``generate_from_graph(project)`` — varre o GraphProject vinculado e
   cria personas sintéticas a partir de nós ELEITORAIS / LIDERANÇA /
   INFLUENCIADOR. Cada persona registra os ``source_node_ids`` que a
   originaram (rastreabilidade exigida pelo PRD §RF-06 e §7).

Ambos registram audit log em political_audit_logs.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.graph import GraphNode
from app.models.political import (
    PoliticalAgentProfile,
    PoliticalAuditLog,
    PoliticalProject,
)
from app.repositories.political_repository import (
    PoliticalAgentRepository,
    PoliticalAuditLogRepository,
)
from app.services.political_agents_catalog import FIXED_SPECIALISTS, FixedSpecialistSpec
from app.services.political_graph_service import PoliticalGraphService

logger = logging.getLogger(__name__)


# Tipos de nó do grafo que viram persona gerada
_GENERATED_FROM_NODE_TYPES = {
    "Eleitor": ("eleitor_segmento", "Eleitor (segmento extraído)"),
    "Segmento Eleitoral": ("eleitor_segmento", "Segmento Eleitoral"),
    "Liderança Comunitária": ("lideranca", "Liderança Comunitária"),
    "Influenciador Digital": ("influenciador", "Influenciador Digital"),
    "Mídia Local": ("midia_local", "Mídia Local"),
    "Mídia Nacional": ("midia_nacional", "Mídia Nacional"),
    "Grupo Religioso": ("grupo_religioso", "Grupo Religioso"),
    "Sindicato": ("sindicato", "Sindicato"),
    "Movimento Social": ("movimento_social", "Movimento Social"),
}


_GENERATED_PROMPT_BASE = (
    "Você é uma persona sintética usada para SIMULAR a reação de um "
    "segmento/ator político específico. Permaneça no domínio política/eleições. "
    "Separe FATO, INFERÊNCIA e HIPÓTESE. Quando expressar opinião, deixe claro "
    "que é simulação, não pesquisa real. Cite as evidências/entidades-fonte "
    "que formaram esse perfil quando perguntado."
)


class PoliticalAgentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._agents = PoliticalAgentRepository(db)
        self._audit = PoliticalAuditLogRepository(db)
        self._graph = PoliticalGraphService(db)

    # ------------------------------------------------------------------
    # Fixed specialists
    # ------------------------------------------------------------------

    def seed_fixed_specialists(
        self,
        *,
        project: PoliticalProject,
        actor_user_id: str | None = None,
    ) -> tuple[int, int]:
        """Cria especialistas fixos faltantes. Retorna (created, skipped)."""
        existing_categories = self._agents.categories_present(project.id, "fixed_specialist")

        new_agents: list[PoliticalAgentProfile] = []
        for spec in FIXED_SPECIALISTS:
            if spec.category in existing_categories:
                continue
            new_agents.append(self._build_fixed(project, spec))

        created = self._agents.add_bulk(new_agents)
        skipped = len(FIXED_SPECIALISTS) - len(created)

        self._audit.add(
            PoliticalAuditLog(
                id=str(uuid4()),
                organization_id=project.organization_id,
                project_id=project.id,
                actor_user_id=actor_user_id,
                action="political_agents.seed_specialists",
                target_type="political_project",
                target_id=project.id,
                payload={"created": len(created), "skipped": skipped},
            )
        )
        return len(created), skipped

    # ------------------------------------------------------------------
    # Generated from graph
    # ------------------------------------------------------------------

    def generate_from_graph(
        self,
        *,
        project: PoliticalProject,
        actor_user_id: str | None = None,
    ) -> tuple[int, int]:
        """Apaga geradas anteriores e cria novas a partir do grafo. (created, removed_old)."""
        graph = self._graph.get_graph_project_for(project.id)
        if graph is None:
            raise ValueError(
                "Nenhum grafo construído para este projeto. "
                "Construa o grafo (Fase 3) antes de gerar agentes."
            )

        nodes = (
            self.db.query(GraphNode)
            .filter(
                GraphNode.project_id == graph.id,
                GraphNode.entity_type.in_(list(_GENERATED_FROM_NODE_TYPES.keys())),
            )
            .all()
        )
        if not nodes:
            raise ValueError(
                "O grafo não tem entidades elegíveis para gerar agentes "
                "(Eleitor, Segmento Eleitoral, Liderança Comunitária, "
                "Influenciador Digital, Mídia Local/Nacional, Grupo Religioso, "
                "Sindicato, Movimento Social)."
            )

        # Limpa geradas antigas pra refletir o grafo atual
        removed = self._agents.delete_generated_for_project(project.id)

        new_agents = [self._build_generated(project, n) for n in nodes]
        created = self._agents.add_bulk(new_agents)

        self._audit.add(
            PoliticalAuditLog(
                id=str(uuid4()),
                organization_id=project.organization_id,
                project_id=project.id,
                actor_user_id=actor_user_id,
                action="political_agents.generate_from_graph",
                target_type="political_project",
                target_id=project.id,
                payload={
                    "created": len(created),
                    "removed_previous": removed,
                    "graph_project_id": graph.id,
                },
            )
        )
        return len(created), removed

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------

    def _build_fixed(
        self,
        project: PoliticalProject,
        spec: FixedSpecialistSpec,
    ) -> PoliticalAgentProfile:
        # Personalização leve do prompt: contextualiza o cargo/UF do projeto
        contextual_prompt = (
            f"{spec.persona_prompt}\n\n"
            f"CONTEXTO DO PROJETO:\n"
            f"- Cargo: {project.office} {project.election_year}\n"
            f"- Candidato principal: {project.candidate_name}\n"
            f"- UF/Município: {project.state or '—'} / {project.municipality or '—'}\n"
            f"- Partidos: {', '.join(project.parties) if project.parties else '—'}\n"
            f"- Adversários conhecidos: "
            f"{', '.join(project.known_opponents) if project.known_opponents else '—'}"
        )
        return PoliticalAgentProfile(
            id=str(uuid4()),
            organization_id=project.organization_id,
            project_id=project.id,
            agent_type="fixed_specialist",
            role=spec.role,
            category=spec.category,
            synthetic_name=spec.synthetic_name,
            biography=spec.biography,
            persona_prompt=contextual_prompt,
            biases_declared=list(spec.biases_declared),
            limitations=list(spec.limitations),
            confidence_level=spec.confidence_level,
            source_node_ids=[],
            source_evidence_ids=[],
        )

    def _build_generated(
        self,
        project: PoliticalProject,
        node: GraphNode,
    ) -> PoliticalAgentProfile:
        category, role_label = _GENERATED_FROM_NODE_TYPES.get(
            node.entity_type, ("entidade_outra", node.entity_type)
        )

        # Evita usar nome real do nó como nome do agente — gera nome sintético
        synthetic = self._synthesize_name(role_label, node.label)

        biography = (
            f"Persona sintética gerada da entidade '{node.label}' "
            f"(tipo {node.entity_type}) extraída do grafo do projeto. "
            "NÃO corresponde a uma pessoa real específica — agrega o "
            "comportamento esperado do segmento/papel mapeado."
        )

        prompt = (
            f"{_GENERATED_PROMPT_BASE}\n\n"
            f"CONTEXTO:\n"
            f"- Você representa o papel: {role_label}\n"
            f"- Originado da entidade do grafo: {node.label}\n"
            f"- Cargo em disputa: {project.office} {project.election_year}\n"
            f"- Território: {project.state or '—'} / {project.municipality or '—'}\n"
            f"- Candidato observado: {project.candidate_name}\n"
            f"- Adversários: {', '.join(project.known_opponents) if project.known_opponents else '—'}\n\n"
            "REGRA DURA: você NÃO conhece informações fora do que foi extraído "
            "das evidências do projeto. Quando perguntado sobre algo que não "
            "está no contexto, responda 'não tenho evidência sobre isso'."
        )

        biases = [
            f"Persona aglutinada de '{role_label}' — esconde diversidade interna.",
            "Modelada a partir de evidências limitadas ao escopo do projeto.",
        ]
        limitations = [
            "Não substitui pesquisa qualitativa real com o segmento.",
            "Reflete vieses presentes nas evidências subidas.",
            f"Baseado em UMA entidade do grafo (id={node.id}) — pode estar enviesada.",
        ]

        # source_evidence_ids: evidências que mencionam essa entidade ainda não
        # ficam mapeadas direto (precisaria de uma tabela edge node↔evidence —
        # entra em fase futura). Por ora deixamos vazio; rastro fica via grafo.
        return PoliticalAgentProfile(
            id=str(uuid4()),
            organization_id=project.organization_id,
            project_id=project.id,
            agent_type="generated",
            role=role_label,
            category=category,
            synthetic_name=synthetic,
            biography=biography,
            persona_prompt=prompt,
            biases_declared=biases,
            limitations=limitations,
            confidence_level="low",
            source_node_ids=[node.id],
            source_evidence_ids=[],
        )

    @staticmethod
    def _synthesize_name(role_label: str, source_label: str) -> str:
        """Gera nome sintético sem usar o label real do nó (evita confundir com pessoa real)."""
        # Estratégia: prefixar com "Persona-" e o role_label
        return f"Persona-{role_label}"
