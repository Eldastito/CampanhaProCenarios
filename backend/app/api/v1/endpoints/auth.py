"""User authentication endpoints: register, login, me."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.core.time import utc_now_naive
from app.db.session import get_db
from app.deps.auth import get_current_user
from app.models.organization import Organization
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse, UserLoginRequest, UserRegisterRequest, UserResponse

router = APIRouter()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(body: UserRegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    # Validate organisation exists
    org = db.get(Organization, body.organization_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    repo = UserRepository(db)
    if repo.email_exists(body.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        id=str(uuid4()),
        email=body.email,
        hashed_password=hash_password(body.password),
        organization_id=body.organization_id,
        role=body.role,
        is_active=True,
        created_at=utc_now_naive(),
    )
    repo.add(user)

    token = create_access_token(
        data={"sub": user.id, "email": user.email, "org": user.organization_id, "role": user.role},
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        organization_id=user.organization_id,
        role=user.role,
    )


@router.post("/login", response_model=TokenResponse, summary="Authenticate and obtain JWT token")
def login(body: UserLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    repo = UserRepository(db)
    user = repo.get_by_email(body.email)

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive.",
        )

    token = create_access_token(
        data={"sub": user.id, "email": user.email, "org": user.organization_id, "role": user.role},
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        organization_id=user.organization_id,
        role=user.role,
    )


@router.get("/me", response_model=UserResponse, summary="Get current authenticated user")
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        user_id=current_user.id,
        email=current_user.email,
        organization_id=current_user.organization_id,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat(),
    )
