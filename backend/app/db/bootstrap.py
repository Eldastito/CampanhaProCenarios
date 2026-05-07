from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import registry  # noqa: F401
from app.models.organization import Organization

DEMO_ORGANIZATION_ID = "org_demo_001"
DEMO_ORGANIZATION_NAME = "Organizacao Demo"

REQUIRED_TABLES = {
    "organizations",
    "predictions",
    "scenarios",
    "scenario_runs",
    "users",
    "campanhapro_events",
    "campanhapro_snapshots",
}


def create_all_tables() -> None:
    """Legacy helper kept only for local/manual fallback."""
    Base.metadata.create_all(bind=engine)


def database_schema_is_ready() -> bool:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    return REQUIRED_TABLES.issubset(existing_tables)


def seed_demo_organization() -> None:
    if settings.app_env.lower() == "production":
        return

    if not database_schema_is_ready():
        return

    with SessionLocal() as session:
        existing = session.get(Organization, DEMO_ORGANIZATION_ID)
        if existing is not None:
            return

        session.add(
            Organization(
                id=DEMO_ORGANIZATION_ID,
                name=DEMO_ORGANIZATION_NAME,
                organization_type="network",
            )
        )
        session.commit()


def healthcheck_database(session: Session) -> bool:
    session.execute(text("SELECT 1"))
    return True
