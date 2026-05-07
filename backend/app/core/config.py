import json
import os
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_cors_origins() -> list[str]:
    """Read BACKEND_CORS_ORIGINS from env directly (bypasses pydantic-settings).

    Accepts comma-separated string OR JSON array string. Returns empty list when unset.
    """
    raw = os.environ.get("BACKEND_CORS_ORIGINS", "")
    if isinstance(raw, list):
        return [str(o).strip() for o in raw if str(o).strip()]
    raw = (raw or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(o).strip() for o in parsed if str(o).strip()]
        except json.JSONDecodeError:
            pass
    return [o.strip() for o in raw.split(",") if o.strip()]


_INSECURE_SECRET_DEFAULTS = frozenset(
    {
        "change-me",
        "dev-internal-key",
        "dev-forge-secret",
        "dev-jwt-secret",
        "dev-campanhapro-secret",
        "dev-backoffice-secret",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="FORGE Scenario Lab API", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="forge_scenario_lab", alias="POSTGRES_DB")
    postgres_user: str = Field(default="postgres", alias="POSTGRES_USER")
    postgres_password: str = Field(default="postgres", alias="POSTGRES_PASSWORD")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # Anthropic Claude API (used for graph entity extraction and simulation)
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-haiku-4-5-20251001", alias="ANTHROPIC_MODEL")

    # FORGE server-to-server secret (X-Forge-Secret header)
    forge_ingest_shared_secret: str = Field(
        default="dev-forge-secret",
        alias="FORGE_INGEST_SHARED_SECRET",
    )

    # CampanhaPro server-to-server secret (X-CampanhaPro-Secret header)
    campanhapro_ingest_shared_secret: str = Field(
        default="dev-campanhapro-secret",
        alias="CAMPANHAPRO_INGEST_SHARED_SECRET",
    )

    # BackOffice server-to-server secret (X-BackOffice-Secret header)
    backoffice_ingest_shared_secret: str = Field(
        default="dev-backoffice-secret",
        alias="BACKOFFICE_INGEST_SHARED_SECRET",
    )

    # Internal service API key (X-API-Key header) — separate from ingest secret
    internal_api_key: str = Field(
        default="dev-internal-key",
        alias="INTERNAL_API_KEY",
    )

    # JWT configuration for user-facing auth
    jwt_secret_key: str = Field(
        default="dev-jwt-secret",
        alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(
        default=480,
        alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_env.lower() != "production":
            return self

        errors: list[str] = []

        if self.forge_ingest_shared_secret in _INSECURE_SECRET_DEFAULTS:
            errors.append("FORGE_INGEST_SHARED_SECRET must be set to a secure value in production")

        if self.campanhapro_ingest_shared_secret in _INSECURE_SECRET_DEFAULTS:
            errors.append("CAMPANHAPRO_INGEST_SHARED_SECRET must be set to a secure value in production")

        if self.backoffice_ingest_shared_secret in _INSECURE_SECRET_DEFAULTS:
            errors.append("BACKOFFICE_INGEST_SHARED_SECRET must be set to a secure value in production")

        if self.internal_api_key in _INSECURE_SECRET_DEFAULTS:
            errors.append("INTERNAL_API_KEY must be set to a secure value in production")

        if self.jwt_secret_key in _INSECURE_SECRET_DEFAULTS:
            errors.append("JWT_SECRET_KEY must be set to a secure value in production")

        if errors:
            raise ValueError(
                "Insecure production configuration detected:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        return self

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
