"""统一错误码：AppError 抛出 → 全局异常处理器转 JSON。"""
from __future__ import annotations

AUTH_REQUIRED = "auth_required"
AUTH_INVALID = "auth_invalid"
TOKEN_EXPIRED = "token_expired"
FORBIDDEN = "forbidden"
NOT_FOUND = "not_found"
VALIDATION_FAILED = "validation_failed"
CONFLICT = "conflict"
RATE_LIMITED = "rate_limited"
LOCKED = "locked"
INTERNAL_ERROR = "internal_error"
