"""决策记录：结论不可读时拒绝落决策（locked 423），只有 admin 能裁决。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.enums import DecisionKind, ExperimentStatus, RunStatus, Verdict
from src.models.analysis_run import AnalysisRun
from src.models.decision import Decision
from src.models.experiment import Experiment
from src.schemas.decision import DecisionCreate, DecisionOut
from src.utils.errors import AppError


class DecisionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _latest_succeeded_run(self, experiment_id: int) -> AnalysisRun:
        run = (
            self.db.query(AnalysisRun)
            .filter(
                AnalysisRun.experiment_id == experiment_id,
                AnalysisRun.status == RunStatus.SUCCEEDED.value,
            )
            .order_by(AnalysisRun.id.desc())
            .first()
        )
        if run is None:
            raise AppError(
                codes.CONFLICT, "该实验还没有成功的分析批次，先跑分析再裁决", None, 409
            )
        return run

    def create(self, experiment_id: int, payload: DecisionCreate, reviewer: str) -> Decision:
        experiment = self.db.get(Experiment, experiment_id)
        if experiment is None:
            raise AppError(codes.NOT_FOUND, "实验不存在", f"experiment_id={experiment_id}", 404)
        run = self._latest_succeeded_run(experiment_id)
        if run.locked or run.verdict == Verdict.UNREADABLE.value:
            raise AppError(
                codes.LOCKED,
                "结论不可读（SRM/样本不足），已锁定，不能落决策记录",
                run.verdict,
                423,
            )
        if payload.decision not in {kind.value for kind in DecisionKind}:
            raise AppError(codes.VALIDATION_FAILED, "决策类型非法", payload.decision, 422)
        duplicate = (
            self.db.query(Decision)
            .filter(Decision.experiment_id == experiment_id, Decision.run_id == run.id)
            .one_or_none()
        )
        if duplicate is not None:
            raise AppError(
                codes.CONFLICT,
                "该分析批次已有决策记录，如需改判请先跑新批次",
                f"decision_id={duplicate.id}",
                409,
            )
        decision = Decision(
            experiment_id=experiment_id,
            run_id=run.id,
            decision=payload.decision,
            rationale=payload.rationale,
            reviewer=reviewer,
            guard_ack=payload.guard_ack,
            exported_formats=["md", "csv"],
        )
        self.db.add(decision)
        experiment.status = ExperimentStatus.DECIDED.value
        self.db.commit()
        self.db.refresh(decision)
        return decision

    def list_decisions(self, experiment_id: int | None = None) -> list[DecisionOut]:
        query = self.db.query(Decision)
        if experiment_id is not None:
            query = query.filter(Decision.experiment_id == experiment_id)
        rows = query.order_by(Decision.id.desc()).all()
        out: list[DecisionOut] = []
        for decision in rows:
            run = self.db.get(AnalysisRun, decision.run_id)
            out.append(
                DecisionOut(
                    id=decision.id,
                    experiment_id=decision.experiment_id,
                    experiment_code=decision.experiment.code if decision.experiment else None,
                    experiment_name=decision.experiment.name if decision.experiment else None,
                    run_id=decision.run_id,
                    run_code=run.run_code if run else None,
                    verdict=run.verdict if run else None,
                    decision=decision.decision,
                    rationale=decision.rationale,
                    reviewer=decision.reviewer,
                    guard_ack=decision.guard_ack,
                    created_at=decision.created_at,
                )
            )
        return out
