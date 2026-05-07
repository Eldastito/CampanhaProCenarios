from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
    # Connection pool tuning for production PostgreSQL.
    # These parameters are ignored by SQLite (used in tests via their own engine).
    pool_size=5,        # persistent connections kept open
    max_overflow=10,    # extra connections allowed under peak load
    pool_timeout=30,    # seconds to wait before raising OperationalError
    pool_recycle=1800,  # recycle connections every 30 min to avoid stale TCP
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
