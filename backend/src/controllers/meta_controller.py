"""元信息控制器：概览与健康检查。"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.schemas.common import HealthOut, OverviewOut
from src.services.meta_service import MetaService
from src.utils.redis_client import get_redis


def overview(db: Session) -> OverviewOut:
    return MetaService(db).overview()


def health(db: Session) -> HealthOut:
    database = "ok"
    redis_state = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        database = f"error: {exc}"
    try:
        get_redis().ping()
    except Exception as exc:  # noqa: BLE001
        redis_state = f"error: {exc}"
    status = "ok" if database == "ok" and redis_state == "ok" else "degraded"
    return HealthOut(
        status=status,
        service="abcheck-backend",
        version="1.0.0",
        database=database,
        redis=redis_state,
    )


def config_summary() -> dict:
    return {
        "brand": "abcheck",
        "alpha": settings.default_alpha,
        "power": settings.default_power,
        "srm_threshold": settings.default_srm_threshold,
        "min_sample_per_arm": settings.min_sample_per_arm,
        "runs_per_minute": settings.runs_per_minute,
    }
