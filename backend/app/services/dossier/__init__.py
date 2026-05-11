"""Serviços de coleta para o Dossiê de Candidato (Fase 3 PRD v2).

Cada serviço expõe uma função síncrona com a assinatura:

    fn(...) -> DossierServiceResult

Onde ``DossierServiceResult`` é um ``TypedDict`` com:
    - ``data``: dict | list — conteúdo coletado (pode ser vazio).
    - ``sources``: list[str] — URLs ou identificadores das fontes consultadas.
    - ``confidence``: str — "high" | "medium" | "low".
    - ``errors``: list[str] — falhas não fatais (timeout, parse error, etc).

Skeletons da Fase 3a retornam ``DossierServiceResult`` vazio +
``confidence="low"`` para que o orquestrador (Fase 3b) já possa
encadear sem quebrar; implementações reais vêm na 3b sem alterar
a assinatura.

Stack escolhida pelo Emerson (sem custo externo no MVP):
- ``web_research_service``: Claude SDK com tool ``web_search`` nativa.
- ``news_service``: parser de RSS (G1/Folha/UOL/Estadão/Poder360 + Google News RSS).
- ``tse_service``: TSE Open Data público (dadosabertos.tse.jus.br).
- ``instagram_service``: Meta Graph API só para o candidato próprio (OAuth do CampanhaPro).
- ``facebook_service``: Meta Graph API para páginas do próprio.
- ``twitter_service`` e ``tiktok_service``: sem API; coleta para
  adversário é manual + LLM via web_search.
- ``legal_search_service``: web_search via LLM em sites públicos (TSE/TJ).
"""

from typing import TypedDict


class DossierServiceResult(TypedDict):
    data: dict | list
    sources: list[str]
    confidence: str
    errors: list[str]


def empty_result(confidence: str = "low") -> DossierServiceResult:
    """Resultado vazio padrão para skeletons / falhas controladas."""
    return {
        "data": {},
        "sources": [],
        "confidence": confidence,
        "errors": [],
    }
