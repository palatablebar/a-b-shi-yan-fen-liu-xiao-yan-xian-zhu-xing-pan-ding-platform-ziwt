"""批次进度：把执行阶段写到 Redis，前端轮询可见（pending → running → succeeded）。"""
from __future__ import annotations

import json
import time

from worker_src.config.settings import settings


def mark(run_id: int, stage: str, extra: dict | None = None) -> None:
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        payload = {"run_id": run_id, "stage": stage, "at": time.time()}
        if extra:
            payload.update(extra)
        client.set(f"abcheck:run:{run_id}:stage", json.dumps(payload), ex=600)
    except Exception:  # noqa: BLE001 - 进度上报失败不影响计算
        pass
