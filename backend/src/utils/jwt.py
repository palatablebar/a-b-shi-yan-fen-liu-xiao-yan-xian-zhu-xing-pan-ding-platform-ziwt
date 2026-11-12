"""JWT 签发与校验（access token，2 小时）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from src.config.settings import settings
from src.constants import error_codes as codes
from src.utils.errors import AppError


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: int, role: str, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "email": email,
        "type": "access",
        "iat": _now(),
        "exp": _now() + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AppError(codes.TOKEN_EXPIRED, "登录已过期，请重新登录", str(exc), 401) from exc
    except jwt.PyJWTError as exc:
        raise AppError(codes.AUTH_INVALID, "登录状态无效，请重新登录", str(exc), 401) from exc

    if payload.get("type") != expected_type:
        raise AppError(codes.AUTH_INVALID, "令牌类型不正确", f"expected {expected_type}", 401)
    return payload
