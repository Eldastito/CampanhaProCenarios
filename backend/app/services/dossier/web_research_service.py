"""Pesquisa web via LLM com tool ``web_search`` nativa do Claude (Fase 3b).

Skeleton da Fase 3a: assinatura definida, retorno vazio. A Fase 3b
preenche com chamada real ao Anthropic SDK usando a tool web_search
(custo só dos tokens do Claude, sem chaves de API extras).
"""

from __future__ import annotations

from app.services.dossier import DossierServiceResult, empty_result


def research_candidate(
    candidate_name: str,
    party: str | None,
    office: str,
    *,
    municipio: str | None = None,
    uf: str | None = None,
) -> DossierServiceResult:
    """Coleta biografia, histórico político, propostas e contexto via web search.

    Fase 3a: skeleton — retorna estrutura vazia com confidence=low.
    Fase 3b: invoca Claude com tool ``web_search``, lê resultados,
    separa FATO / INFERÊNCIA / HIPÓTESE e preserva URLs em ``sources``.
    """
    _ = (candidate_name, party, office, municipio, uf)  # usados na Fase 3b
    return empty_result()
