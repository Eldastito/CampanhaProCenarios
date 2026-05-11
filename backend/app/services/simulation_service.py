"""Simulation service — generates full step-by-step political/scenario simulation via Claude."""
from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.graph import GraphEdge, GraphNode, GraphProject, Simulation, SimulationStep
from app.services.graph_service import _call_claude, _extract_json, get_last_claude_error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fallback simulation steps when no API key is set
# ---------------------------------------------------------------------------

_FALLBACK_STEPS = [
    {"agent_label": "Agente 1", "agent_type": "Entidade", "action": "speak", "content": "Inicio minha participação no cenário analisando os dados disponíveis.", "affected_nodes": []},
    {"agent_label": "Agente 2", "agent_type": "Entidade", "action": "react", "content": "Respondo à posição do Agente 1 com uma perspectiva diferente.", "affected_nodes": []},
    {"agent_label": "Agente 3", "agent_type": "Entidade", "action": "speak", "content": "Apresento minha análise sobre o cenário atual.", "affected_nodes": []},
    {"agent_label": "Agente 1", "agent_type": "Entidade", "action": "move", "content": "Ajusto minha estratégia com base nas reações observadas.", "affected_nodes": []},
    {"agent_label": "Agente 2", "agent_type": "Entidade", "action": "speak", "content": "Proponho uma nova direção baseada nos acontecimentos.", "affected_nodes": []},
]


class SimulationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_simulation(
        self,
        project_id: str,
        organization_id: str,
        name: str,
        prompt: str | None = None,
    ) -> Simulation:
        simulation = Simulation(
            id=str(uuid4()),
            project_id=project_id,
            organization_id=organization_id,
            name=name,
            prompt=prompt,
            status="pending",
        )
        self.db.add(simulation)
        self.db.commit()
        self.db.refresh(simulation)
        return simulation

    def get_simulation(self, simulation_id: str) -> Simulation | None:
        return self.db.query(Simulation).filter(Simulation.id == simulation_id).first()

    def list_simulations(self, organization_id: str) -> list[Simulation]:
        return (
            self.db.query(Simulation)
            .filter(Simulation.organization_id == organization_id)
            .order_by(Simulation.created_at.desc())
            .all()
        )

    def get_steps(self, simulation_id: str) -> list[SimulationStep]:
        return (
            self.db.query(SimulationStep)
            .filter(SimulationStep.simulation_id == simulation_id)
            .order_by(SimulationStep.step_number)
            .all()
        )

    def get_simulation_view(self, simulation_id: str) -> dict:
        sim = self.get_simulation(simulation_id)
        if not sim:
            raise ValueError("Simulation not found.")
        steps = self.get_steps(simulation_id)
        return {
            "simulation_id": sim.id,
            "project_id": sim.project_id,
            "name": sim.name,
            "prompt": sim.prompt,
            "status": sim.status,
            "summary": sim.summary,
            "step_count": sim.step_count,
            "created_at": sim.created_at.isoformat(),
            "steps": [
                {
                    "step_number": s.step_number,
                    "agent_label": s.agent_label,
                    "agent_type": s.agent_type,
                    "agent_node_id": s.agent_node_id,
                    "action": s.action,
                    "content": s.content,
                    "affected_nodes": s.affected_nodes,
                    "created_at": s.created_at.isoformat(),
                }
                for s in steps
            ],
        }

    # ------------------------------------------------------------------
    # Run simulation (generates all steps at once)
    # ------------------------------------------------------------------

    def run_simulation(self, simulation_id: str, num_steps: int = 12) -> Simulation:
        sim = self.get_simulation(simulation_id)
        if not sim:
            raise ValueError("Simulation not found.")

        sim.status = "running"
        self.db.commit()

        try:
            # Load graph
            nodes = self.db.query(GraphNode).filter(GraphNode.project_id == sim.project_id).all()
            edges = self.db.query(GraphEdge).filter(GraphEdge.project_id == sim.project_id).all()
            project = self.db.query(GraphProject).filter(GraphProject.id == sim.project_id).first()

            steps_data, summary = self._generate_steps(sim, nodes, edges, project, num_steps)
            self._save_steps(simulation_id, steps_data, nodes)

            sim.status = "completed"
            sim.summary = summary
            sim.step_count = len(steps_data)
        except Exception as exc:
            logger.error("simulation_run_error", extra={"error": str(exc)})
            sim.status = "error"
            sim.summary = f"Erro durante a simulação: {exc}"

        self.db.commit()
        self.db.refresh(sim)
        return sim

    def _generate_steps(
        self,
        sim: Simulation,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        project: GraphProject | None,
        num_steps: int,
    ) -> tuple[list[dict], str]:
        if (not settings.openai_api_key and not settings.anthropic_api_key) or not nodes:
            return _FALLBACK_STEPS[:num_steps], "Simulação de demonstração (sem API key configurada)."

        # Build graph description
        node_descriptions = "\n".join(
            f"- {n.label} ({n.entity_type})" for n in nodes[:30]
        )
        edge_descriptions = "\n".join(
            f"- {self._node_label(n.id, nodes)} → {e.relationship_type} → {self._node_label(e.target_id, nodes)}"
            for e in edges[:30]
            for n in [self._find_node(e.source_id, nodes)]
            if n
        )
        scenario_type = project.scenario_type if project else "political"
        scenario_prompt = sim.prompt or f"Simule interações realistas entre os agentes neste cenário de {scenario_type}."

        prompt = f"""Você é um simulador de cenários. Com base no grafo de conhecimento abaixo, gere {num_steps} passos de simulação realistas.

GRAFO DE ENTIDADES:
{node_descriptions}

RELACIONAMENTOS:
{edge_descriptions}

CENÁRIO / PROMPT DO USUÁRIO:
{scenario_prompt}

Gere exatamente {num_steps} passos de simulação. Cada passo representa uma ação ou fala de um agente.
Os agentes devem reagir uns aos outros de forma realista.

Retorne APENAS um JSON válido no seguinte formato:
{{
  "summary": "Resumo do que acontece nesta simulação em 2-3 frases",
  "steps": [
    {{
      "step": 1,
      "agent_label": "Nome exato do agente (deve ser um dos nós listados)",
      "agent_type": "Tipo do agente",
      "action": "speak",
      "content": "O que o agente diz ou faz (1-2 frases objetivas)",
      "affected_nodes": ["Nome de outro agente afetado pela ação"]
    }}
  ]
}}

Tipos de ação: speak (falar), react (reagir), move (mudar posição), announce (anunciar).
Use agentes variados a cada passo. Torne a simulação dramática e interessante."""

        response = _call_claude(prompt)
        data = _extract_json(response)

        if not data or not isinstance(data, dict):
            err = get_last_claude_error()
            reason = err if err else "resposta inválida da API"
            return _FALLBACK_STEPS[:num_steps], f"Simulação demonstrativa — IA falhou: {reason}"

        steps = data.get("steps", [])
        summary = data.get("summary", "Simulação concluída.")
        return steps, summary

    def prepare_streaming_steps(self, simulation_id: str, num_steps: int = 12) -> tuple[list[dict], str]:
        """Generate, save, and return enriched steps ready to be streamed one by one.

        Called synchronously from an async executor so SSE can yield each step.
        """
        sim = self.get_simulation(simulation_id)
        if not sim:
            raise ValueError("Simulation not found.")

        sim.status = "running"
        self.db.commit()

        nodes = self.db.query(GraphNode).filter(GraphNode.project_id == sim.project_id).all()
        edges = self.db.query(GraphEdge).filter(GraphEdge.project_id == sim.project_id).all()
        project = self.db.query(GraphProject).filter(GraphProject.id == sim.project_id).first()

        steps_data, summary = self._generate_steps(sim, nodes, edges, project, num_steps)

        node_map = {n.label.lower(): n for n in nodes}
        enriched: list[dict] = []
        for i, step in enumerate(steps_data):
            agent_label = step.get("agent_label", f"Agente {i + 1}")
            node = node_map.get(agent_label.lower())
            enriched.append({
                "step_number": i + 1,
                "agent_label": agent_label,
                "agent_type": step.get("agent_type", "Entidade"),
                "agent_node_id": node.id if node else None,
                "action": step.get("action", "speak"),
                "content": step.get("content", "..."),
                "affected_nodes": step.get("affected_nodes", []),
            })

        self._save_steps(simulation_id, steps_data, nodes)
        sim.status = "completed"
        sim.summary = summary
        sim.step_count = len(steps_data)
        self.db.commit()

        return enriched, summary

    def _save_steps(
        self, simulation_id: str, steps_data: list[dict], nodes: list[GraphNode]
    ) -> None:
        # Remove old steps
        self.db.query(SimulationStep).filter(
            SimulationStep.simulation_id == simulation_id
        ).delete()

        node_map = {n.label.lower(): n for n in nodes}

        for i, step in enumerate(steps_data):
            agent_label = step.get("agent_label", f"Agente {i+1}")
            # Try to find matching node
            node = node_map.get(agent_label.lower())
            sim_step = SimulationStep(
                id=str(uuid4()),
                simulation_id=simulation_id,
                step_number=i + 1,
                agent_label=agent_label,
                agent_type=step.get("agent_type", "Entidade"),
                agent_node_id=node.id if node else None,
                action=step.get("action", "speak"),
                content=step.get("content", "..."),
                affected_nodes=step.get("affected_nodes", []),
            )
            self.db.add(sim_step)
        self.db.commit()

    @staticmethod
    def _find_node(node_id: str, nodes: list[GraphNode]) -> GraphNode | None:
        return next((n for n in nodes if n.id == node_id), None)

    @staticmethod
    def _node_label(node_id: str, nodes: list[GraphNode]) -> str:
        node = next((n for n in nodes if n.id == node_id), None)
        return node.label if node else node_id
