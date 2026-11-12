"""分析批次路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import run_controller
from src.middlewares.rbac import require_permission
from src.models.user import User
from src.schemas.run import RunDetail, RunSummary

router = APIRouter(tags=["runs"])


@router.post("/experiments/{experiment_id}/runs", response_model=RunSummary, status_code=202)
def trigger_run(
    experiment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("runs:trigger")),
) -> RunSummary:
    return run_controller.trigger_run(experiment_id, request, db, user)


@router.get("/runs", response_model=list[RunSummary])
def list_runs(
    experiment_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("runs:read")),
) -> list[RunSummary]:
    return run_controller.list_runs(db, experiment_id, limit)


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("runs:read")),
) -> RunDetail:
    return run_controller.get_run(run_id, db)
