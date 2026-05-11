"""Fase 6 PRD v2 — Claude Managed (orquestrador de cenários).

Cobre:
- 503 quando nenhuma chave LLM configurada.
- Geração feliz: prompt → cenário criado + executado + análises por agente.
  Mocka ``_llm_call`` para não bater no provedor real.
- Validação: alternative_inputs vazio após filtragem → 422.
- Chaves fora das 12 válidas são descartadas (não vazam para Scenario).
- Valores fora de [0, 100] são clampados.
- Rate limit: 11ª chamada na mesma hora → 429.
- Endpoint /agents lista os 17 especialistas com tools_available.
- Endpoint /rate-limit reflete uso atual.
- Audit log scenario_orchestrator.completed emitido.
"""

from __future__ import annotations

import json

from sqlalchemy import select

from app.models.political import PoliticalAuditLog
from app.models.scenario import Scenario
from app.models.scenario_orchestrator import ScenarioOrchestratorCall
from app.services import scenario_orchestrator_service as svc


def _create_project(client, headers, *, campaign_id: str = "cmp_orch") -> str:
    payload = {
        "organization_id": "org_demo_001",
        "campaign_id": campaign_id,
        "name": "Projeto Orchestrator",
        "election_year": 2026,
        "office": "Prefeito",
        "candidate_name": "Maria",
        "parties": ["PT"],
        "known_opponents": ["João"],
    }
    resp = client.post("/api/v1/political/projects", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _llm_factory(scenario_json: str, agent_text: str = "Análise OK"):
    """Retorna função compatível com a assinatura de _llm_call.

    Primeira chamada (json_mode=True) → scenario JSON. Demais → agent_text.
    """
    state = {"call_count": 0}

    def fake(prompt: str, *, json_mode: bool = False):  # noqa: ARG001
        state["call_count"] += 1
        if json_mode:
            return scenario_json, "gpt-4o-mini-test"
        return agent_text, "gpt-4o-mini-test"

    return fake


# ---------------------------------------------------------------------------
# 503 sem chaves LLM
# ---------------------------------------------------------------------------


def test_orchestrator_503_when_no_llm_keys(client, analyst_auth_headers, monkeypatch):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_no_llm")
    # Garante zero chaves.
    monkeypatch.setattr(svc.settings, "openai_api_key", None)
    monkeypatch.setattr(svc.settings, "anthropic_api_key", None)
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/scenarios/generate",
        json={"prompt": "Simule um cenário de teste."},
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 503
    assert "Claude Managed" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


_HAPPY_SCENARIO_JSON = json.dumps(
    {
        "name": "Mais presença no bairro X",
        "description": "Dobramos visitas e ampliamos engajamento.",
        "baseline_inputs": {
            "vote_intention": 40,
            "awareness": 50,
            "rejection": 25,
        },
        "alternative_inputs": {
            "vote_intention": 55,
            "awareness": 65,
            "rejection": 22,
            "mobilization": 70,
            "ignored_key_should_drop": 999,
        },
        "rationale": (
            "FATO: pesquisa indica 40% intenção. "
            "INFERÊNCIA: aumento de presença típicamente eleva mobilização. "
            "HIPÓTESE: 15pp em vote_intention em 3 semanas é otimista."
        ),
    }
)


def test_orchestrator_happy_path_creates_scenario_and_consults_agents(
    client, db_session, analyst_auth_headers, monkeypatch
):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_happy")
    monkeypatch.setattr(svc.settings, "openai_api_key", "fake-key")
    monkeypatch.setattr(svc, "_llm_call", _llm_factory(_HAPPY_SCENARIO_JSON))

    resp = client.post(
        f"/api/v1/political/projects/{project_id}/scenarios/generate",
        json={
            "prompt": "Simule presença dobrada no bairro X por 3 semanas.",
            "agents_to_consult": [
                "Análise de Adversários",
                "Mídia (Porta-voz)",
                "Crise / Reputação",
            ],
        },
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["scenario_id"] is not None
    # Chaves inválidas foram filtradas.
    alt = body["scenario_payload"]["alternative_inputs"]
    assert "ignored_key_should_drop" not in alt
    assert alt["vote_intention"] == 55
    assert alt["mobilization"] == 70
    # 3 análises de especialista, todas com texto.
    assert len(body["agents_analyses"]) == 3
    assert all(a["status"] == "ok" for a in body["agents_analyses"])
    # Cenário foi de fato persistido.
    sc = db_session.execute(
        select(Scenario).filter_by(id=body["scenario_id"])
    ).scalar_one()
    assert sc.name == "Mais presença no bairro X"


# ---------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------


def test_orchestrator_422_when_alternative_inputs_invalid(
    client, analyst_auth_headers, monkeypatch
):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_bad")
    monkeypatch.setattr(svc.settings, "openai_api_key", "fake-key")
    bad_json = json.dumps(
        {
            "name": "Fora",
            "alternative_inputs": {"invalida_x": 50, "outra": 60},
            "rationale": "FATO: prompt fora do escopo.",
        }
    )
    monkeypatch.setattr(svc, "_llm_call", _llm_factory(bad_json))
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/scenarios/generate",
        json={"prompt": "Cenário inválido com chaves erradas."},
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 422


def test_orchestrator_clamps_out_of_range_values(
    client, analyst_auth_headers, db_session, monkeypatch
):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_clamp")
    monkeypatch.setattr(svc.settings, "openai_api_key", "fake-key")
    extreme = json.dumps(
        {
            "name": "Cenário extremo",
            "alternative_inputs": {
                "vote_intention": 150,
                "rejection": -20,
                "awareness": 75,
            },
            "rationale": "FATO: dados extremos.",
        }
    )
    monkeypatch.setattr(svc, "_llm_call", _llm_factory(extreme))
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/scenarios/generate",
        json={"prompt": "Cenário com valores extremos para teste."},
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 200
    alt = resp.json()["scenario_payload"]["alternative_inputs"]
    assert alt["vote_intention"] == 100  # clamp top
    assert alt["rejection"] == 0  # clamp bottom
    assert alt["awareness"] == 75


# ---------------------------------------------------------------------------
# Rate limit
# ---------------------------------------------------------------------------


def test_orchestrator_rate_limit_blocks_after_10_calls(
    client, db_session, analyst_auth_headers, monkeypatch
):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_rl")
    monkeypatch.setattr(svc.settings, "openai_api_key", "fake-key")
    monkeypatch.setattr(svc, "_llm_call", _llm_factory(_HAPPY_SCENARIO_JSON))

    for i in range(svc.RATE_LIMIT_PER_PROJECT_PER_HOUR):
        resp = client.post(
            f"/api/v1/political/projects/{project_id}/scenarios/generate",
            json={
                "prompt": f"Cenário número {i} para teste de rate limit.",
                "agents_to_consult": [],
            },
            headers=analyst_auth_headers,
        )
        assert resp.status_code == 200, f"falha na chamada {i}: {resp.text}"

    # 11ª deve ser bloqueada.
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/scenarios/generate",
        json={"prompt": "Décima primeira tentativa deveria falhar."},
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 429
    assert "Rate limit" in resp.json()["detail"]

    # Registro rate_limited persistido.
    rate_rows = db_session.execute(
        select(ScenarioOrchestratorCall).filter_by(status="rate_limited")
    ).scalars().all()
    assert len(rate_rows) == 1


# ---------------------------------------------------------------------------
# /agents e /rate-limit
# ---------------------------------------------------------------------------


def test_list_available_agents_returns_17_specialists(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_ag")
    resp = client.get(
        f"/api/v1/political/projects/{project_id}/scenarios/agents",
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 17
    # Pelo menos os 3 com tools_available estão completos.
    with_tools = [a for a in body if a["tools_available"]]
    assert len(with_tools) >= 3
    for a in with_tools:
        assert "dossier_lookup" in a["tools_available"]


def test_rate_limit_endpoint_reports_usage(
    client, analyst_auth_headers, monkeypatch
):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_rli")
    monkeypatch.setattr(svc.settings, "openai_api_key", "fake-key")
    monkeypatch.setattr(svc, "_llm_call", _llm_factory(_HAPPY_SCENARIO_JSON))

    for _ in range(2):
        client.post(
            f"/api/v1/political/projects/{project_id}/scenarios/generate",
            json={"prompt": "Teste rate limit endpoint reports.", "agents_to_consult": []},
            headers=analyst_auth_headers,
        )

    resp = client.get(
        f"/api/v1/political/projects/{project_id}/scenarios/rate-limit",
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit_per_hour"] == 10
    assert body["used_last_hour"] == 2
    assert body["remaining"] == 8


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


def test_audit_log_scenario_orchestrator_completed(
    client, db_session, analyst_auth_headers, monkeypatch
):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_audit_orch")
    monkeypatch.setattr(svc.settings, "openai_api_key", "fake-key")
    monkeypatch.setattr(svc, "_llm_call", _llm_factory(_HAPPY_SCENARIO_JSON))
    client.post(
        f"/api/v1/political/projects/{project_id}/scenarios/generate",
        json={"prompt": "Cenário para audit log.", "agents_to_consult": []},
        headers=analyst_auth_headers,
    )
    logs = db_session.execute(
        select(PoliticalAuditLog).filter_by(action="scenario_orchestrator.completed")
    ).scalars().all()
    assert len(logs) >= 1


# ---------------------------------------------------------------------------
# Listagem histórico
# ---------------------------------------------------------------------------


def test_orchestrator_history_listing(
    client, analyst_auth_headers, monkeypatch
):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_hist_orch")
    monkeypatch.setattr(svc.settings, "openai_api_key", "fake-key")
    monkeypatch.setattr(svc, "_llm_call", _llm_factory(_HAPPY_SCENARIO_JSON))
    for i in range(3):
        client.post(
            f"/api/v1/political/projects/{project_id}/scenarios/generate",
            json={"prompt": f"Cenário {i} hist.", "agents_to_consult": []},
            headers=analyst_auth_headers,
        )
    resp = client.get(
        f"/api/v1/political/projects/{project_id}/scenarios",
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3
    assert all(r["status"] == "completed" for r in body)


# ---------------------------------------------------------------------------
# Prompt curto demais → 422 do Pydantic
# ---------------------------------------------------------------------------


def test_short_prompt_rejected_by_schema(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_short")
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/scenarios/generate",
        json={"prompt": "curto"},
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 422
