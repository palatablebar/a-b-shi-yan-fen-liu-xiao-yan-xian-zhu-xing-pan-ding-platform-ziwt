"""限流：分析批次触发按「用户 × 分钟」限流（Redis 计数），超限返回 429。

写在中间件层而不是业务层：所有 /experiments/{id}/runs 的 POST 统一受控。
"""
from __future__ import annotations

import re
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.config.settings import settings
from src.utils.jwt import decode_token
from src.utils.redis_client import get_redis

_RUN_PATH = re.compile(r"^(?:/api)?/experiments/\d+/runs$")


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("bearer "):
        return None
    return header.split(" ", 1)[1].strip()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method != "POST" or not _RUN_PATH.match(request.url.path):
            return await call_next(request)
        token = _bearer(request)
        if not token:
            return await call_next(request)  # 未登录交给认证层返回 401
        try:
            payload = decode_token(token)
        except Exception:  # noqa: BLE001 - 令牌无效同样交给认证层
            return await call_next(request)
        actor = str(payload.get("sub", "anonymous"))
        window = int(time.time() // 60)
        key = f"abcheck:ratelimit:run:{actor}:{window}"
        try:
            client = get_redis()
            count = client.incr(key)
            if count == 1:
                client.expire(key, 90)
        except Exception:  # noqa: BLE001 - Redis 抖动时不阻塞主流程
            return await call_next(request)
        if count > settings.runs_per_minute:
            return JSONResponse(
                status_code=429,
                content={
                    "code": "rate_limited",
                    "message": f"分析触发过于频繁（>{settings.runs_per_minute} 次/分钟），请稍后再试",
                    "detail": key,
                },
                headers={"Retry-After": "60"},
            )
        return await call_next(request)
