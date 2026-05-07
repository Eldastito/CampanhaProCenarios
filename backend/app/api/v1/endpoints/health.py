from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.bootstrap import healthcheck_database
from app.db.session import get_db

router = APIRouter()


@router.get("", summary="Health check")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "campanhapro-cenarios-api",
    }


@router.get("/ready", summary="Readiness check")
def readiness_check(db: Session = Depends(get_db)) -> dict:
    try:
        healthcheck_database(db)
        return {
            "status": "ready",
            "service": "campanhapro-cenarios-api",
            "dependencies": {
                "database": "ok",
            },
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "service": "campanhapro-cenarios-api",
                "dependencies": {
                    "database": "error",
                },
                "error": str(exc),
            },
        )