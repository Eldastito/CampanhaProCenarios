from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import registry  # noqa: F401
from app.models.organization import Organization
from app.services.bootstrap_service import BootstrapService

_INTERNAL_API_KEY = settings.internal_api_key
_CAMPANHAPRO_SECRET = settings.campanhapro_ingest_shared_secret


def _make_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture()
def _shared_engine(monkeypatch):
    """Engine SQLite in-memory único compartilhado entre ``db_session`` e ``client``.

    Necessário para que testes que combinam chamadas via API e queries diretas
    em SQLAlchemy enxerguem os mesmos dados. Antes, cada fixture criava o
    próprio engine — quem escrevia via API populava um SQLite, quem lia via
    ORM lia outro, e asserts cruzados ficavam invisíveis. A organização
    ``org_demo_001`` é semeada aqui uma única vez por teste para evitar
    colisão de UNIQUE quando ambas as fixtures forem solicitadas.

    Também repatcheia ``app.db.session.SessionLocal`` para usar este engine,
    permitindo que workers Celery (eager mode na Fase 2 PRD v2) abram
    sessão própria sem cair no Postgres de produção.
    """
    engine = _make_engine()
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(BootstrapService, "initialize", staticmethod(lambda: None))

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    # Patch das duas referências que workers podem importar.
    monkeypatch.setattr("app.db.session.SessionLocal", SessionLocal)
    monkeypatch.setattr("app.workers.snapshot_tasks.SessionLocal", SessionLocal)
    monkeypatch.setattr("app.workers.dossier_tasks.SessionLocal", SessionLocal)
    monkeypatch.setattr("app.workers.election_tasks.SessionLocal", SessionLocal)

    with SessionLocal() as session:
        session.add(
            Organization(
                id="org_demo_001",
                name="Organizacao Demo",
                organization_type="network",
            )
        )
        session.commit()

    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _celery_eager(monkeypatch):
    """Celery roda síncrono em testes — sem broker, sem worker."""
    from app.workers.celery_app import celery_app

    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)


@pytest.fixture()
def db_session(_shared_engine):
    """Yield a SQLite in-memory session; tears down schema afterwards."""
    TestingSessionLocal = sessionmaker(
        bind=_shared_engine, autoflush=False, autocommit=False
    )
    with TestingSessionLocal() as session:
        yield session


@pytest.fixture()
def client(_shared_engine):
    """TestClient with SQLite in-memory DB and a seeded demo org."""
    TestingSessionLocal = sessionmaker(
        bind=_shared_engine, autoflush=False, autocommit=False
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def api_key_headers() -> dict[str, str]:
    """Headers for internal service calls (X-API-Key)."""
    return {"x-api-key": _INTERNAL_API_KEY}


def campanhapro_secret_headers() -> dict[str, str]:
    """Headers for CampanhaPro ingest calls (X-CampanhaPro-Secret)."""
    return {"x-campanhapro-secret": _CAMPANHAPRO_SECRET}


def make_jwt_token(user_id: str, org_id: str, role: str = "analyst") -> str:
    return create_access_token(
        data={"sub": user_id, "org": org_id, "role": role},
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        expires_delta=timedelta(minutes=30),
    )


def jwt_headers(user_id: str = "user_test_001", org_id: str = "org_demo_001", role: str = "analyst") -> dict[str, str]:
    token = make_jwt_token(user_id, org_id, role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def analyst_user(client) -> dict:
    """Register and return an analyst user via the API."""
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "analyst@test.example",
            "password": "securepass123",
            "organization_id": "org_demo_001",
            "role": "analyst",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture()
def analyst_auth_headers(analyst_user) -> dict[str, str]:
    token = analyst_user["access_token"]
    return {"Authorization": f"Bearer {token}"}
