import logging
import os

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.bootstrap import seed_demo_organization

logger = logging.getLogger(__name__)


class BootstrapService:
    @staticmethod
    def initialize() -> None:
        configure_logging(
            log_level="DEBUG" if settings.app_debug else "INFO",
            json_logs=settings.app_env.lower() == "production",
        )
        BootstrapService._run_migrations()
        seed_demo_organization()

    @staticmethod
    def _run_migrations() -> None:
        """Run any pending Alembic migrations on startup.

        This ensures the DB schema is always current even when the container
        is hot-reloaded without a full restart (e.g. `uvicorn --reload`).
        """
        try:
            from alembic import command
            from alembic.config import Config

            # Resolve path relative to the project root (two levels up from this file)
            here = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.normpath(os.path.join(here, "..", ".."))
            ini_path = os.path.join(project_root, "alembic", "alembic.ini")

            alembic_cfg = Config(ini_path)
            command.upgrade(alembic_cfg, "head")
            logger.info("db_migrations_applied")
        except Exception as exc:  # pragma: no cover
            logger.warning("db_migration_failed", extra={"error": str(exc)})
