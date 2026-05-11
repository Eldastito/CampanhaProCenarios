"""Fase 4 PRD v2 — Monte Carlo de probabilidade de eleição.

Testa:
- Determinismo (mesmo seed = mesmo resultado).
- Fatores idênticos → ~50/50.
- Strength 90 vs 30 → forte vence ≥ 95%.
- Coverage baixo (confidence baixa) alarga IC 95%.
- Office com 2 turnos calcula second_round_*.
- Endpoint POST cria + worker eager grava resultado.
- Endpoint GET retorna histórico e detalhe.
- Validação: < 2 candidatos rejeita; > 10 rejeita.
"""

from __future__ import annotations

from sqlalchemy import select

from app.models.election_probability import ElectionProbabilityResult
from app.services.election_probability_service import simulate_election


# ---------------------------------------------------------------------------
# Unit (sem DB)
# ---------------------------------------------------------------------------


def _full_factors(value: float) -> dict[str, float]:
    return {
        k: value
        for k in (
            "vote_intention",
            "rejection",
            "awareness",
            "territorial_strength",
            "alliances",
            "mobilization",
            "digital_sentiment",
            "local_agenda_fit",
            "reputation_risk",
            "operational_efficiency",
            "media_coverage",
            "declared_funding",
        )
    }


def test_simulation_is_deterministic_with_seed():
    cands = [
        {"name": "A", "factors": _full_factors(60), "confidence": 0.6},
        {"name": "B", "factors": _full_factors(40), "confidence": 0.6},
    ]
    r1 = simulate_election(cands, office="Vereador", iterations=2000, seed=123)
    r2 = simulate_election(cands, office="Vereador", iterations=2000, seed=123)
    assert r1 == r2


def test_identical_factors_lead_to_roughly_50_50():
    cands = [
        {"name": "A", "factors": _full_factors(50), "confidence": 0.7},
        {"name": "B", "factors": _full_factors(50), "confidence": 0.7},
    ]
    r = simulate_election(cands, office="Vereador", iterations=4000, seed=1)
    a = next(x for x in r["results"] if x["candidate_name"] == "A")
    b = next(x for x in r["results"] if x["candidate_name"] == "B")
    assert 0.40 <= a["win_probability"] <= 0.60
    assert 0.40 <= b["win_probability"] <= 0.60


def test_strong_candidate_wins_overwhelmingly():
    cands = [
        {"name": "Forte", "factors": _full_factors(90), "confidence": 0.8},
        {"name": "Fraco", "factors": _full_factors(30), "confidence": 0.8},
    ]
    r = simulate_election(cands, office="Vereador", iterations=4000, seed=7)
    forte = next(x for x in r["results"] if x["candidate_name"] == "Forte")
    assert forte["win_probability"] >= 0.95


def test_low_confidence_widens_ci_95():
    high_conf = simulate_election(
        [
            {"name": "A", "factors": _full_factors(60), "confidence": 0.95},
            {"name": "B", "factors": _full_factors(40), "confidence": 0.95},
        ],
        office="Vereador",
        iterations=4000,
        seed=2,
    )
    low_conf = simulate_election(
        [
            {"name": "A", "factors": _full_factors(60), "confidence": 0.05},
            {"name": "B", "factors": _full_factors(40), "confidence": 0.05},
        ],
        office="Vereador",
        iterations=4000,
        seed=2,
    )
    high_a = high_conf["results"][0]["share_ci_95_first_round"]
    low_a = low_conf["results"][0]["share_ci_95_first_round"]
    high_width = high_a[1] - high_a[0]
    low_width = low_a[1] - low_a[0]
    assert low_width > high_width


def test_two_round_office_emits_second_round_metrics():
    cands = [
        {"name": "A", "factors": _full_factors(40), "confidence": 0.6},
        {"name": "B", "factors": _full_factors(40), "confidence": 0.6},
        {"name": "C", "factors": _full_factors(40), "confidence": 0.6},
    ]
    r = simulate_election(cands, office="Governador", iterations=2000, seed=5)
    assert r["two_rounds"] is True
    for item in r["results"]:
        assert item["second_round_qualification_probability"] is not None


def test_simple_majority_office_omits_second_round_metrics():
    cands = [
        {"name": "A", "factors": _full_factors(40), "confidence": 0.6},
        {"name": "B", "factors": _full_factors(40), "confidence": 0.6},
    ]
    r = simulate_election(cands, office="Vereador", iterations=1000, seed=5)
    assert r["two_rounds"] is False
    for item in r["results"]:
        assert item["second_round_qualification_probability"] is None


# ---------------------------------------------------------------------------
# Endpoints (worker eager)
# ---------------------------------------------------------------------------


def _create_project(client, headers, *, campaign_id: str = "cmp_election") -> str:
    payload = {
        "organization_id": "org_demo_001",
        "campaign_id": campaign_id,
        "name": "Projeto Eleição",
        "election_year": 2026,
        "office": "Prefeito",
        "candidate_name": "Maria",
        "parties": ["PT"],
        "known_opponents": [],
    }
    resp = client.post("/api/v1/political/projects", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_post_simulation_runs_worker_and_completes(
    client, db_session, analyst_auth_headers
):
    project_id = _create_project(client, analyst_auth_headers)
    body = {
        "office": "Vereador",
        "iterations": 1000,
        "seed": 42,
        "candidates": [
            {"name": "A", "factors": _full_factors(70), "confidence": 0.7},
            {"name": "B", "factors": _full_factors(30), "confidence": 0.7},
        ],
    }
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/election-probability",
        json=body,
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 202, resp.text
    rid = resp.json()["result_id"]

    fresh = db_session.execute(
        select(ElectionProbabilityResult).filter_by(id=rid)
    ).scalar_one()
    assert fresh.status == "completed"
    assert fresh.completed_at is not None
    names = {r["candidate_name"] for r in fresh.output_results}
    assert names == {"A", "B"}


def test_get_simulation_detail(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_get")
    create = client.post(
        f"/api/v1/political/projects/{project_id}/election-probability",
        json={
            "office": "Vereador",
            "iterations": 500,
            "seed": 1,
            "candidates": [
                {"name": "A", "factors": _full_factors(60), "confidence": 0.7},
                {"name": "B", "factors": _full_factors(40), "confidence": 0.7},
            ],
        },
        headers=analyst_auth_headers,
    )
    rid = create.json()["result_id"]
    detail = client.get(
        f"/api/v1/political/projects/{project_id}/election-probability/{rid}",
        headers=analyst_auth_headers,
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "completed"
    assert len(body["output_results"]) == 2
    assert "share_ci_95_first_round" in body["output_results"][0]


def test_history_listing(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_hist")
    for _ in range(2):
        client.post(
            f"/api/v1/political/projects/{project_id}/election-probability",
            json={
                "office": "Vereador",
                "iterations": 300,
                "candidates": [
                    {"name": "A", "factors": _full_factors(50), "confidence": 0.5},
                    {"name": "B", "factors": _full_factors(50), "confidence": 0.5},
                ],
            },
            headers=analyst_auth_headers,
        )
    listing = client.get(
        f"/api/v1/political/projects/{project_id}/election-probability",
        headers=analyst_auth_headers,
    )
    assert listing.status_code == 200
    items = listing.json()
    assert len(items) == 2
    for item in items:
        assert item["status"] == "completed"


def test_validation_rejects_single_candidate(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_val")
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/election-probability",
        json={
            "office": "Vereador",
            "candidates": [{"name": "Solo", "factors": {}, "confidence": 0.5}],
        },
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 422


def test_validation_rejects_eleven_candidates(client, analyst_auth_headers):
    project_id = _create_project(client, analyst_auth_headers, campaign_id="cmp_max")
    resp = client.post(
        f"/api/v1/political/projects/{project_id}/election-probability",
        json={
            "office": "Vereador",
            "candidates": [
                {"name": f"C{i}", "factors": {}, "confidence": 0.5} for i in range(11)
            ],
        },
        headers=analyst_auth_headers,
    )
    assert resp.status_code == 422
