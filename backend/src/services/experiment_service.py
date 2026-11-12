"""实验服务：列表、详情、创建/编辑/删除（写操作由路由层做权限校验）。"""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.enums import ExperimentStatus, RunStatus
from src.constants.roles import ROLE_ADMIN, ROLE_ANALYST
from src.models.analysis_run import AnalysisRun
from src.models.assignment import Assignment
from src.models.decision import Decision
from src.models.experiment import Experiment
from src.models.metric import Metric
from src.models.variant import Variant
from src.schemas.assignment import AssignmentSummary
from src.schemas.experiment import (
    ExperimentCreate,
    ExperimentDetail,
    ExperimentSummary,
    ExperimentUpdate,
)
from src.schemas.metric import MetricOut
from src.schemas.variant import VariantOut
from src.services.assignment_service import AssignmentService, ordered_variants, variant_counts
from src.utils.errors import AppError

_VALID_STATUSES = {status.value for status in ExperimentStatus}


class ExperimentService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _get(self, experiment_id: int) -> Experiment:
        experiment = self.db.get(Experiment, experiment_id)
        if experiment is None:
            raise AppError(codes.NOT_FOUND, "实验不存在", f"experiment_id={experiment_id}", 404)
        return experiment

    def _counts(self) -> dict[int, int]:
        rows = (
            self.db.query(Assignment.experiment_id, func.count(Assignment.id))
            .group_by(Assignment.experiment_id)
            .all()
        )
        return {int(experiment_id): int(count) for experiment_id, count in rows}

    def _latest_runs(self) -> dict[int, AnalysisRun]:
        rows = (
            self.db.query(AnalysisRun)
            .order_by(AnalysisRun.experiment_id.asc(), AnalysisRun.id.desc())
            .all()
        )
        latest: dict[int, AnalysisRun] = {}
        for run in rows:
            latest.setdefault(run.experiment_id, run)
        return latest

    def list_experiments(self) -> list[ExperimentSummary]:
        experiments = self.db.query(Experiment).order_by(Experiment.id.asc()).all()
        counts = self._counts()
        latest = self._latest_runs()
        out: list[ExperimentSummary] = []
        for experiment in experiments:
            run = latest.get(experiment.id)
            out.append(
                ExperimentSummary(
                    id=experiment.id,
                    code=experiment.code,
                    name=experiment.name,
                    status=experiment.status,
                    owner_name=experiment.owner_name,
                    primary_metric_name=(
                        experiment.primary_metric.name if experiment.primary_metric else None
                    ),
                    start_date=experiment.start_date,
                    end_date=experiment.end_date,
                    variants=len(experiment.variants),
                    assignments=counts.get(experiment.id, 0),
                    latest_verdict=run.verdict if run else None,
                    latest_srm=(run.srm or {}).get("verdict") if run else None,
                    latest_run_at=run.created_at if run else None,
                )
            )
        return out

    def get_detail(self, experiment_id: int) -> ExperimentDetail:
        experiment = self._get(experiment_id)
        variants = ordered_variants(experiment)
        assignments = (
            self.db.query(Assignment)
            .filter(Assignment.experiment_id == experiment.id)
            .all()
        )
        counts = variant_counts(assignments)
        variant_out = [
            VariantOut.from_model(
                variant,
                users=counts[variant.id]["users"],
                exposures=counts[variant.id]["exposures"],
            )
            for variant in variants
        ]
        metrics_by_id = {m.id: m for m in self.db.query(Metric).all()}
        guard_metrics = [
            MetricOut.from_model(metrics_by_id[mid])
            for mid in (experiment.guard_metric_ids or [])
            if mid in metrics_by_id
        ]

        srm_snapshot = None
        if assignments:
            summary: AssignmentSummary = AssignmentService(self.db).summary(experiment)
            srm_snapshot = summary.srm
            srm_snapshot["variants"] = [bucket.model_dump() for bucket in summary.variants]

        latest_run = (
            self.db.query(AnalysisRun)
            .filter(AnalysisRun.experiment_id == experiment.id)
            .order_by(AnalysisRun.id.desc())
            .first()
        )
        latest_payload = None
        if latest_run is not None:
            primary_lift = None
            primary_p = None
            for entry in latest_run.metrics or []:
                if entry.get("family") == "primary":
                    primary_lift = entry["stat"]["lift"]
                    primary_p = entry["stat"]["p_value"]
            latest_payload = {
                "id": latest_run.id,
                "run_code": latest_run.run_code,
                "status": latest_run.status,
                "verdict": latest_run.verdict,
                "locked": latest_run.locked,
                "srm": latest_run.srm,
                "primary_lift": primary_lift,
                "primary_p_value": primary_p,
                "verdict_reasons": latest_run.verdict_reasons,
                "created_at": latest_run.created_at.isoformat() if latest_run.created_at else None,
                "finished_at": latest_run.finished_at.isoformat() if latest_run.finished_at else None,
            }

        decision = (
            self.db.query(Decision)
            .filter(Decision.experiment_id == experiment.id)
            .order_by(Decision.id.desc())
            .first()
        )
        return ExperimentDetail(
            id=experiment.id,
            code=experiment.code,
            name=experiment.name,
            hypothesis=experiment.hypothesis or "",
            description=experiment.description or "",
            owner_name=experiment.owner_name,
            status=experiment.status,
            alpha=experiment.alpha,
            srm_threshold=experiment.srm_threshold,
            min_sample_per_arm=experiment.min_sample_per_arm,
            start_date=experiment.start_date,
            end_date=experiment.end_date,
            notes=experiment.notes or "",
            created_by=experiment.created_by,
            updated_at=experiment.updated_at,
            primary_metric=(
                MetricOut.from_model(experiment.primary_metric)
                if experiment.primary_metric
                else None
            ),
            guard_metrics=guard_metrics,
            variants=variant_out,
            assignment_total=len(assignments),
            srm_snapshot=srm_snapshot,
            latest_run=latest_payload,
            decision=(
                {
                    "id": decision.id,
                    "decision": decision.decision,
                    "rationale": decision.rationale,
                    "reviewer": decision.reviewer,
                    "guard_ack": decision.guard_ack,
                    "created_at": decision.created_at.isoformat(),
                }
                if decision
                else None
            ),
        )

    # ------------------------------------------------------------------ 写 ----
    def create(self, payload: ExperimentCreate, actor_email: str, actor_role: str) -> Experiment:
        if actor_role not in (ROLE_ADMIN, ROLE_ANALYST):
            raise AppError(codes.FORBIDDEN, "当前角色无权创建实验", f"role={actor_role}", 403)
        existing = self.db.query(Experiment).filter(Experiment.code == payload.code).one_or_none()
        if existing is not None:
            raise AppError(codes.CONFLICT, "实验编号已存在", f"code={payload.code}", 409)
        metric = self.db.get(Metric, payload.primary_metric_id)
        if metric is None:
            raise AppError(codes.VALIDATION_FAILED, "主指标不存在", f"metric_id={payload.primary_metric_id}", 422)
        if len(payload.variants) < 2:
            raise AppError(codes.VALIDATION_FAILED, "至少需要对照组与实验组两个变体", None, 422)

        experiment = Experiment(
            code=payload.code,
            name=payload.name,
            hypothesis=payload.hypothesis,
            description=payload.description,
            owner_name=payload.owner_name,
            status=ExperimentStatus.DRAFT.value,
            primary_metric_id=payload.primary_metric_id,
            guard_metric_ids=payload.guard_metric_ids or [],
            secondary_metric_ids=payload.secondary_metric_ids or [],
            start_date=payload.start_date,
            end_date=payload.end_date,
            alpha=payload.alpha,
            srm_threshold=payload.srm_threshold,
            min_sample_per_arm=payload.min_sample_per_arm if hasattr(payload, "min_sample_per_arm") else 120,
            notes=payload.notes,
            created_by=actor_email,
        )
        self.db.add(experiment)
        self.db.flush()
        for index, variant in enumerate(payload.variants):
            self.db.add(
                Variant(
                    experiment_id=experiment.id,
                    code=variant.code,
                    name=variant.name,
                    traffic_allocation=variant.traffic_allocation,
                    is_control=variant.is_control or index == 0,
                    description=variant.description,
                )
            )
        self.db.commit()
        self.db.refresh(experiment)
        return experiment

    def update(self, experiment_id: int, payload: ExperimentUpdate) -> Experiment:
        experiment = self._get(experiment_id)
        data = payload.model_dump(exclude_unset=True)
        if "status" in data and data["status"] is not None:
            if data["status"] not in _VALID_STATUSES:
                raise AppError(codes.VALIDATION_FAILED, "实验状态非法", f"status={data['status']}", 422)
            experiment.status = data["status"]
        for field in ("name", "hypothesis", "description", "owner_name", "notes"):
            if data.get(field) is not None:
                setattr(experiment, field, data[field])
        if data.get("primary_metric_id") is not None:
            if self.db.get(Metric, data["primary_metric_id"]) is None:
                raise AppError(codes.VALIDATION_FAILED, "主指标不存在", None, 422)
            experiment.primary_metric_id = data["primary_metric_id"]
        if data.get("guard_metric_ids") is not None:
            experiment.guard_metric_ids = data["guard_metric_ids"]
        if data.get("secondary_metric_ids") is not None:
            experiment.secondary_metric_ids = data["secondary_metric_ids"]
        if data.get("alpha") is not None:
            experiment.alpha = data["alpha"]
        if data.get("srm_threshold") is not None:
            experiment.srm_threshold = data["srm_threshold"]
        self.db.commit()
        self.db.refresh(experiment)
        return experiment

    def delete(self, experiment_id: int) -> None:
        experiment = self._get(experiment_id)
        self.db.delete(experiment)
        self.db.commit()
