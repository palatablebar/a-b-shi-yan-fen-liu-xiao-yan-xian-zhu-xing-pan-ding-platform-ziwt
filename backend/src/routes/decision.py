"""决策路由：写仅 admin。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import decision_controller
from src.middlewares.rbac import require_permission
from src.models.user import User
from src.schemas.decision import DecisionCreate, DecisionOut

router = APIRouter(tags=["decisions"])


@router.post("/experiments/{experiment_id}/decisions", response_model=DecisionOut, status_code=201)
def create_decision(
    experiment_id: int,
    payload: DecisionCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("decisions:write")),
) -> DecisionOut:
    return decision_controller.create_decision(experiment_id, payload, request, db, user)


@router.get("/decisions", response_model=list[DecisionOut])
def list_decisions(
    experiment_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("decisions:read")),
) -> list[DecisionOut]:
    return decision_controller.list_decisions(db, experiment_id)
