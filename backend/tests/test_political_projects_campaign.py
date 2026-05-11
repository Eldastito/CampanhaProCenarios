"""Fase 0 do PRD v2 — campaign_id em political_projects.

Cobre:
- Criação sem campaign_id explícito → backfill com o id do projeto.
- Criação com campaign_id explícito → respeita valor enviado.
- Múltiplos projetos podem compartilhar campaign_id (não consome slot novo).
- Quota MVP de 10 campanhas distintas por organização.
"""

from __future__ import annotations


def _project_payload(**overrides) -> dict:
    base = {
        "organization_id": "org_demo_001",
        "name": "Campanha Teste",
        "election_year": 2026,
        "office": "Prefeito",
        "candidate_name": "Fulano",
        "parties": ["Partido X"],
        "known_opponents": [],
    }
    base.update(overrides)
    return base


def test_create_project_without_campaign_id_defaults_to_project_id(
    client, analyst_auth_headers
):
    resp = client.post(
        "/api/v1/political/projects",
        json=_project_payload(),
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["campaign_id"] == body["id"]


def test_create_project_with_explicit_campaign_id(client, analyst_auth_headers):
    resp = client.post(
        "/api/v1/political/projects",
        json=_project_payload(campaign_id="cmp_alpha"),
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["campaign_id"] == "cmp_alpha"


def test_multiple_projects_same_campaign_id_do_not_consume_extra_slots(
    client, analyst_auth_headers
):
    # Cria 10 projetos todos na mesma campanha — só consome 1 slot.
    for idx in range(10):
        resp = client.post(
            "/api/v1/political/projects",
            json=_project_payload(name=f"Cenario {idx}", campaign_id="cmp_shared"),
            headers=analyst_auth_headers,
        )
        assert resp.status_code == 201, resp.text

    # Ainda restam 9 slots — criar uma nova campanha distinta deve passar.
    resp = client.post(
        "/api/v1/political/projects",
        json=_project_payload(name="Campanha Extra", campaign_id="cmp_other"),
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 201, resp.text


def test_mvp_quota_blocks_eleventh_distinct_campaign(client, analyst_auth_headers):
    for idx in range(10):
        resp = client.post(
            "/api/v1/political/projects",
            json=_project_payload(
                name=f"Campanha {idx}", campaign_id=f"cmp_{idx:02d}"
            ),
            headers=analyst_auth_headers,
        )
        assert resp.status_code == 201, resp.text

    # 11ª campanha distinta → 403.
    resp = client.post(
        "/api/v1/political/projects",
        json=_project_payload(name="Estouro", campaign_id="cmp_overflow"),
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 403
    assert "Limite MVP" in resp.json()["detail"]


def test_quota_does_not_block_existing_campaign_after_limit(
    client, analyst_auth_headers
):
    # Preenche a quota com 10 campanhas distintas.
    for idx in range(10):
        client.post(
            "/api/v1/political/projects",
            json=_project_payload(
                name=f"Campanha {idx}", campaign_id=f"cmp_{idx:02d}"
            ),
            headers=analyst_auth_headers,
        )
    # Adicionar outro projeto numa campanha já existente continua permitido.
    resp = client.post(
        "/api/v1/political/projects",
        json=_project_payload(
            name="Cenário extra na cmp_00", campaign_id="cmp_00"
        ),
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 201, resp.text
