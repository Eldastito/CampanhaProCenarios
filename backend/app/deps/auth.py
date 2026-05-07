from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository

_bearer_scheme = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Internal service auth (X-API-Key header)
# ---------------------------------------------------------------------------


def require_internal_api_key(x_api_key: str | None = Header(default=None)) -> str:
    """Validate the X-API-Key header for internal service calls."""
    if not x_api_key or x_api_key != settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal API key.",
        )
    return x_api_key


# ---------------------------------------------------------------------------
# JWT user auth (Bearer token)
# ---------------------------------------------------------------------------


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the JWT Bearer token; return the authenticated User."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(
        credentials.credentials,
        settings.jwt_secret_key,
        settings.jwt_algorithm,
    )
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token: missing subject.",
        )

    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )

    return user


# ---------------------------------------------------------------------------
# Flexible auth — accepts either JWT Bearer token OR X-API-Key
# Used by scenario and prediction endpoints so both frontend (JWT) and
# internal services (API key) can reach them.
# ---------------------------------------------------------------------------


def require_scenario_access(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | str:
    """Accept either a valid JWT Bearer token or a valid X-API-Key.

    Returns the authenticated User (JWT path) or the api key string (key path).
    Raises HTTP 401 if neither is valid.
    """
    # 1. Try JWT
    if credentials is not None:
        payload = decode_access_token(
            credentials.credentials,
            settings.jwt_secret_key,
            settings.jwt_algorithm,
        )
        if payload is not None:
            user_id = payload.get("sub")
            if user_id:
                repo = UserRepository(db)
                user = repo.get_by_id(user_id)
                if user and user.is_active:
                    return user

    # 2. Try API key
    if x_api_key and x_api_key == settings.internal_api_key:
        return x_api_key

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide a Bearer token or X-API-Key header.",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ---------------------------------------------------------------------------
# Role-based access helpers (JWT only)
# ---------------------------------------------------------------------------

_ROLE_HIERARCHY = {"viewer": 0, "analyst": 1, "admin": 2}


def _require_role_level(minimum_role: str):
    """Return a FastAPI dependency that enforces a minimum role level."""
    min_level = _ROLE_HIERARCHY.get(minimum_role, 0)

    def _check(user: User = Depends(get_current_user)) -> User:
        user_level = _ROLE_HIERARCHY.get(user.role, -1)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{minimum_role}' or higher required.",
            )
        return user

    return _check


require_analyst = _require_role_level("analyst")
require_admin = _require_role_level("admin")
