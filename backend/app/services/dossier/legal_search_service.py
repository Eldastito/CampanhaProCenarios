"""Busca de questões jurídicas relevantes — sem custo (Fase 3 PRD v2).

Fase 3b: usa Claude com tool ``web_search`` direcionada a sites
públicos (TSE, TRE, TJ, Consultor Jurídico, JusBrasil para tese,
não para processo sigiloso). Cada hit preserva URL e marca como
INFERÊNCIA quando não há decisão pública direta.

Skeleton Fase 3a.
"""

from __future__ import annotations

from app.services.dossier import DossierServiceResult, empty_result


def search_legal_issues(
    candidate_name: str,
    *,
    party: str | None = None,
    uf: str | None = None,
) -> DossierServiceResult:
    """Lista de questões jurídicas conhecidas (processos públicos, decisões).

    Item esperado em ``data`` (Fase 3b):
        {tipo, descricao, status, fonte_url, data, severidade}

    Fase 3a: skeleton vazio.
    """
    _ = (candidate_name, party, uf)
    result = empty_result()
    result["data"] = []
    return result
