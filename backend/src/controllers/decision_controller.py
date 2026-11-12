"""决策控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.models.user import User
from src.schemas.decision import DecisionCreate, DecisionOut
from src.services.audit_service import AuditService
from src.services.decision_service import DecisionService


def create_decision(
    experiment_id: int, payload: DecisionCreate, request: Request, db: Session, user: User
) -> DecisionOut:
    decision = DecisionService(db).create(experiment_id, payload, user.email)
    AuditService(db).record(
        actor_email=user.email,
        actor_role=user.role,
        action="decision.create",
        method="POST",
        path=request.url.path,
        status_code=201,
        detail={"experiment_id": experiment_id, "decision": decision.decision},
        ip=request.client.host if request.client else "",
    )
    items = DecisionService(db).list_decisions(experiment_id)
    return next(item for item in items if item.id == decision.id)


def list_decisions(db: Session, experiment_id: int | None = None) -> list[DecisionOut]:
    return DecisionService(db).list_decisions(experiment_id)
