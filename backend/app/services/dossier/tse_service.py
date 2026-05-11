"""TSE Open Data — público, sem chave (Fase 3 PRD v2).

Base: ``https://dadosabertos.tse.jus.br/api`` (configurável via
``settings.tse_api_base_url``). Endpoints relevantes para o dossiê:
- Candidato registrado (consulta-cand): nome, partido, número, cargo, status.
- Ficha Limpa: status derivado de ``situacao_candidatura`` + decisões judiciais.
- Prestação de contas: receitas/despesas declaradas (quando publicado).

Skeleton Fase 3a: retorna estrutura vazia.
"""

from __future__ import annotations

from app.services.dossier import DossierServiceResult, empty_result


def lookup_candidate(
    candidate_name: str,
    *,
    election_year: int,
    office: str,
    uf: str | None = None,
    municipio: str | None = None,
) -> DossierServiceResult:
    """Procura candidato no TSE Open Data.

    Fase 3b retorna em ``data``:
        {tse_candidate_id, nome_urna, partido, numero, situacao,
         ficha_limpa_status, prestacao_contas_url}

    Fase 3a: skeleton vazio.
    """
    _ = (candidate_name, election_year, office, uf, municipio)
    return empty_result()
