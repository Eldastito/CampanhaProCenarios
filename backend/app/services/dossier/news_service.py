"""Coleta de notícias via RSS público — sem API paga (Fase 3 PRD v2).

Estratégia (Fase 3b):
- Google News RSS por query: ``https://news.google.com/rss/search?q=...``.
- RSS direto de mídia BR consolidada (G1, Folha, UOL, Estadão, Poder360).
- Parser stdlib (``xml.etree.ElementTree`` ou ``feedparser``).
- Sem chaves nem rate limits comerciais.

Skeleton Fase 3a: retorna lista vazia.
"""

from __future__ import annotations

from app.services.dossier import DossierServiceResult, empty_result


def fetch_recent_news(
    candidate_name: str,
    *,
    party: str | None = None,
    days: int = 30,
    limit: int = 20,
) -> DossierServiceResult:
    """Lista de notícias recentes mencionando o candidato.

    Cada item esperado em ``data`` (Fase 3b):
        {title, url, source, published_at, snippet}

    Fase 3a: skeleton vazio.
    """
    _ = (candidate_name, party, days, limit)
    result = empty_result()
    result["data"] = []
    return result
