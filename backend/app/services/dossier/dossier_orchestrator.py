"""Orquestrador do pipeline de geração de Dossiê (Fase 3b PRD v2).

Pipeline (executado pelo worker em background):

1. ``tse_service.lookup_candidate`` → identidade oficial, ficha limpa.
2. ``web_research_service.research_candidate`` → biografia, histórico, contexto.
3. ``news_service.fetch_recent_news`` → últimas notícias.
4. Redes sociais (paralelo lógico, sequencial aqui): instagram/facebook
   para próprio (Meta Graph API), twitter/tiktok como manual+LLM.
5. ``legal_search_service.search_legal_issues`` → questões jurídicas
   públicas.
6. **Consolidação LLM** (Claude/OpenAI): junta tudo, separa FATO /
   INFERÊNCIA / HIPÓTESE, gera SWOT, rejection_drivers e strength_drivers.

Graceful degradation:
- Cada serviço pode retornar vazio sem quebrar o pipeline.
- Sem chave LLM, o orquestrador ainda preenche o dossiê com o que
  os serviços retornaram, marca ``confidence_level="low"`` e adiciona
  warning. Status final fica ``ready`` (não ``failed``) — a UI mostra
  cobertura parcial.
- Em qualquer exceção interna o orquestrador captura, registra
  ``error_message`` e status ``failed``.

Idempotência: o orquestrador atualiza o ``CandidateDossier`` existente
em vez de criar um novo. ``last_refreshed_at`` registra cada execução.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from app.core.config import settings
from app.models.dossier import CandidateDossier, DossierSocialSnapshot
from app.services.dossier import (
    facebook_service,
    instagram_service,
    legal_search_service,
    news_service,
    tse_service,
    web_research_service,
)

# tiktok_service e twitter_service são intencionalmente fora deste pipeline:
# adversários entram por POST manual de social-snapshots; candidato próprio
# usa as plataformas Meta (instagram/facebook) via Graph API.

logger = logging.getLogger(__name__)


_CONSOLIDATION_PROMPT = """Você é um analista político sênior. Receba dados brutos coletados
para o dossiê do candidato {candidate_name} ({party} - {office}) e devolva JSON
estruturado em PORTUGUÊS DO BRASIL com as chaves:

{{
  "biography": "string curta (3-5 frases) — só FATO sustentado pelas fontes",
  "political_history": {{ "trajectory": "string", "key_positions": ["string"] }},
  "current_mandates": ["string"],
  "platform_and_proposals": {{ "principais": ["string"], "tom": "string" }},
  "rejection_drivers": ["string — o que sustenta rejeição segundo fontes públicas"],
  "strength_drivers": ["string — o que sustenta apoio segundo fontes públicas"],
  "swot": {{ "strengths": ["string"], "weaknesses": ["string"], "opportunities": ["string"], "threats": ["string"] }},
  "confidence_level": "high | medium | low",
  "consolidation_notes": ["string — anote ambiguidades, ausências, hipóteses"]
}}

Regras inegociáveis:
- Separe FATO, INFERÊNCIA e HIPÓTESE — quando algo for inferência, prefixe com "INFERÊNCIA: ".
- Nunca invente processos judiciais, parentescos ou apoios não documentados.
- Se a evidência for fraca, use "confidence_level": "low".
- Cite fontes só quando houver URL fornecida — não invente URL.

Dados brutos:

TSE: {tse_data}

Pesquisa web: {web_data}

Notícias recentes (últimos 30 dias): {news_data}

Questões jurídicas conhecidas: {legal_data}

Métricas sociais coletadas: {social_data}
"""


def _llm_consolidate(prompt: str) -> str:
    """Tenta consolidar via OpenAI ou Anthropic. Retorna '' se nada configurado.

    Reusa o padrão já estabelecido em ``graph_service`` mas isolado aqui para
    não acoplar este módulo ao serviço de grafo.
    """
    # OpenAI primeiro (mais barato e estável).
    if settings.openai_api_key:
        try:
            import openai

            client = openai.OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model=settings.openai_model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("dossier_openai_error", extra={"error": repr(exc)})

    if settings.anthropic_api_key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            message = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            text_blocks = [b.text for b in message.content if getattr(b, "text", None)]
            return "\n".join(text_blocks)
        except Exception as exc:  # noqa: BLE001
            logger.warning("dossier_anthropic_error", extra={"error": repr(exc)})

    return ""


def _safe_load_json(text: str) -> dict:
    """Extrai bloco JSON do texto da LLM. Tolerante a cercas markdown."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        # remove eventual prefixo "json\n"
        idx = text.find("\n")
        if idx >= 0:
            text = text[idx + 1 :]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Tenta extrair primeiro objeto JSON encontrado.
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {}
        return {}


# ---------------------------------------------------------------------------
# Persistência de snapshots sociais (DossierSocialSnapshot)
# ---------------------------------------------------------------------------


def _persist_social_snapshot(
    db,
    *,
    dossier_id: str,
    platform: str,
    payload: dict,
    source: str,
) -> None:
    """Cria ``DossierSocialSnapshot`` se ``payload`` trouxer handle ou métricas."""
    handle = payload.get("handle")
    if not handle:
        return
    from uuid import uuid4

    snap = DossierSocialSnapshot(
        id=str(uuid4()),
        dossier_id=dossier_id,
        platform=platform,
        handle=str(handle),
        followers=payload.get("followers"),
        posts_last_30d=payload.get("posts_last_30d"),
        engagement_rate=payload.get("engagement_rate"),
        avg_likes=payload.get("avg_likes"),
        avg_comments=payload.get("avg_comments"),
        top_posts=payload.get("top_posts") or [],
        sentiment_distribution=payload.get("sentiment_distribution") or {},
        source=source,
    )
    db.add(snap)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_pipeline(db, dossier: CandidateDossier) -> CandidateDossier:
    """Executa o pipeline para um dossiê já persistido em ``status='queued'``.

    Atualiza o registro in-place (campos estruturados, status, confidence,
    sources, llm_models_used, last_refreshed_at) e dá commit ao final.
    """
    dossier.status = "running"
    db.commit()

    sources: list[str] = []
    errors: list[str] = []
    confidences: list[str] = []
    llm_models_used: list[str] = []

    def _absorb(result):
        sources.extend(result["sources"])
        errors.extend(result["errors"])
        confidences.append(result["confidence"])

    try:
        tse_result = tse_service.lookup_candidate(
            dossier.candidate_name,
            election_year=2026,
            office=dossier.office,
        )
        _absorb(tse_result)

        web_result = web_research_service.research_candidate(
            dossier.candidate_name,
            dossier.party,
            dossier.office,
        )
        _absorb(web_result)

        news_result = news_service.fetch_recent_news(
            dossier.candidate_name, party=dossier.party
        )
        _absorb(news_result)

        legal_result = legal_search_service.search_legal_issues(
            dossier.candidate_name, party=dossier.party
        )
        _absorb(legal_result)

        # Redes sociais — só rodam para o candidato próprio com OAuth.
        # Para adversários, snapshots vêm via endpoint manual separado.
        social_data: dict[str, dict] = {}
        if dossier.candidate_type == "own":
            ig = instagram_service.fetch_own_metrics(dossier.candidate_name)
            fb = facebook_service.fetch_own_page_metrics(dossier.candidate_name)
            for platform_name, r in (("instagram", ig), ("facebook", fb)):
                _absorb(r)
                if isinstance(r["data"], dict) and r["data"]:
                    social_data[platform_name] = r["data"]
                    _persist_social_snapshot(
                        db,
                        dossier_id=dossier.id,
                        platform=platform_name,
                        payload=r["data"],
                        source="api",
                    )

        # Consolidação LLM (graceful fallback se sem chave).
        consolidation: dict = {}
        if settings.openai_api_key or settings.anthropic_api_key:
            prompt = _CONSOLIDATION_PROMPT.format(
                candidate_name=dossier.candidate_name,
                party=dossier.party or "—",
                office=dossier.office,
                tse_data=json.dumps(tse_result["data"], ensure_ascii=False),
                web_data=json.dumps(web_result["data"], ensure_ascii=False),
                news_data=json.dumps(news_result["data"], ensure_ascii=False),
                legal_data=json.dumps(legal_result["data"], ensure_ascii=False),
                social_data=json.dumps(social_data, ensure_ascii=False),
            )
            raw = _llm_consolidate(prompt)
            consolidation = _safe_load_json(raw)
            if settings.openai_api_key:
                llm_models_used.append(settings.openai_model)
            elif settings.anthropic_api_key:
                llm_models_used.append(settings.anthropic_model)

        # Aplica consolidação aos campos do dossiê.
        dossier.biography = consolidation.get("biography") or dossier.biography
        if isinstance(consolidation.get("political_history"), dict):
            dossier.political_history = consolidation["political_history"]
        if isinstance(consolidation.get("current_mandates"), list):
            dossier.current_mandates = consolidation["current_mandates"]
        if isinstance(consolidation.get("platform_and_proposals"), dict):
            dossier.platform_and_proposals = consolidation["platform_and_proposals"]
        if isinstance(consolidation.get("rejection_drivers"), list):
            dossier.rejection_drivers = consolidation["rejection_drivers"]
        if isinstance(consolidation.get("strength_drivers"), list):
            dossier.strength_drivers = consolidation["strength_drivers"]
        if isinstance(consolidation.get("swot"), dict):
            dossier.swot = consolidation["swot"]

        # Dados estruturados não-LLM
        if isinstance(tse_result["data"], dict):
            tse_data = tse_result["data"]
            if tse_data.get("tse_candidate_id"):
                dossier.tse_candidate_id = str(tse_data["tse_candidate_id"])
            if tse_data.get("ficha_limpa_status"):
                dossier.ficha_limpa_status = tse_data["ficha_limpa_status"]
        if isinstance(news_result["data"], list):
            dossier.recent_news = news_result["data"]
        if isinstance(legal_result["data"], list):
            dossier.legal_issues = legal_result["data"]
        if social_data:
            dossier.social_metrics = social_data

        dossier.sources = sorted(set(s for s in sources if s))
        dossier.llm_models_used = llm_models_used

        # Confidence agregada — heurística simples: pior do que coletamos.
        order = {"low": 0, "medium": 1, "high": 2}
        levels = [c for c in confidences if c in order]
        if consolidation.get("confidence_level") in order:
            levels.append(consolidation["confidence_level"])
        if not levels:
            dossier.confidence_level = "low"
        else:
            dossier.confidence_level = min(levels, key=lambda c: order[c])

        dossier.last_refreshed_at = datetime.utcnow()
        dossier.status = "ready"
        dossier.error_message = None
        db.commit()
        return dossier

    except Exception as exc:  # noqa: BLE001
        logger.exception("dossier_pipeline_failed", extra={"dossier_id": dossier.id})
        db.rollback()
        # Reload e marcar failed.
        db.refresh(dossier)
        dossier.status = "failed"
        dossier.error_message = f"{type(exc).__name__}: {exc}"[:500]
        db.commit()
        return dossier
