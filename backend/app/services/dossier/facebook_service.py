"""Facebook — Meta Graph API só para páginas do candidato próprio.

Mesmo padrão do ``instagram_service``: adversário entra manual ou
via LLM. Skeleton Fase 3a.
"""

from __future__ import annotations

from app.services.dossier import DossierServiceResult, empty_result


def fetch_own_page_metrics(
    page_id: str, *, access_token: str | None = None
) -> DossierServiceResult:
    """Métricas de página do Facebook do candidato próprio (Graph API).

    Fase 3b preenche em ``data``:
        {page_id, followers, posts_last_30d, engagement_rate,
         avg_reactions, avg_comments, top_posts: [...]}
    """
    _ = (page_id, access_token)
    return empty_result()


def parse_manual_entry(form_payload: dict) -> DossierServiceResult:
    """Adversários: entrada manual de métricas da página."""
    _ = form_payload
    return empty_result()
