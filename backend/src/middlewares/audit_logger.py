"""审计：对写操作统一落 audit_logs（不改业务返回，失败只记日志）。"""
from __future__ import annotations

import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.config.database import SessionLocal
from src.models.audit_log import AuditLog
from src.utils.jwt import decode_token
from src.utils.logger import get_logger

logger = get_logger("abcheck.audit")

_MUTATING = {"POST", "PATCH", "PUT", "DELETE"}


def _action_for(method: str, path: str) -> str:
    normalized = path
    if normalized.startswith("/api/"):
        normalized = normalized[4:]
    if re.match(r"^/auth/login$", normalized):
        return "auth.login"
    if re.match(r"^/experiments$", normalized):
        return "experiment.create"
    if re.match(r"^/experiments/\d+$", normalized):
        return "experiment.update" if method == "PATCH" else "experiment.delete"
    if re.match(r"^/experiments/\d+/runs$", normalized):
        return "run.create"
    if re.match(r"^/experiments/\d+/decisions$", normalized):
        return "decision.create"
    if re.match(r"^/metrics/\d+$", normalized):
        return "metric.update"
    if re.match(r"^/experiments/\d+/(variants|assignments)$", normalized):
        return "experiment.data_write"
    return f"{method.lower()}.{normalized}"


class AuditContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.method not in _MUTATING:
            return response
        path = request.url.path
        if path.startswith("/api/health"):
            return response
        try:
            actor_email = getattr(request.state, "actor_email", None)
            actor_role = getattr(request.state, "actor_role", None)
            if not actor_email:
                token = (request.headers.get("authorization") or "")
                token = token.split(" ", 1)[1].strip() if token.lower().startswith("bearer ") else None
                if token:
                    try:
                        payload = decode_token(token)
                        actor_email = payload.get("email")
                        actor_role = payload.get("role")
                    except Exception:  # noqa: BLE001
                        actor_email = None
            actor_email = actor_email or "anonymous"
            actor_role = actor_role or ""
            detail = getattr(request.state, "audit_detail", None) or {}
            with SessionLocal() as db:
                db.add(
                    AuditLog(
                        actor_email=str(actor_email),
                        actor_role=str(actor_role),
                        action=_action_for(request.method, path)[:64],
                        method=request.method,
                        path=path[:240],
                        status_code=response.status_code,
                        detail=detail,
                        ip=(request.client.host if request.client else "")[:64],
                    )
                )
                db.commit()
        except Exception as exc:  # noqa: BLE001 - 审计失败绝不阻塞响应
            logger.warning("audit_write_failed path=%s error=%s", path, exc)
        return response
