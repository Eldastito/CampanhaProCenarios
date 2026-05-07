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
def db_session(monkeypatch):
    """Yield a SQLite in-memory session; tears down schema afterwards."""
    test_engine = _make_engine()
    TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=test_engine)

    monkeypatch.setattr(BootstrapService, "initialize", staticmethod(lambda: None))

    with TestingSessionLocal() as session:
        session.add(
            Organization(
                id="org_demo_001",
                name="Organizacao Demo",
                organization_type="network",
            )
        )
        session.commit()
        yield session

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def client(monkeypatch):
    """TestClient with SQLite in-memory DB and a seeded demo org."""
    test_engine = _make_engine()
    TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=test_engine)

    monkeypatch.setattr(BootstrapService, "initialize", staticmethod(lambda: None))

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestingSessionLocal() as db:
        db.add(
            Organization(
                id="org_demo_001",
                name="Organizacao Demo",
                organization_type="network",
            )
        )
        db.commit()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


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
