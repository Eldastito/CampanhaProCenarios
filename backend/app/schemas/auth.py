from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Minimum 8 characters")
    organization_id: str
    role: str = Field(default="analyst", pattern="^(admin|analyst|viewer)$")


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    organization_id: str
    role: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    organization_id: str
    role: str
    is_active: bool
    created_at: str
