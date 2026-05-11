"""Claude Managed — orquestrador de cenários (Fase 6 PRD v2).

Endpoint público: ``POST /api/v1/political/projects/{id}/scenarios/generate``
recebe um prompt em PT-BR e devolve cenário pronto + análises de agentes
especialistas relevantes. **Diferente** do ``dossier_orchestrator`` da
Fase 3b (que apenas agrega dados externos para o dossiê).

Pipeline:
1. **Contextualizar**: Claude recebe prompt + 12 fatores atuais (cache
   da Fase 2 se houver) + lista de dossiês disponíveis + descrição do projeto.
2. **Estruturar**: Claude devolve JSON com ``name``, ``description``,
   ``baseline_inputs``, ``alternative_inputs``, ``rationale``.
3. **Validar**: filtra ``alternative_inputs`` para conter SOMENTE as 12
   chaves válidas; valores fora de [0, 100] são clampados. Se nenhuma
   chave válida sobra, falha com 422.
4. **Criar cenário** via ``ScenarioService.create_scenario``.
5. **Executar** via ``queue_run`` + ``execute_run`` (caminho legado).
6. **Multi-agent**: para cada ``agent_id`` em ``agents_to_consult``,
   pedir ao Claude análise usando ``persona_prompt`` do especialista
   fixo. Resultados agregados.
7. **Persistir**: ``ScenarioOrchestratorCall`` grava prompt + saída
   completa para auditoria/rate-limit.

Guardrails: o prompt-base reforça as 3 regras do PRD §1
(separar FATO/INFERÊNCIA/HIPÓTESE, nunca inventar dados sobre candidatos,
recusar tema fora do escopo eleitoral).

Sem chave LLM configurada → 503. Não há fallback gracioso aqui
(diferente da Fase 3b): a Claude Managed é tipicamente paga e premium;
melhor falhar explícito do que entregar cenário vazio.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.scenario_catalog import ELECTORAL_FACTORS
from app.models.dossier import CandidateDossier
from app.models.factor_cache import CampanhaProFactorCache
from app.models.political import PoliticalProject
from app.models.scenario_orchestrator import ScenarioOrchestratorCall
from app.services.political_agents_catalog import FIXED_SPECIALISTS
from app.services.scenario_service import ScenarioService

logger = logging.getLogger(__name__)

VALID_FACTOR_KEYS: frozenset[str] = frozenset(f.key for f in ELECTORAL_FACTORS)
RATE_LIMIT_PER_PROJECT_PER_HOUR = 10


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


_SCENARIO_PROMPT = """Você é um analista político sênior trabalhando dentro de uma ferramenta de
simulação de campanhas brasileiras. Receba um prompt em português e devolva
APENAS um objeto JSON com a estrutura abaixo. Sem markdown, sem comentários.

{{
  "name": "string curta — nome do cenário",
  "description": "1-2 frases descrevendo a hipótese",
  "baseline_inputs": {{ "<chave>": <valor 0-100>, ... }},
  "alternative_inputs": {{ "<chave>": <valor 0-100>, ... }},
  "rationale": "explicação separando FATO / INFERÊNCIA / HIPÓTESE"
}}

Regras INEGOCIÁVEIS:
- ``baseline_inputs`` e ``alternative_inputs`` só podem usar estas 12 chaves:
  {valid_keys}.
  Qualquer outra chave será descartada.
- Valores devem ser inteiros entre 0 e 100.
- ``rationale`` deve marcar trechos como "FATO:", "INFERÊNCIA:", "HIPÓTESE:".
- Nunca invente dados sobre candidatos, processos ou apoiadores.
- Se o prompt está fora do escopo eleitoral, devolva um JSON com
  ``"name": "Fora de escopo"`` e ``rationale`` explicando o motivo —
  baseline/alternative ficam vazios.

Contexto do projeto:
- Candidato: {candidate_name} ({party}) — {office} {year}
- Localização: {municipality} / {state}
- Conhecidos adversários: {opponents}

Fatores atuais (cache da Fase 2):
{factors_block}

Dossiês disponíveis ({dossier_count}):
{dossier_block}

Prompt do usuário:
{prompt}
"""


_AGENT_PROMPT = """{persona_prompt}

Você está sendo consultado sobre um cenário gerado por outro analista. Receba
o JSON do cenário e devolva uma análise de até 200 palavras seguindo seus
vieses e limitações DECLARADOS. Separe FATO, INFERÊNCIA e HIPÓTESE.
Não invente dados externos ao contexto.

Cenário:
{scenario_json}
"""


# ---------------------------------------------------------------------------
# LLM call (reusa padrão do dossier_orchestrator)
# ---------------------------------------------------------------------------


def _llm_call(prompt: str, *, json_mode: bool = False) -> tuple[str, str | None]:
    """Retorna (texto, modelo_usado). Sem chave configurada → ('', None)."""
    if settings.openai_api_key:
        try:
            import openai

            client = openai.OpenAI(api_key=settings.openai_api_key)
            kwargs: dict[str, Any] = {
                "model": settings.openai_model,
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or "", settings.openai_model
        except Exception as exc:  # noqa: BLE001
            logger.warning("scenario_orchestrator_openai_error", extra={"error": repr(exc)})

    if settings.anthropic_api_key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            message = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            text_blocks = [b.text for b in message.content if getattr(b, "text", None)]
            return "\n".join(text_blocks), settings.anthropic_model
        except Exception as exc:  # noqa: BLE001
            logger.warning("scenario_orchestrator_anthropic_error", extra={"error": repr(exc)})

    return "", None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        idx = text.find("\n")
        if idx >= 0:
            text = text[idx + 1 :]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {}
        return {}


def _validate_inputs(raw: Any) -> dict[str, float]:
    """Mantém só chaves válidas com valores em [0, 100]."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for k, v in raw.items():
        if k not in VALID_FACTOR_KEYS:
            continue
        try:
            num = float(v)
        except (TypeError, ValueError):
            continue
        out[k] = max(0.0, min(100.0, num))
    return out


def _build_context(
    db: Session, project: PoliticalProject
) -> dict[str, Any]:
    """Pega cache de fatores + dossiês para enriquecer o prompt."""
    cache = (
        db.query(CampanhaProFactorCache)
        .filter(
            CampanhaProFactorCache.organization_id == project.organization_id,
            CampanhaProFactorCache.campaign_id == project.campaign_id,
        )
        .order_by(CampanhaProFactorCache.reference_date.desc())
        .first()
    )
    factors_block = (
        "\n".join(f"  - {k}: {v}" for k, v in (cache.factors or {}).items())
        if cache and cache.factors
        else "  (sem cache de fatores ainda)"
    )

    dossiers = (
        db.query(CandidateDossier)
        .filter(CandidateDossier.political_project_id == project.id)
        .order_by(CandidateDossier.candidate_type.desc())
        .all()
    )
    dossier_block = (
        "\n".join(
            f"  - {d.candidate_name} ({d.candidate_type}, {d.party or 's/p'}) — confiança {d.confidence_level}"
            for d in dossiers
        )
        if dossiers
        else "  (nenhum dossiê ainda)"
    )

    return {
        "factors_block": factors_block,
        "dossier_block": dossier_block,
        "dossier_count": len(dossiers),
    }


def _check_rate_limit(db: Session, project_id: str) -> tuple[bool, int]:
    """Conta chamadas do último hora. Retorna (allowed, used_count)."""
    cutoff = datetime.utcnow() - timedelta(hours=1)
    used = (
        db.query(ScenarioOrchestratorCall)
        .filter(
            ScenarioOrchestratorCall.political_project_id == project_id,
            ScenarioOrchestratorCall.created_at >= cutoff,
            ScenarioOrchestratorCall.status != "rate_limited",
        )
        .count()
    )
    return used < RATE_LIMIT_PER_PROJECT_PER_HOUR, used


def _persist_call(
    db: Session,
    *,
    organization_id: str,
    project_id: str,
    requested_by: str | None,
    prompt: str,
    agents_consulted: list[str],
    scenario_id: str | None,
    scenario_payload: dict,
    agents_analyses: list[dict],
    rationale: str | None,
    llm_model_used: str | None,
    status: str,
    error_message: str | None = None,
) -> ScenarioOrchestratorCall:
    row = ScenarioOrchestratorCall(
        id=str(uuid4()),
        organization_id=organization_id,
        political_project_id=project_id,
        requested_by=requested_by,
        prompt=prompt,
        agents_consulted=agents_consulted,
        scenario_id=scenario_id,
        scenario_payload=scenario_payload,
        agents_analyses=agents_analyses,
        rationale=rationale,
        llm_model_used=llm_model_used,
        status=status,
        error_message=error_message,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Errors de domínio
# ---------------------------------------------------------------------------


class OrchestratorError(Exception):
    """Falha do orquestrador. Status sugerido vai no atributo .status_code."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def generate_scenario_from_prompt(
    db: Session,
    *,
    project: PoliticalProject,
    prompt: str,
    agents_to_consult: list[str] | None = None,
    requested_by: str | None = None,
) -> ScenarioOrchestratorCall:
    """Gera um cenário a partir de prompt + opcionalmente consulta agentes.

    ``agents_to_consult`` é uma lista de ``role`` dos especialistas fixos
    (ex: "Análise de Adversários", "Mídia (Porta-voz)"). Quando vazia,
    nenhuma análise extra é gerada (só o cenário).
    """
    agents_to_consult = agents_to_consult or []

    # 1. Rate limit
    allowed, used = _check_rate_limit(db, project.id)
    if not allowed:
        row = _persist_call(
            db,
            organization_id=project.organization_id,
            project_id=project.id,
            requested_by=requested_by,
            prompt=prompt,
            agents_consulted=agents_to_consult,
            scenario_id=None,
            scenario_payload={},
            agents_analyses=[],
            rationale=None,
            llm_model_used=None,
            status="rate_limited",
            error_message=f"Rate limit excedido: {used}/{RATE_LIMIT_PER_PROJECT_PER_HOUR} por hora.",
        )
        raise OrchestratorError(
            f"Rate limit do orquestrador excedido para este projeto "
            f"({used}/{RATE_LIMIT_PER_PROJECT_PER_HOUR}/h). Tente novamente em até 1h.",
            status_code=429,
        )

    # 2. Sem chave LLM → 503 explícito
    if not (settings.openai_api_key or settings.anthropic_api_key):
        _persist_call(
            db,
            organization_id=project.organization_id,
            project_id=project.id,
            requested_by=requested_by,
            prompt=prompt,
            agents_consulted=agents_to_consult,
            scenario_id=None,
            scenario_payload={},
            agents_analyses=[],
            rationale=None,
            llm_model_used=None,
            status="failed",
            error_message="Nenhuma chave LLM configurada (OPENAI_API_KEY / ANTHROPIC_API_KEY).",
        )
        raise OrchestratorError(
            "Claude Managed indisponível: nenhuma chave LLM configurada no servidor.",
            status_code=503,
        )

    # 3. Monta contexto + chama Claude
    ctx = _build_context(db, project)
    scenario_prompt = _SCENARIO_PROMPT.format(
        valid_keys=", ".join(sorted(VALID_FACTOR_KEYS)),
        candidate_name=project.candidate_name,
        party=", ".join(project.parties) if project.parties else "—",
        office=project.office,
        year=project.election_year,
        municipality=project.municipality or "—",
        state=project.state or "—",
        opponents=", ".join(project.known_opponents) or "—",
        factors_block=ctx["factors_block"],
        dossier_block=ctx["dossier_block"],
        dossier_count=ctx["dossier_count"],
        prompt=prompt,
    )
    raw, model_used = _llm_call(scenario_prompt, json_mode=True)
    parsed = _safe_json(raw)
    if not parsed:
        _persist_call(
            db,
            organization_id=project.organization_id,
            project_id=project.id,
            requested_by=requested_by,
            prompt=prompt,
            agents_consulted=agents_to_consult,
            scenario_id=None,
            scenario_payload={},
            agents_analyses=[],
            rationale=None,
            llm_model_used=model_used,
            status="failed",
            error_message="Falha ao parsear JSON do LLM.",
        )
        raise OrchestratorError("LLM não devolveu JSON parseável.", status_code=502)

    baseline_inputs = _validate_inputs(parsed.get("baseline_inputs"))
    alternative_inputs = _validate_inputs(parsed.get("alternative_inputs"))
    rationale = parsed.get("rationale")
    name = (parsed.get("name") or "Cenário gerado por IA").strip()[:255]
    description = (parsed.get("description") or "").strip() or None

    if not alternative_inputs:
        _persist_call(
            db,
            organization_id=project.organization_id,
            project_id=project.id,
            requested_by=requested_by,
            prompt=prompt,
            agents_consulted=agents_to_consult,
            scenario_id=None,
            scenario_payload=parsed,
            agents_analyses=[],
            rationale=rationale,
            llm_model_used=model_used,
            status="failed",
            error_message="alternative_inputs vazio após validação.",
        )
        raise OrchestratorError(
            "LLM não devolveu fatores válidos para alternative_inputs.",
            status_code=422,
        )

    # 4. Cria cenário + executa
    service = ScenarioService(db)
    scenario = service.create_scenario(
        organization_id=project.organization_id,
        name=name,
        description=description,
        baseline_inputs=baseline_inputs,
        alternative_inputs=alternative_inputs,
        scenario_type="electoral",
    )
    # Encadeia queue_run + execute_run (caminho usado pelo endpoint legado).
    run = service.queue_run(scenario.id, run_label="claude_managed")
    service.start_run(run.id)
    service.execute_run(run.id)

    # 5. Análises multi-agent
    analyses: list[dict] = []
    if agents_to_consult:
        catalog = {spec.role: spec for spec in FIXED_SPECIALISTS}
        scenario_json = json.dumps(
            {
                "name": name,
                "description": description,
                "baseline_inputs": baseline_inputs,
                "alternative_inputs": alternative_inputs,
                "rationale": rationale,
            },
            ensure_ascii=False,
            indent=2,
        )
        for role in agents_to_consult:
            spec = catalog.get(role)
            if spec is None:
                analyses.append(
                    {
                        "agent_role": role,
                        "status": "unknown_agent",
                        "analysis": None,
                    }
                )
                continue
            agent_prompt = _AGENT_PROMPT.format(
                persona_prompt=spec.persona_prompt, scenario_json=scenario_json
            )
            text, _ = _llm_call(agent_prompt, json_mode=False)
            analyses.append(
                {
                    "agent_role": role,
                    "agent_synthetic_name": spec.synthetic_name,
                    "category": spec.category,
                    "confidence_level": spec.confidence_level,
                    "analysis": text.strip() if text else None,
                    "status": "ok" if text else "empty",
                }
            )

    # 6. Persiste audit
    row = _persist_call(
        db,
        organization_id=project.organization_id,
        project_id=project.id,
        requested_by=requested_by,
        prompt=prompt,
        agents_consulted=agents_to_consult,
        scenario_id=scenario.id,
        scenario_payload={
            "name": name,
            "description": description,
            "baseline_inputs": baseline_inputs,
            "alternative_inputs": alternative_inputs,
        },
        agents_analyses=analyses,
        rationale=rationale,
        llm_model_used=model_used,
        status="completed",
    )
    return row
