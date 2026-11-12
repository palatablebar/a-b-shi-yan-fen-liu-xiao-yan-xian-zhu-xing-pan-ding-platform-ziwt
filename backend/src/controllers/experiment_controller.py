"""实验控制器：列表 / 详情 / 增改删 / 分桶摘要。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.models.experiment import Experiment
from src.models.user import User
from src.schemas.assignment import AssignmentSummary
from src.schemas.experiment import (
    ExperimentCreate,
    ExperimentDetail,
    ExperimentSummary,
    ExperimentUpdate,
)
from src.services.assignment_service import AssignmentService
from src.services.audit_service import AuditService
from src.services.experiment_service import ExperimentService


def list_experiments(db: Session) -> list[ExperimentSummary]:
    return ExperimentService(db).list_experiments()


def get_experiment(experiment_id: int, db: Session) -> ExperimentDetail:
    return ExperimentService(db).get_detail(experiment_id)


def create_experiment(
    payload: ExperimentCreate, request: Request, db: Session, user: User
) -> ExperimentSummary:
    service = ExperimentService(db)
    experiment: Experiment = service.create(payload, user.email, user.role)
    AuditService(db).record(
        actor_email=user.email,
        actor_role=user.role,
        action="experiment.create",
        method="POST",
        path=request.url.path,
        status_code=201,
        detail={"code": experiment.code},
        ip=request.client.host if request.client else "",
    )
    return next(
        summary for summary in service.list_experiments() if summary.id == experiment.id
    )


def update_experiment(
    experiment_id: int, payload: ExperimentUpdate, request: Request, db: Session, user: User
) -> ExperimentDetail:
    service = ExperimentService(db)
    service.update(experiment_id, payload)
    AuditService(db).record(
        actor_email=user.email,
        actor_role=user.role,
        action="experiment.update",
        method="PATCH",
        path=request.url.path,
        status_code=200,
        detail={"experiment_id": experiment_id},
        ip=request.client.host if request.client else "",
    )
    return service.get_detail(experiment_id)


def delete_experiment(experiment_id: int, request: Request, db: Session, user: User) -> dict:
    ExperimentService(db).delete(experiment_id)
    AuditService(db).record(
        actor_email=user.email,
        actor_role=user.role,
        action="experiment.delete",
        method="DELETE",
        path=request.url.path,
        status_code=200,
        detail={"experiment_id": experiment_id},
        ip=request.client.host if request.client else "",
    )
    return {"deleted": True, "experiment_id": experiment_id}


def assignment_summary(experiment_id: int, db: Session) -> AssignmentSummary:
    service = ExperimentService(db)
    detail = service.get_detail(experiment_id)
    experiment = service._get(experiment_id)  # noqa: SLF001 - 同层服务复用
    summary = AssignmentService(db).summary(experiment)
    summary.total_users = detail.assignment_total
    return summary


def segments(experiment_id: int, db: Session) -> dict:
    """分层分析视图：读取最近一次成功批次的分层结果（无批次时给出 409 提示）。"""
    from src.constants import error_codes as codes
    from src.constants.enums import RunStatus
    from src.models.analysis_run import AnalysisRun
    from src.utils.errors import AppError

    service = ExperimentService(db)
    experiment = service._get(experiment_id)  # noqa: SLF001 - 同层服务复用
    run = (
        db.query(AnalysisRun)
        .filter(
            AnalysisRun.experiment_id == experiment_id,
            AnalysisRun.status == RunStatus.SUCCEEDED.value,
        )
        .order_by(AnalysisRun.id.desc())
        .first()
    )
    if run is None:
        raise AppError(codes.CONFLICT, "该实验还没有成功的分析批次，先跑分析", None, 409)
    primary = None
    for entry in run.metrics or []:
        if entry.get("family") == "primary":
            primary = entry
            break
    return {
        "experiment": {
            "id": experiment.id,
            "code": experiment.code,
            "name": experiment.name,
            "status": experiment.status,
            "primary_metric": primary["metric"] if primary else None,
        },
        "run": {
            "id": run.id,
            "run_code": run.run_code,
            "verdict": run.verdict,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "srm": run.srm,
        },
        "strata": run.strata or {},
        "primary": primary,
    }
