from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_campanhapro_ingest_secret(
    x_campanhapro_secret: str | None = Header(default=None),
) -> str:
    if x_campanhapro_secret != settings.campanhapro_ingest_shared_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid integration secret.",
        )
    return x_campanhapro_secret


async def require_backoffice_ingest_secret(
    x_backoffice_secret: str | None = Header(default=None),
) -> str:
    if x_backoffice_secret != settings.backoffice_ingest_shared_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid integration secret.",
        )
    return x_backoffice_secret
