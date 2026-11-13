"""完整 seed 流程验证：seed_all() 连跑两遍（幂等），核对汇总行与三臂批次落库。"""
from __future__ import annotations

import sys

sys.path.insert(0, "/workspace/backend")

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.config import database as dbmod
from src.models import AnalysisRun, Assignment, Decision, Experiment, Variant, Base
from scripts import seed_demo

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    future=True,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=engine, future=True)
Base.metadata.create_all(engine)
# seed_demo 通过 `from src.config.database import session_scope` 引用模块级工厂，
# 必须替换函数本身（闭包内的 SessionLocal 符号才会切到测试库）
@contextmanager
def _test_session_scope():
    db = TestSession()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

dbmod.session_scope = _test_session_scope
dbmod.engine = engine
dbmod.SessionLocal = TestSession
# seed_demo 在 import 时 `from src.config.database import session_scope`，需替换它自己模块里的名字
seed_demo.session_scope = _test_session_scope

first = seed_demo.seed_all()
created_after_first = seed_demo.CREATED
summary_1 = first["summary"]
print("\nFIRST  ->", summary_1)

second = seed_demo.seed_all()
print("SECOND ->", second["summary"])
assert seed_demo.CREATED == created_after_first, "第二遍必须全部幂等跳过（created 计数不得增长）"

db = TestSession()
try:
    n_exp = db.query(Experiment).count()
    n_var = db.query(Variant).count()
    n_assign = db.query(Assignment).count()
    n_runs = db.query(AnalysisRun).count()
    n_decisions = db.query(Decision).count()
    print(f"rows: experiments={n_exp} variants={n_var} assignments={n_assign} runs={n_runs} decisions={n_decisions}")
    assert (n_exp, n_var, n_assign, n_runs, n_decisions) == (5, 11, 7400, 4, 1)

    exp3 = db.query(Experiment).filter(Experiment.code == "exp_home_copy_1113").one()
    assert len(exp3.variants) == 3
    run3 = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.experiment_id == exp3.id)
        .order_by(AnalysisRun.id.desc())
        .first()
    )
    assert run3 is not None and len(run3.arms) == 2 and run3.verdict == "pass"
    codes = [a["variant"]["code"] for a in run3.arms]
    assert codes == ["short_copy", "coupon_copy"]
    states = {a["variant"]["code"]: (a["verdict"], a["ship_state"]) for a in run3.arms}
    print("arm states:", states)
    assert states["short_copy"] == ("pass", "ship_eligible")
    assert states["coupon_copy"] == ("fail", "blocked")
    # 全量 BH 行数：2 处理臂 ×（1 主 + 2 守卫 + 1 辅助 + 6 分层）= 20
    assert len(run3.comparisons) == 20
    assert run3.params["multi_arm"] is True
    # 两臂历史批次 arms 也有 1 条，且顶层结构照旧
    exp_b = db.query(Experiment).filter(Experiment.code == "exp_coupon_default_1105").one()
    run_b = db.query(AnalysisRun).filter(AnalysisRun.experiment_id == exp_b.id).one()
    assert len(run_b.arms) == 1 and run_b.arms[0]["verdict"] == run_b.verdict == "warn"
    assert run_b.params["multi_arm"] is False
    assert run_b.metrics and run_b.strata and run_b.guard
    print("\nSEED_E2E_ASSERTIONS_PASSED")
finally:
    db.close()
