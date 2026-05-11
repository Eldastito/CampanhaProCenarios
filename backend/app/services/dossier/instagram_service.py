"""Instagram — Meta Graph API só para candidato próprio (Fase 3 PRD v2).

Decisão de produto: sem APIs pagas. Para o **candidato próprio** o
CampanhaPro já tem OAuth Meta, então essa coleta é gratuita via
Graph API. Para **adversários**, métricas vêm por entrada manual no
formulário do dossiê (ver ``DossierSocialSnapshot.source='manual'``)
ou por LLM com web search lendo a página pública (``source='llm_estimate'``).

Skeleton Fase 3a.
"""

from __future__ import annotations

from app.services.dossier import DossierServiceResult, empty_result


def fetch_own_metrics(handle: str, *, access_token: str | None = None) -> DossierServiceResult:
    """Métricas via Meta Graph API para o handle do candidato próprio.

    Fase 3b retorna em ``data``:
        {handle, followers, posts_last_30d, engagement_rate,
         avg_likes, avg_comments, top_posts: [...]}

    Fase 3a: skeleton vazio; ``confidence=low`` quando ``access_token``
    está ausente.
    """
    _ = (handle, access_token)
    return empty_result()


def parse_manual_entry(form_payload: dict) -> DossierServiceResult:
    """Adversários: operador colou handle + followers + observações.

    Valida o payload e devolve como ``DossierServiceResult`` para
    persistir como ``DossierSocialSnapshot(source='manual')``.
    A Fase 3b implementa a validação real.
    """
    _ = form_payload
    return empty_result()
