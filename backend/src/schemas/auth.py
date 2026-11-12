"""认证相关 schema。"""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from src.constants.roles import ROLE_LABELS, role_permissions


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    role_label: str
    permissions: list[str]

    @classmethod
    def from_model(cls, user) -> "UserOut":
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            role_label=ROLE_LABELS.get(user.role, user.role),
            permissions=role_permissions(user.role),
        )


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
