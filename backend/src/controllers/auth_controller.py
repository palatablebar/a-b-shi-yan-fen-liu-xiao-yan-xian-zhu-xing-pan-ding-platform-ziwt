"""认证控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.middlewares.auth import get_current_user
from src.models.user import User
from src.schemas.auth import LoginRequest, LoginResponse, UserOut
from src.services.auth_service import AuthService


def login(payload: LoginRequest, request: Request, db: Session) -> LoginResponse:
    service = AuthService(db)
    user, token = service.login(str(payload.email), payload.password)
    # 审计由 AuditContextMiddleware 统一落库：这里只把 actor 写进 request.state
    request.state.actor_email = user.email
    request.state.actor_role = user.role
    request.state.audit_detail = {"role": user.role}
    return LoginResponse(access_token=token, user=service.serialize(user))


def me(user: User) -> UserOut:
    return UserOut.from_model(user)


__all__ = ["login", "me", "get_current_user"]
