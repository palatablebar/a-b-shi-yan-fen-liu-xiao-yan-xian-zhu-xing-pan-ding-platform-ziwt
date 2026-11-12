"""路由聚合：所有子路由挂到 /api 前缀（Nginx 反代时剥掉 /api）。"""
from __future__ import annotations

from fastapi import APIRouter

from src.routes import audit, auth, decision, experiment, health, meta, metric, report, run

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(meta.router)
api_router.include_router(experiment.router)
api_router.include_router(metric.router)
api_router.include_router(run.router)
api_router.include_router(decision.router)
api_router.include_router(report.router)
api_router.include_router(audit.router)
