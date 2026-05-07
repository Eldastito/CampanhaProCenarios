"""Graph building service — uses Claude API to extract entities and relationships."""
from __future__ import annotations

import json
import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.graph import GraphEdge, GraphNode, GraphProject, Simulation, SimulationStep

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default ontologies per scenario type
# ---------------------------------------------------------------------------

_DEFAULT_ONTOLOGIES: dict[str, dict] = {
    "political": {
        "entity_types": [
            "Candidato", "Partido", "Eleitor", "Mídia Tradicional", "Município",
            "Aliado", "Adversário", "Apoiador", "Tribunal", "ONG",
            "Empresa", "Influenciador Digital", "Grupo Religioso", "Sindicato", "Rede Social",
        ],
        "relationship_types": [
            "APOIA", "OPÕE", "REPORTA_SOBRE", "COMPETE_COM", "ALIADO_DE",
            "CRITICA", "REPRESENTA", "INFLUENCIA", "FINANCIA", "PROCESSA",
            "DENUNCIA", "ENDOSSA", "REJEITA", "CONSOME", "PUBLICA",
        ],
    },
    "education": {
        "entity_types": [
            "Escola", "Professor", "Aluno", "Gestor", "Secretaria",
            "Plataforma", "Família", "Sindicato Docente", "MEC", "Pesquisador",
        ],
        "relationship_types": [
            "ENSINA", "ESTUDA_EM", "GERENCIA", "ADOTA", "RESISTE_A",
            "APOIA", "REPORTA_A", "FINANCIA", "REGULA", "PESQUISA",
        ],
    },
    "business": {
        "entity_types": [
            "Empresa", "Produto", "Cliente", "Concorrente", "Fornecedor",
            "Influencer", "Mercado", "Investidor", "Regulador", "Parceiro",
        ],
        "relationship_types": [
            "VENDE", "COMPRA", "COMPETE_COM", "PROMOVE", "FORNECE_PARA",
            "INFLUENCIA", "LIDERA", "INVESTE_EM", "REGULA", "PARCEIRO_DE",
        ],
    },
}

# ---------------------------------------------------------------------------
# LLM helpers (OpenAI preferred, Anthropic as alternative)
# ---------------------------------------------------------------------------

_LAST_LLM_ERROR: dict[str, str | None] = {"message": None}


def get_last_claude_error() -> str | None:
    """Backwards-compat alias — returns last LLM error regardless of provider."""
    return _LAST_LLM_ERROR["message"]


def _call_openai(prompt: str) -> str:
    import openai
    client = openai.OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


def _call_anthropic(prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _call_llm(prompt: str) -> str:
    """Call OpenAI if configured, else Anthropic. Returns "" on error."""
    _LAST_LLM_ERROR["message"] = None
    if settings.openai_api_key:
        try:
            return _call_openai(prompt)
        except Exception as exc:
            err = f"OpenAI {type(exc).__name__}: {exc}"
            logger.warning("openai_api_error", extra={"error": err})
            _LAST_LLM_ERROR["message"] = err
            # If Anthropic is also configured, try it as fallback
            if not settings.anthropic_api_key:
                return ""
    if settings.anthropic_api_key:
        try:
            return _call_anthropic(prompt)
        except Exception as exc:
            err = f"Anthropic {type(exc).__name__}: {exc}"
            logger.warning("anthropic_api_error", extra={"error": err})
            _LAST_LLM_ERROR["message"] = err
            return ""
    _LAST_LLM_ERROR["message"] = "Nenhuma chave de IA configurada (OPENAI_API_KEY ou ANTHROPIC_API_KEY)."
    return ""


# Backwards-compat alias for code that still imports _call_claude
_call_claude = _call_llm


def _extract_json(text: str) -> dict | list | None:
    """Extract first JSON object or array from a text response."""
    start_obj = text.find("{")
    start_arr = text.find("[")
    if start_obj == -1 and start_arr == -1:
        return None
    if start_obj == -1:
        start = start_arr
    elif start_arr == -1:
        start = start_obj
    else:
        start = min(start_obj, start_arr)

    # Find matching end
    depth = 0
    open_char = text[start]
    close_char = "}" if open_char == "{" else "]"
    for i, ch in enumerate(text[start:], start):
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


# ---------------------------------------------------------------------------
# Graph Service
# ---------------------------------------------------------------------------

class GraphService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def create_project(
        self,
        organization_id: str,
        name: str,
        scenario_type: str = "political",
        description: str | None = None,
    ) -> GraphProject:
        project = GraphProject(
            id=str(uuid4()),
            organization_id=organization_id,
            name=name,
            description=description,
            scenario_type=scenario_type,
            ontology=_DEFAULT_ONTOLOGIES.get(scenario_type, _DEFAULT_ONTOLOGIES["political"]),
            status="pending",
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def list_projects(self, organization_id: str) -> list[GraphProject]:
        return (
            self.db.query(GraphProject)
            .filter(GraphProject.organization_id == organization_id)
            .order_by(GraphProject.created_at.desc())
            .all()
        )

    def get_project(self, project_id: str) -> GraphProject | None:
        return self.db.query(GraphProject).filter(GraphProject.id == project_id).first()

    def get_project_graph(self, project_id: str) -> dict:
        project = self.get_project(project_id)
        if not project:
            raise ValueError("Project not found.")
        nodes = self.db.query(GraphNode).filter(GraphNode.project_id == project_id).all()
        edges = self.db.query(GraphEdge).filter(GraphEdge.project_id == project_id).all()
        return {
            "project_id": project_id,
            "name": project.name,
            "scenario_type": project.scenario_type,
            "status": project.status,
            "description": project.description,
            "ontology": project.ontology,
            "node_count": project.node_count,
            "edge_count": project.edge_count,
            "nodes": [
                {"id": n.id, "entity_type": n.entity_type, "label": n.label, "properties": n.properties}
                for n in nodes
            ],
            "edges": [
                {
                    "id": e.id,
                    "source": e.source_id,
                    "target": e.target_id,
                    "relationship_type": e.relationship_type,
                    "properties": e.properties,
                }
                for e in edges
            ],
        }

    # ------------------------------------------------------------------
    # Build graph from text
    # ------------------------------------------------------------------

    def build_graph_from_text(self, project_id: str, text: str) -> GraphProject:
        project = self.get_project(project_id)
        if not project:
            raise ValueError("Project not found.")

        project.status = "building"
        project.source_text = text[:50000]  # cap at 50k chars
        self.db.commit()

        try:
            nodes, edges = self._extract_graph(text, project.ontology, project.scenario_type)
            self._save_graph(project_id, nodes, edges)
            project = self.get_project(project_id)
            if project:
                project.node_count = len(nodes)
                project.edge_count = len(edges)
                project.status = "ready"
                claude_err = get_last_claude_error()
                if claude_err:
                    project.description = f"AVISO IA: {claude_err}. Usando grafo demonstrativo."[:500]
                self.db.commit()
        except Exception as exc:
            logger.exception("graph_build_error")
            self.db.rollback()
            project = self.get_project(project_id)
            if project:
                project.status = "error"
                project.description = f"Build error: {exc}"[:500]
                self.db.commit()

        if project:
            self.db.refresh(project)
        return project

    def _extract_graph(
        self, text: str, ontology: dict, scenario_type: str
    ) -> tuple[list[dict], list[dict]]:
        """Extract nodes and edges from text using LLM or fallback."""
        if settings.openai_api_key or settings.anthropic_api_key:
            return self._extract_with_claude(text, ontology, scenario_type)
        return self._extract_fallback(text, ontology)

    def _extract_with_claude(
        self, text: str, ontology: dict, scenario_type: str
    ) -> tuple[list[dict], list[dict]]:
        entity_types = ", ".join(ontology.get("entity_types", []))
        rel_types = ", ".join(ontology.get("relationship_types", []))

        prompt = f"""Você é um extrator especializado de grafos de conhecimento político-social. Analise o texto e gere um grafo RICO e DENSO.

TIPOS DE ENTIDADE DISPONÍVEIS: {entity_types}
TIPOS DE RELACIONAMENTO DISPONÍVEIS: {rel_types}

TEXTO:
{text[:10000]}

INSTRUÇÕES:
- Extraia o MÁXIMO possível de entidades — mínimo 40 nós, idealmente 60+
- Gere conexões densas — mínimo 80 arestas
- Para cada candidato, crie eleitores de perfis variados (jovem, idoso, trabalhador, empresário, religioso, etc.)
- Adicione mídias, partidos, municípios, aliados, ONGs e grupos de interesse
- Propriedades úteis: idade, região, renda, escolaridade, religião, ocupação (para eleitores)
- Se o texto for curto, INVENTE entidades realistas compatíveis com o cenário político brasileiro

Retorne APENAS um JSON válido no seguinte formato (sem explicações):
{{
  "nodes": [
    {{"id": "n1", "entity_type": "Candidato", "label": "Nome da Entidade", "properties": {{"região": "SP", "partido": "..."}}}},
    ...
  ],
  "edges": [
    {{"source": "n1", "target": "n2", "relationship_type": "APOIA", "properties": {{"intensidade": "alta"}}}},
    ...
  ]
}}

Cada nó deve ter id único (n1, n2, ...). Responda SOMENTE com o JSON."""

        response = _call_claude(prompt)
        data = _extract_json(response)

        if not data or not isinstance(data, dict):
            return self._extract_fallback("", {"entity_types": ontology.get("entity_types", [])})

        nodes = data.get("nodes", [])
        edges = data.get("edges", [])

        # Validate node references in edges
        node_ids = {n["id"] for n in nodes if "id" in n}
        valid_edges = [
            e for e in edges
            if e.get("source") in node_ids and e.get("target") in node_ids
        ]

        return nodes, valid_edges

    # ------------------------------------------------------------------
    # Populate opinions — generates citizen-agent nodes with opinions
    # ------------------------------------------------------------------

    def populate_opinions(self, project_id: str, prompt_hint: str = "") -> dict:
        """Generate 30+ citizen-agent nodes with opinions attached to the existing graph."""
        project = self.get_project(project_id)
        if not project:
            raise ValueError("Project not found.")

        # Load existing graph for context
        nodes = self.db.query(GraphNode).filter(GraphNode.project_id == project_id).all()
        candidates = [n for n in nodes if n.entity_type == "Candidato"]
        parties = [n for n in nodes if n.entity_type == "Partido"]
        media_nodes = [n for n in nodes if n.entity_type in ("Mídia Tradicional", "Rede Social", "Influenciador Digital")]

        candidate_names = ", ".join(n.label for n in candidates[:8]) or "candidatos do cenário"
        party_names = ", ".join(n.label for n in parties[:5]) or "partidos do cenário"
        media_names = ", ".join(n.label for n in media_nodes[:5]) or "Jornal Nacional, G1, Instagram"

        if not (settings.openai_api_key or settings.anthropic_api_key):
            return self._populate_opinions_fallback(project_id, candidates)

        context = prompt_hint or f"Eleição com candidatos: {candidate_names}. Partidos: {party_names}."

        ai_prompt = f"""Você é um gerador de agentes sociais para simulação de cenário político brasileiro.

CONTEXTO DO CENÁRIO:
{context}

CANDIDATOS NO GRAFO: {candidate_names}
PARTIDOS: {party_names}
MÍDIAS: {media_names}

TAREFA: Gere exatamente 35 agentes-cidadãos simulados representando a sociedade brasileira.
Cada agente deve ter perfil demográfico realista e opiniões sobre os candidatos.

Retorne APENAS JSON válido:
{{
  "agents": [
    {{
      "id": "ag1",
      "label": "Nome Fictício",
      "entity_type": "Eleitor",
      "properties": {{
        "faixa_etaria": "18-25",
        "renda": "baixa",
        "escolaridade": "ensino médio",
        "região": "Nordeste",
        "religião": "evangélica",
        "ocupação": "comerciante",
        "uso_redes_sociais": "alto"
      }},
      "opinions": [
        {{"candidate_label": "Nome do Candidato", "stance": "APOIA", "intensity": "alta"}},
        {{"candidate_label": "Outro Candidato", "stance": "OPÕE", "intensity": "média"}}
      ],
      "media_consumption": ["Nome da Mídia"]
    }}
  ]
}}

Varie os perfis: jovens, idosos, trabalhadores, empresários, religiosos, professores, desempregados.
Distribua as opiniões de forma realista (alguns divididos, outros convictos).
Responda SOMENTE com o JSON."""

        response = _call_llm(ai_prompt)
        data = _extract_json(response)

        if not data or not isinstance(data, dict) or "agents" not in data:
            return self._populate_opinions_fallback(project_id, candidates)

        new_nodes: list[dict] = []
        new_edges: list[dict] = []
        agent_id_counter = len(nodes) + 1
        candidate_map = {n.label.lower(): n for n in candidates}
        media_map = {n.label.lower(): n for n in media_nodes}

        for agent in data.get("agents", []):
            if not isinstance(agent, dict):
                continue
            temp_id = f"op{agent_id_counter}"
            agent_id_counter += 1
            new_nodes.append({
                "id": temp_id,
                "entity_type": "Eleitor",
                "label": str(agent.get("label", f"Cidadão {agent_id_counter}"))[:255],
                "properties": agent.get("properties", {}),
            })
            for opinion in agent.get("opinions", []):
                cand_key = str(opinion.get("candidate_label", "")).lower()
                cand_node = candidate_map.get(cand_key)
                if cand_node:
                    new_edges.append({
                        "source": temp_id,
                        "target": f"__existing__{cand_node.id}",
                        "relationship_type": opinion.get("stance", "APOIA"),
                        "properties": {"intensidade": opinion.get("intensity", "média")},
                    })
            for media_name in agent.get("media_consumption", []):
                media_node = media_map.get(media_name.lower())
                if media_node:
                    new_edges.append({
                        "source": temp_id,
                        "target": f"__existing__{media_node.id}",
                        "relationship_type": "CONSOME",
                        "properties": {},
                    })

        # Save new nodes (append, don't replace existing)
        id_map: dict[str, str] = {}
        for n in new_nodes:
            real_id = str(uuid4())
            id_map[n["id"]] = real_id
            db_node = GraphNode(
                id=real_id,
                project_id=project_id,
                entity_type=n["entity_type"],
                label=n["label"],
                properties=n.get("properties", {}),
            )
            self.db.add(db_node)
        self.db.flush()

        added_edges = 0
        for e in new_edges:
            src_key = str(e.get("source", ""))
            tgt_key = str(e.get("target", ""))
            src = id_map.get(src_key)
            if tgt_key.startswith("__existing__"):
                tgt = tgt_key.replace("__existing__", "")
            else:
                tgt = id_map.get(tgt_key)
            if src and tgt:
                db_edge = GraphEdge(
                    id=str(uuid4()),
                    project_id=project_id,
                    source_id=src,
                    target_id=tgt,
                    relationship_type=str(e.get("relationship_type", "RELACIONA_COM"))[:100],
                    properties=e.get("properties", {}),
                )
                self.db.add(db_edge)
                added_edges += 1

        # Update counts
        total_nodes = self.db.query(GraphNode).filter(GraphNode.project_id == project_id).count()
        total_edges = self.db.query(GraphEdge).filter(GraphEdge.project_id == project_id).count()
        if project:
            project.node_count = total_nodes
            project.edge_count = total_edges
        self.db.commit()

        return {
            "added_nodes": len(new_nodes),
            "added_edges": added_edges,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
        }

    def _populate_opinions_fallback(self, project_id: str, candidates: list) -> dict:
        """Demo fallback when no API key — generates 10 fixed voter nodes."""
        profiles = [
            ("Maria Silva", "jovem-urbana", {"faixa_etaria": "18-25", "renda": "baixa", "região": "Sudeste"}),
            ("João Santos", "trabalhador", {"faixa_etaria": "36-50", "renda": "média", "região": "Nordeste"}),
            ("Ana Costa", "empresária", {"faixa_etaria": "36-50", "renda": "alta", "região": "Sul"}),
            ("Pedro Oliveira", "aposentado", {"faixa_etaria": "60+", "renda": "média", "região": "Centro-Oeste"}),
            ("Carla Lima", "estudante", {"faixa_etaria": "18-25", "renda": "baixa", "região": "Norte"}),
            ("Roberto Alves", "professor", {"faixa_etaria": "26-35", "renda": "média", "região": "Sudeste"}),
            ("Francisca Souza", "religiosa", {"faixa_etaria": "51-60", "renda": "baixa", "região": "Nordeste"}),
            ("Marcelo Pereira", "autônomo", {"faixa_etaria": "26-35", "renda": "baixa", "região": "Sul"}),
            ("Lucia Ferreira", "funcionária pública", {"faixa_etaria": "36-50", "renda": "média", "região": "Sudeste"}),
            ("Carlos Nunes", "empresário rural", {"faixa_etaria": "51-60", "renda": "alta", "região": "Centro-Oeste"}),
        ]
        stances = ["APOIA", "OPÕE", "APOIA", "OPÕE", "APOIA", "OPÕE", "APOIA", "APOIA", "OPÕE", "APOIA"]
        added_nodes = 0
        added_edges = 0
        for i, (label, _, props) in enumerate(profiles):
            nid = str(uuid4())
            self.db.add(GraphNode(id=nid, project_id=project_id, entity_type="Eleitor", label=label, properties=props))
            added_nodes += 1
            if candidates:
                cand = candidates[i % len(candidates)]
                self.db.add(GraphEdge(
                    id=str(uuid4()), project_id=project_id,
                    source_id=nid, target_id=cand.id,
                    relationship_type=stances[i % len(stances)],
                    properties={"intensidade": "média"},
                ))
                added_edges += 1
        total_nodes = self.db.query(GraphNode).filter(GraphNode.project_id == project_id).count()
        total_edges = self.db.query(GraphEdge).filter(GraphEdge.project_id == project_id).count()
        project = self.get_project(project_id)
        if project:
            project.node_count = total_nodes
            project.edge_count = total_edges
        self.db.commit()
        return {"added_nodes": added_nodes, "added_edges": added_edges, "total_nodes": total_nodes, "total_edges": total_edges}

    def _extract_fallback(self, text: str, ontology: dict) -> tuple[list[dict], list[dict]]:
        """Create a minimal demo graph when no API key is configured."""
        entity_types = ontology.get("entity_types", ["Entidade A", "Entidade B"])
        rel_types = ontology.get("relationship_types", ["RELACIONA_COM"])

        nodes = [
            {"id": f"n{i+1}", "entity_type": entity_types[i % len(entity_types)], "label": f"{entity_types[i % len(entity_types)]} {i+1}", "properties": {}}
            for i in range(6)
        ]
        edges = [
            {"source": f"n{i+1}", "target": f"n{(i+2) % 6 + 1}", "relationship_type": rel_types[i % len(rel_types)], "properties": {}}
            for i in range(5)
        ]
        return nodes, edges

    def _save_graph(self, project_id: str, nodes: list[dict], edges: list[dict]) -> None:
        # Remove existing nodes and edges
        self.db.query(GraphEdge).filter(GraphEdge.project_id == project_id).delete(
            synchronize_session=False
        )
        self.db.query(GraphNode).filter(GraphNode.project_id == project_id).delete(
            synchronize_session=False
        )
        self.db.flush()

        # Map temp ids to real UUIDs
        id_map: dict[str, str] = {}
        for n in nodes:
            if not isinstance(n, dict):
                continue
            temp_id = n.get("id")
            if not temp_id:
                continue
            real_id = str(uuid4())
            id_map[str(temp_id)] = real_id
            entity_type = str(n.get("entity_type") or "Entidade")[:100]
            label = str(n.get("label") or "?")[:255]
            properties = n.get("properties") or {}
            if not isinstance(properties, dict):
                properties = {}
            node = GraphNode(
                id=real_id,
                project_id=project_id,
                entity_type=entity_type,
                label=label,
                properties=properties,
            )
            self.db.add(node)
        self.db.flush()

        for e in edges:
            if not isinstance(e, dict):
                continue
            src = id_map.get(str(e.get("source", "")))
            tgt = id_map.get(str(e.get("target", "")))
            if src and tgt:
                relationship_type = str(e.get("relationship_type") or "RELACIONA_COM")[:100]
                properties = e.get("properties") or {}
                if not isinstance(properties, dict):
                    properties = {}
                edge = GraphEdge(
                    id=str(uuid4()),
                    project_id=project_id,
                    source_id=src,
                    target_id=tgt,
                    relationship_type=relationship_type,
                    properties=properties,
                )
                self.db.add(edge)

        self.db.commit()
