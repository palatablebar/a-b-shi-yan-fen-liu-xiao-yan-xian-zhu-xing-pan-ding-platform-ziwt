"""概览：实验/批次计数、待裁决数、SRM 告警数与 worker 心跳。"""
from __future__ import annotations

import time

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import ExperimentStatus, RunStatus
from src.models.analysis_run import AnalysisRun
from src.models.assignment import Assignment
from src.models.decision import Decision
from src.models.experiment import Experiment
from src.models.metric import Metric
from src.schemas.common import OverviewOut
from src.utils.redis_client import get_redis


class MetaService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def overview(self) -> OverviewOut:
        experiments = self.db.query(func.count(Experiment.id)).scalar() or 0
        running = (
            self.db.query(func.count(Experiment.id))
            .filter(Experiment.status == ExperimentStatus.RUNNING.value)
            .scalar()
            or 0
        )
        analyzing = (
            self.db.query(func.count(Experiment.id))
            .filter(Experiment.status == ExperimentStatus.ANALYZING.value)
            .scalar()
            or 0
        )
        decided = (
            self.db.query(func.count(Experiment.id))
            .filter(Experiment.status == ExperimentStatus.DECIDED.value)
            .scalar()
            or 0
        )
        runs = self.db.query(func.count(AnalysisRun.id)).scalar() or 0
        assignments = self.db.query(func.count(Assignment.id)).scalar() or 0
        metrics = self.db.query(func.count(Metric.id)).scalar() or 0
        decisions = self.db.query(func.count(Decision.id)).scalar() or 0
        succeeded_runs = (
            self.db.query(AnalysisRun)
            .filter(AnalysisRun.status == RunStatus.SUCCEEDED.value)
            .all()
        )
        pending_decisions = sum(1 for run in succeeded_runs if run.verdict in ("pass", "warn")) - decisions
        srm_alerts = sum(
            1
            for run in succeeded_runs
            if (run.srm or {}).get("verdict") == "detected"
        )

        heartbeat_age = None
        try:
            raw = get_redis().get(settings.worker_heartbeat_key)
            if raw is not None:
                heartbeat_age = round(time.time() - float(raw), 1)
        except Exception:  # noqa: BLE001 - 概览不允许因 Redis 抖动失败
            heartbeat_age = None

        return OverviewOut(
            experiments=experiments,
            running=running,
            analyzing=analyzing,
            decided=decided,
            runs=runs,
            assignments=assignments,
            metrics=metrics,
            pending_decisions=max(0, pending_decisions),
            worker_heartbeat_age=heartbeat_age,
            srm_alerts=srm_alerts,
        )
