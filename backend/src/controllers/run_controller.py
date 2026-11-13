"""分析批次控制器：触发、列表、详情（结果回读）。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.models.experiment import Experiment
from src.models.user import User
from src.schemas.run import RunDetail, RunSummary
from src.services.analysis_service import AnalysisService
from src.services.audit_service import AuditService
from src.utils.errors import AppError


def _summary(db: Session, run) -> RunSummary:
    primary_lift = None
    primary_p = None
    for entry in run.metrics or []:
        if entry.get("family") == "primary":
            primary_lift = entry["stat"].get("lift")
            primary_p = entry["stat"].get("p_value")
    # 多臂批次：取可上线方案（否则第一个方案）的主指标作为列表摘要
    if primary_lift is None and run.arms:
        winner = next(
            (arm for arm in run.arms if arm.get("ship_state") == "ship_eligible"),
            run.arms[0],
        )
        primary_summary = winner.get("primary") or {}
        primary_lift = primary_summary.get("lift")
        primary_p = primary_summary.get("p_value")
    experiment = db.get(Experiment, run.experiment_id)
    return RunSummary(
        id=run.id,
        experiment_id=run.experiment_id,
        experiment_code=experiment.code if experiment else None,
        experiment_name=experiment.name if experiment else None,
        run_code=run.run_code,
        status=run.status,
        verdict=run.verdict,
        locked=run.locked,
        triggered_by=run.triggered_by,
        srm_verdict=(run.srm or {}).get("verdict"),
        srm_p_value=(run.srm or {}).get("p_value"),
        primary_lift=primary_lift,
        primary_p_value=primary_p,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        error=run.error,
    )


def trigger_run(experiment_id: int, request: Request, db: Session, user: User) -> RunSummary:
    experiment = db.get(Experiment, experiment_id)
    if experiment is None:
        raise AppError(codes.NOT_FOUND, "实验不存在", f"experiment_id={experiment_id}", 404)
    run = AnalysisService(db).create_run(experiment, user.email)
    AuditService(db).record(
        actor_email=user.email,
        actor_role=user.role,
        action="run.create",
        method="POST",
        path=request.url.path,
        status_code=202,
        detail={"run_code": run.run_code, "experiment": experiment.code},
        ip=request.client.host if request.client else "",
    )
    return _summary(db, run)


def list_runs(db: Session, experiment_id: int | None = None, limit: int = 50) -> list[RunSummary]:
    from src.models.analysis_run import AnalysisRun

    query = db.query(AnalysisRun)
    if experiment_id is not None:
        query = query.filter(AnalysisRun.experiment_id == experiment_id)
    rows = query.order_by(AnalysisRun.id.desc()).limit(limit).all()
    return [_summary(db, run) for run in rows]


def get_run(run_id: int, db: Session) -> RunDetail:
    from src.models.analysis_run import AnalysisRun

    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise AppError(codes.NOT_FOUND, "分析批次不存在", f"run_id={run_id}", 404)
    experiment = db.get(Experiment, run.experiment_id)
    return RunDetail(
        id=run.id,
        experiment_id=run.experiment_id,
        run_code=run.run_code,
        status=run.status,
        verdict=run.verdict,
        locked=run.locked,
        triggered_by=run.triggered_by,
        params=run.params,
        srm=run.srm,
        metrics=run.metrics,
        strata=run.strata,
        comparisons=run.comparisons,
        guard=run.guard,
        arms=run.arms,
        verdict_reasons=run.verdict_reasons,
        error=run.error,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        experiment=(
            {
                "id": experiment.id,
                "code": experiment.code,
                "name": experiment.name,
                "status": experiment.status,
                "primary_metric": (
                    {
                        "id": experiment.primary_metric.id,
                        "code": experiment.primary_metric.code,
                        "name": experiment.primary_metric.name,
                        "kind": experiment.primary_metric.kind,
                        "unit": experiment.primary_metric.unit,
                    }
                    if experiment.primary_metric
                    else None
                ),
            }
            if experiment
            else None
        ),
    )
