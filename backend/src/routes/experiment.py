"""实验路由：读操作全角色可用；写操作按 experiments:* 权限控制。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import experiment_controller
from src.middlewares.rbac import require_permission
from src.models.user import User
from src.schemas.assignment import AssignmentSummary
from src.schemas.experiment import (
    ExperimentCreate,
    ExperimentDetail,
    ExperimentSummary,
    ExperimentUpdate,
)

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("", response_model=list[ExperimentSummary])
def list_experiments(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("experiments:read")),
) -> list[ExperimentSummary]:
    return experiment_controller.list_experiments(db)


@router.post("", response_model=ExperimentSummary, status_code=201)
def create_experiment(
    payload: ExperimentCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("experiments:write")),
) -> ExperimentSummary:
    return experiment_controller.create_experiment(payload, request, db, user)


@router.get("/{experiment_id}", response_model=ExperimentDetail)
def get_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("experiments:read")),
) -> ExperimentDetail:
    return experiment_controller.get_experiment(experiment_id, db)


@router.patch("/{experiment_id}", response_model=ExperimentDetail)
def update_experiment(
    experiment_id: int,
    payload: ExperimentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("experiments:write")),
) -> ExperimentDetail:
    return experiment_controller.update_experiment(experiment_id, payload, request, db, user)


@router.delete("/{experiment_id}")
def delete_experiment(
    experiment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("experiments:delete")),
) -> dict:
    return experiment_controller.delete_experiment(experiment_id, request, db, user)


@router.get("/{experiment_id}/assignments", response_model=AssignmentSummary)
def assignment_summary(
    experiment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("assignments:read")),
) -> AssignmentSummary:
    return experiment_controller.assignment_summary(experiment_id, db)


@router.get("/{experiment_id}/segments")
def segments(
    experiment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("experiments:read")),
) -> dict:
    return experiment_controller.segments(experiment_id, db)
