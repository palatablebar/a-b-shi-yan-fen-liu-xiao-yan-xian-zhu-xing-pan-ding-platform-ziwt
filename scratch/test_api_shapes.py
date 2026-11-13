"""验证 API 序列化：RunDetail/RunSummary/ExperimentDetail/SegmentView 全部能过 Pydantic。

模拟 controller 层产出的 dict 直接喂给 response_model，确保前端拿到的字段类型与新增 arms 兼容。
"""
from __future__ import annotations

import sys
from contextlib import contextmanager

sys.path.insert(0, "/workspace/backend")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.config import database as dbmod
from src.models import Base, AnalysisRun
from src.constants.enums import RunStatus
from src.models.base import utcnow
from scripts import seed_demo
from src.services.analysis_service import AnalysisService
from src.schemas.run import RunDetail as RunDetailSchema, RunSummary as RunSummarySchema
from src.schemas.experiment import ExperimentDetail as ExperimentDetailSchema
from src.services.experiment_service import ExperimentService
from src.controllers import experiment_controller

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    future=True,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=engine, future=True)
Base.metadata.create_all(engine)


@contextmanager
def _scope():
    db = TestSession()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


dbmod.session_scope = _scope
seed_demo.session_scope = _scope
seed_demo.seed_all()

db = TestSession()
svc = AnalysisService(db)
exp_svc = ExperimentService(db)

exp = next(e for e in db.query(seed_demo.Experiment).all() if e.code == "exp_home_copy_1113")

# 直接把 compute 结果落成一条批次，再走 controller 的 RunDetail 序列化
payload = svc.compute(exp)
run = AnalysisRun(
    experiment_id=exp.id, run_code="RUN-API-001", status=RunStatus.SUCCEEDED.value,
    triggered_by="analyst@abcheck.io", params={"multi_arm": True, "alpha": 0.05},
    srm=payload["srm"], metrics=payload["metrics"], strata=payload.get("strata"),
    comparisons=payload["comparisons"], guard=payload.get("guard"), arms=payload["arms"],
    verdict=payload["verdict"], verdict_reasons=payload["verdict_reasons"],
    locked=payload["locked"], started_at=utcnow(), finished_at=utcnow(),
)
db.add(run)
db.commit()
db.refresh(run)

from src.controllers.run_controller import _summary, get_run

summary = _summary(db, run)
summary_json = RunSummarySchema.model_validate(summary, from_attributes=True) if hasattr(RunSummarySchema, "model_validate") else summary
print("RunSummary ok:", summary.run_code, summary.verdict, "lift=", summary.primary_lift, "p=", summary.primary_p_value)
assert summary.primary_lift is not None and summary.primary_p_value is not None

detail = get_run(run.id, db)
assert detail.arms is not None and len(detail.arms) == 2
arm0 = detail.arms[0]
assert {"variant", "control_variant", "srm_pair", "sample", "metrics", "guard", "strata",
        "primary", "verdict", "verdict_reasons", "ship_state", "guard_regression", "bh_distorted"} <= set(arm0)
print("RunDetail ok: multi arms =", [a["ship_state"] for a in detail.arms])

# 实验详情 schema
exp_detail = exp_svc.get_detail(exp.id)
assert exp_detail.latest_run is not None
print("ExperimentDetail ok: latest verdict =", exp_detail.latest_run["verdict"],
      "lift =", exp_detail.latest_run["primary_lift"])
assert abs(exp_detail.latest_run["primary_lift"] - arm0["primary"]["lift"]) < 1e-12

# 分层视图（多臂返回 arms）
seg = experiment_controller.segments(exp.id, db)
assert seg["multi_arm"] is True and seg["arms"] is not None and len(seg["arms"]) == 2
assert seg["strata"] == {}  # 多臂顶层无单分层
print("SegmentView ok: arms =", [a["variant"]["code"] for a in seg["arms"]])

# 两臂实验的序列化回归
exp2 = next(e for e in db.query(seed_demo.Experiment).all() if e.code == "exp_coupon_default_1105")
d2 = exp_svc.get_detail(exp2.id)
assert d2.latest_run and d2.latest_run["verdict"] == "warn"
seg2 = experiment_controller.segments(exp2.id, db)
assert seg2["multi_arm"] is False and seg2["arms"] is None and seg2["strata"]["cells"]
run2 = db.query(AnalysisRun).filter(AnalysisRun.experiment_id == exp2.id).first()
detail2 = get_run(run2.id, db)
assert detail2.arms is not None and len(detail2.arms) == 1 and detail2.metrics
print("two-arm RunDetail ok: metrics =", len(detail2.metrics), "arms =", len(detail2.arms))

print("\nAPI_SERIALIZATION_PASSED")
