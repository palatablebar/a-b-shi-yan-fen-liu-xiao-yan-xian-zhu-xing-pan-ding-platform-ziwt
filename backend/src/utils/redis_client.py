"""Redis 客户端（限流计数、worker 心跳）。"""
from __future__ import annotations

import redis

from src.config.settings import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _client
