"""TikTok — sem API viável no MVP (Fase 3 PRD v2).

Decisão de produto idêntica ao ``twitter_service``: TikTok não tem
API pública útil para análise de adversários e os scrapers comerciais
(Apify etc.) custam mensalidade. No MVP:
- Entrada manual no formulário do dossiê.
- Estimativa via LLM com web_search.

Skeleton Fase 3a.
"""

from __future__ import annotations

from app.services.dossier import DossierServiceResult, empty_result


def parse_manual_entry(form_payload: dict) -> DossierServiceResult:
    """Operador colou handle + métricas básicas."""
    _ = form_payload
    return empty_result()


def estimate_via_llm(handle: str) -> DossierServiceResult:
    """Claude com web_search visita o perfil TikTok público e descreve."""
    _ = handle
    return empty_result()
