"""Twitter/X — sem API paga no MVP (Fase 3 PRD v2).

Decisão de produto: a API v2 do X custa USD 100/mês mínimo. Para
ficar dentro do orçamento zero, o dossiê de **qualquer** candidato
(próprio ou adversário) trata Twitter como:
- Entrada manual: operador cola handle + followers.
- Estimativa por LLM: Claude com web_search lê a página pública
  e extrai sentimento/conteúdo dos posts visíveis.

Skeleton Fase 3a.
"""

from __future__ import annotations

from app.services.dossier import DossierServiceResult, empty_result


def parse_manual_entry(form_payload: dict) -> DossierServiceResult:
    """Operador colou handle + métricas básicas. Fase 3b valida."""
    _ = form_payload
    return empty_result()


def estimate_via_llm(handle: str) -> DossierServiceResult:
    """Claude com web_search lê o perfil público e estima sentimento.

    Fase 3b retorna em ``data``:
        {handle, observed_followers, last_posts: [...], sentiment_distribution}
    Sempre marcar como inferência — não promete contadores precisos.
    """
    _ = handle
    return empty_result()
