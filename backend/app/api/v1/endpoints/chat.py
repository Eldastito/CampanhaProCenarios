"""Agent chat endpoints — 55 personas + 4 tools (InsightCampanha, PanoramaSearch, QuickSearch, VirtualInterview)."""
from __future__ import annotations

import logging
from collections import deque
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.agent_personas import get_agent, list_agents
from app.core.time import utc_now_naive
from app.db.session import get_db
from app.deps.auth import get_current_user, require_scenario_access
from app.models.chat import ChatMessageRecord, ChatThread
from app.models.graph import GraphEdge, GraphNode, GraphProject, Simulation, SimulationStep
from app.models.user import User
from app.services.graph_service import _call_llm, get_last_claude_error

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


ToolType = Literal["conversation", "quick_search", "panorama_search", "insight_campanha", "virtual_interview"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    agent_id: str
    tool_type: ToolType = "conversation"
    messages: list[ChatMessage]
    graph_project_id: str | None = None
    thread_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    agent_name: str
    tool_used: str
    tool_metadata: dict
    thread_id: str | None = None


class CreateThreadRequest(BaseModel):
    organization_id: str
    agent_id: str
    title: str | None = None
    graph_project_id: str | None = None


class UpdateThreadRequest(BaseModel):
    title: str


@router.get("/agents", summary="List all 55 agent personas")
def get_agents() -> dict:
    return {"count": 55, "items": list_agents()}


@router.post("/messages", response_model=ChatResponse, summary="Send message to an agent")
def send_message(
    body: ChatRequest,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> ChatResponse:
    agent = get_agent(body.agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent {body.agent_id} not found.")

    if not body.messages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="messages cannot be empty.")

    last_user_msg = next((m.content for m in reversed(body.messages) if m.role == "user"), "")

    if body.tool_type == "quick_search":
        response = _handle_quick_search(agent, last_user_msg, body.graph_project_id, db)
    elif body.tool_type == "panorama_search":
        response = _handle_panorama_search(agent, last_user_msg, body.graph_project_id, db)
    elif body.tool_type == "insight_campanha":
        response = _handle_insight_campanha(agent, last_user_msg, body.graph_project_id, db)
    elif body.tool_type == "virtual_interview":
        response = _handle_virtual_interview(agent, body.messages)
    else:
        response = _handle_conversation(agent, body.messages, body.graph_project_id, db)

    if body.thread_id:
        _persist_turn(db, body.thread_id, last_user_msg, response.reply, body.tool_type)
        response.thread_id = body.thread_id

    return response


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def _handle_conversation(agent, messages: list[ChatMessage], graph_id: str | None, db: Session) -> ChatResponse:
    """Default chat — agent responds in character."""
    history = "\n".join(f"{'Usuário' if m.role == 'user' else agent.name}: {m.content}" for m in messages[-10:])
    graph_context = _build_graph_context(graph_id, db)

    prompt = f"""{agent.persona_prompt}

CONTEXTO DO CENÁRIO:
{graph_context}

HISTÓRICO DA CONVERSA:
{history}

Responda como {agent.name}, mantendo a persona. Seja conciso (2-4 parágrafos). Use português brasileiro."""

    reply = _call_llm(prompt) or _fallback_reply(agent)
    return ChatResponse(
        reply=reply,
        agent_name=agent.name,
        tool_used="conversation",
        tool_metadata={"persona": agent.role, "category": agent.category},
    )


def _handle_quick_search(agent, query: str, graph_id: str | None, db: Session) -> ChatResponse:
    """GraphRAG-style instant query — find matching nodes/edges in graph."""
    if not graph_id:
        return ChatResponse(reply="⚠ Selecione um grafo para usar a Recuperação Rápida.",
                            agent_name=agent.name, tool_used="quick_search", tool_metadata={})

    nodes = db.query(GraphNode).filter(GraphNode.project_id == graph_id).all()
    if not nodes:
        return ChatResponse(reply="Grafo vazio.", agent_name=agent.name, tool_used="quick_search", tool_metadata={})

    q = query.lower()
    matches = [n for n in nodes if q in n.label.lower() or q in n.entity_type.lower()]
    if not matches:
        # fallback: return first 5 nodes
        matches = nodes[:5]

    matches = matches[:8]
    edges = db.query(GraphEdge).filter(
        GraphEdge.project_id == graph_id,
        GraphEdge.source_id.in_([n.id for n in matches]) | GraphEdge.target_id.in_([n.id for n in matches]),
    ).limit(20).all()

    label_of = {n.id: n.label for n in nodes}
    lines = [f"## Recuperação Rápida — '{query}'\n"]
    lines.append(f"**{len(matches)} entidades** encontradas:\n")
    for n in matches:
        props = ", ".join(f"{k}={v}" for k, v in (n.properties or {}).items() if k in ("região", "renda", "faixa_etaria", "religião"))
        lines.append(f"- **{n.label}** ({n.entity_type}){' — ' + props if props else ''}")

    if edges:
        lines.append(f"\n**{len(edges)} relações** envolvidas:")
        for e in edges[:10]:
            lines.append(f"- {label_of.get(e.source_id, '?')} → *{e.relationship_type}* → {label_of.get(e.target_id, '?')}")

    return ChatResponse(
        reply="\n".join(lines),
        agent_name=agent.name,
        tool_used="quick_search",
        tool_metadata={"matches_found": len(matches), "edges_found": len(edges)},
    )


def _handle_panorama_search(agent, query: str, graph_id: str | None, db: Session) -> ChatResponse:
    """BFS-based event propagation through the graph."""
    if not graph_id:
        return ChatResponse(reply="⚠ Selecione um grafo para usar o PanoramaSearch.",
                            agent_name=agent.name, tool_used="panorama_search", tool_metadata={})

    nodes = db.query(GraphNode).filter(GraphNode.project_id == graph_id).all()
    edges = db.query(GraphEdge).filter(GraphEdge.project_id == graph_id).all()
    if not nodes:
        return ChatResponse(reply="Grafo vazio.", agent_name=agent.name, tool_used="panorama_search", tool_metadata={})

    # Find seed node matching query
    q = query.lower()
    seed = next((n for n in nodes if q in n.label.lower()), None) or nodes[0]

    # BFS
    adj: dict[str, list[tuple[str, str]]] = {}
    for e in edges:
        adj.setdefault(e.source_id, []).append((e.target_id, e.relationship_type))
        adj.setdefault(e.target_id, []).append((e.source_id, f"~{e.relationship_type}"))

    label_of = {n.id: n.label for n in nodes}
    type_of = {n.id: n.entity_type for n in nodes}
    visited = {seed.id}
    levels: list[list[tuple[str, str, str]]] = [[(seed.id, "(origem)", seed.entity_type)]]
    queue = deque([(seed.id, 0)])

    while queue and len(levels) <= 4:
        node_id, depth = queue.popleft()
        if depth >= 4:
            continue
        for neighbor_id, rel in adj.get(node_id, []):
            if neighbor_id not in visited:
                visited.add(neighbor_id)
                while len(levels) <= depth + 1:
                    levels.append([])
                levels[depth + 1].append((neighbor_id, rel, type_of.get(neighbor_id, "?")))
                queue.append((neighbor_id, depth + 1))

    lines = [f"## PanoramaSearch — Propagação a partir de '{seed.label}'\n"]
    for depth, level in enumerate(levels):
        if not level:
            continue
        lines.append(f"\n**Nível {depth}** ({len(level)} nós):")
        for nid, rel, etype in level[:12]:
            lines.append(f"- via *{rel}* → **{label_of.get(nid, '?')}** ({etype})")

    lines.append(f"\n**Total de propagação:** {len(visited)} entidades em {len(levels)} níveis.")

    return ChatResponse(
        reply="\n".join(lines),
        agent_name=agent.name,
        tool_used="panorama_search",
        tool_metadata={"seed": seed.label, "levels_traversed": len(levels), "nodes_reached": len(visited)},
    )


def _handle_insight_campanha(agent, query: str, graph_id: str | None, db: Session) -> ChatResponse:
    """Deep attribution — cross-reference simulation outcomes with graph nodes."""
    if not graph_id:
        return ChatResponse(reply="⚠ Selecione um grafo para usar o InsightCampanha.",
                            agent_name=agent.name, tool_used="insight_campanha", tool_metadata={})

    sims = db.query(Simulation).filter(Simulation.project_id == graph_id).order_by(Simulation.created_at.desc()).limit(3).all()
    if not sims:
        return ChatResponse(
            reply="⚠ Nenhuma simulação executada. Execute uma simulação no modo Dividir antes de usar a Atribuição Profunda.",
            agent_name=agent.name, tool_used="insight_campanha", tool_metadata={},
        )

    nodes = {n.id: n for n in db.query(GraphNode).filter(GraphNode.project_id == graph_id).all()}
    lines = [f"## InsightCampanha — Atribuição Profunda\n"]

    for sim in sims:
        steps = db.query(SimulationStep).filter(SimulationStep.simulation_id == sim.id).all()
        agent_freq: dict[str, int] = {}
        for s in steps:
            agent_freq[s.agent_label] = agent_freq.get(s.agent_label, 0) + 1
        top = sorted(agent_freq.items(), key=lambda x: -x[1])[:5]

        lines.append(f"### Simulação: *{sim.name}*")
        lines.append(f"- Status: {sim.status} · {len(steps)} atos")
        lines.append(f"- Resumo: {sim.summary or 'sem resumo'}")
        lines.append(f"- **Atribuição (top 5 agentes mais influentes):**")
        for agent_label, count in top:
            pct = round(100 * count / max(len(steps), 1), 1)
            lines.append(f"  - {agent_label}: {count} atos ({pct}%)")
        lines.append("")

    lines.append(f"\n**Análise:** A IA identifica que {top[0][0] if top else '—'} foi o nó mais influente, "
                 f"correlacionando {top[0][1] if top else 0} atos da simulação ao grafo de {len(nodes)} entidades.")

    return ChatResponse(
        reply="\n".join(lines),
        agent_name=agent.name,
        tool_used="insight_campanha",
        tool_metadata={"simulations_analyzed": len(sims), "nodes_in_graph": len(nodes)},
    )


def _handle_virtual_interview(agent, messages: list[ChatMessage]) -> ChatResponse:
    """Multi-turn interview — agent responds to interview questions."""
    history = "\n".join(f"{'Entrevistador' if m.role == 'user' else agent.name}: {m.content}" for m in messages[-8:])

    prompt = f"""{agent.persona_prompt}

VOCÊ ESTÁ EM UMA ENTREVISTA. O entrevistador está coletando dados de opinião e estados psicológicos.
Responda em primeira pessoa, com profundidade emocional, citando experiências pessoais inventadas mas plausíveis para sua persona.

ROTEIRO DA ENTREVISTA:
{history}

Responda agora como {agent.name}. Tom autêntico, 2-3 parágrafos. Se for a primeira pergunta, comece se apresentando."""

    reply = _call_llm(prompt) or _fallback_reply(agent)
    return ChatResponse(
        reply=reply,
        agent_name=agent.name,
        tool_used="virtual_interview",
        tool_metadata={"persona": agent.role, "turn": len(messages)},
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_graph_context(graph_id: str | None, db: Session) -> str:
    if not graph_id:
        return "(nenhum grafo selecionado)"
    project = db.query(GraphProject).filter(GraphProject.id == graph_id).first()
    if not project:
        return "(grafo não encontrado)"
    nodes = db.query(GraphNode).filter(GraphNode.project_id == graph_id).limit(20).all()
    summary = ", ".join(f"{n.label} ({n.entity_type})" for n in nodes[:15])
    return f"Cenário: {project.name}. Entidades: {summary}."


def _fallback_reply(agent) -> str:
    err = get_last_claude_error()
    msg = f"⚠ IA indisponível ({err})." if err else "⚠ Configure OPENAI_API_KEY no .env."
    return f"{msg}\n\nEu sou {agent.name}, {agent.role}. {agent.description}"


def _persist_turn(db: Session, thread_id: str, user_text: str, assistant_text: str, tool_type: str) -> None:
    """Append a user message + assistant reply to an existing thread."""
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id).first()
    if not thread:
        return
    last_position = (
        db.query(ChatMessageRecord)
        .filter(ChatMessageRecord.thread_id == thread_id)
        .order_by(ChatMessageRecord.position.desc())
        .first()
    )
    next_pos = (last_position.position + 1) if last_position else 0
    if user_text:
        db.add(ChatMessageRecord(
            id=str(uuid4()), thread_id=thread_id, position=next_pos,
            role="user", content=user_text, tool_type=tool_type,
        ))
        next_pos += 1
    db.add(ChatMessageRecord(
        id=str(uuid4()), thread_id=thread_id, position=next_pos,
        role="assistant", content=assistant_text, tool_type=tool_type,
    ))
    thread.updated_at = utc_now_naive()
    db.commit()


# ---------------------------------------------------------------------------
# Thread CRUD
# ---------------------------------------------------------------------------

def _serialize_thread(thread: ChatThread, *, include_messages: bool = False) -> dict:
    out = {
        "thread_id": thread.id,
        "organization_id": thread.organization_id,
        "user_id": thread.user_id,
        "agent_id": thread.agent_id,
        "agent_name": thread.agent_name,
        "title": thread.title,
        "graph_project_id": thread.graph_project_id,
        "created_at": thread.created_at.isoformat(),
        "updated_at": thread.updated_at.isoformat(),
    }
    if include_messages:
        out["messages"] = [
            {
                "id": m.id,
                "position": m.position,
                "role": m.role,
                "content": m.content,
                "tool_type": m.tool_type,
                "created_at": m.created_at.isoformat(),
            }
            for m in thread.messages
        ]
    return out


@router.get("/threads", summary="List chat threads for the current user")
def list_threads(
    organization_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    threads = (
        db.query(ChatThread)
        .filter(ChatThread.user_id == user.id, ChatThread.organization_id == organization_id)
        .order_by(ChatThread.updated_at.desc())
        .all()
    )
    return {"count": len(threads), "items": [_serialize_thread(t) for t in threads]}


@router.post("/threads", summary="Create a new chat thread")
def create_thread(
    body: CreateThreadRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    agent = get_agent(body.agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent {body.agent_id} not found.")
    title = body.title or f"Conversa com {agent.name}"
    thread = ChatThread(
        id=str(uuid4()),
        organization_id=body.organization_id,
        user_id=user.id,
        agent_id=agent.id,
        agent_name=agent.name,
        title=title[:255],
        graph_project_id=body.graph_project_id,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return _serialize_thread(thread, include_messages=True)


@router.get("/threads/{thread_id}", summary="Get a chat thread with all messages")
def get_thread(
    thread_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.")
    if thread.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your thread.")
    return _serialize_thread(thread, include_messages=True)


@router.patch("/threads/{thread_id}", summary="Rename a chat thread")
def update_thread(
    thread_id: str,
    body: UpdateThreadRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.")
    if thread.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your thread.")
    thread.title = body.title[:255]
    db.commit()
    db.refresh(thread)
    return _serialize_thread(thread)


@router.delete("/threads/{thread_id}", summary="Delete a chat thread (cascades messages)")
def delete_thread(
    thread_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found.")
    if thread.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your thread.")
    db.delete(thread)
    db.commit()
    return {"deleted": thread_id}
