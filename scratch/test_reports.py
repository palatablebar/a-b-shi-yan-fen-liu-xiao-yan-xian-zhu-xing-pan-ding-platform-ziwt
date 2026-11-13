"""验证报告服务：两臂走历史模板，三臂走多臂模板（MD + CSV 都可渲染）。"""
from __future__ import annotations

import sys

sys.path.insert(0, "/workspace/backend")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, AnalysisRun, Experiment, Metric, Variant
from scripts.seed_demo import EXPERIMENT_SPECS, METRIC_SPECS, _build_assignments
from src.services.analysis_service import AnalysisService
from src.services.report_service import ReportService
from src.constants.enums import RunStatus
from src.models.base import utcnow

engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
SessionLocal = sessionmaker(bind=engine, future=True)
Base.metadata.create_all(engine)
db = SessionLocal()

metric_objs: dict[str, Metric] = {}
for spec in METRIC_SPECS:
    m = Metric(**{k: spec[k] for k in ("code", "name", "kind", "role", "direction", "unit", "definition")})
    db.add(m)
    db.flush()
    metric_objs[spec["code"]] = m

exp_objs: dict[str, Experiment] = {}
for spec in EXPERIMENT_SPECS:
    exp = Experiment(
        code=spec["code"], name=spec["name"], hypothesis=spec["hypothesis"],
        description=spec["description"], owner_name=spec["owner_name"], status=spec["status"],
        primary_metric_id=metric_objs[spec["primary_metric"]].id,
        guard_metric_ids=[metric_objs[c].id for c in spec["guard_metrics"]],
        secondary_metric_ids=[metric_objs[c].id for c in spec["secondary_metrics"]],
        start_date=spec["start_date"], end_date=spec["end_date"],
        alpha=0.05, srm_threshold=0.001, min_sample_per_arm=120, notes=spec["notes"],
        created_by="admin@abcheck.io",
    )
    db.add(exp)
    db.flush()
    variant_ids: dict[str, int] = {}
    for code, name, allocation, is_control, description in spec["variants"]:
        v = Variant(experiment_id=exp.id, code=code, name=name,
                    traffic_allocation=allocation, is_control=is_control, description=description)
        db.add(v)
        db.flush()
        variant_ids[code] = v.id
    db.add_all(_build_assignments(spec, exp.id, variant_ids))
    db.commit()
    exp_objs[spec["code"]] = exp

svc = AnalysisService(db)
report_svc = ReportService(db)

for code in ("exp_home_copy_1113", "exp_coupon_default_1105", "exp_home_feed_1101"):
    exp = exp_objs[code]
    payload = svc.compute(exp)
    run = AnalysisRun(
        experiment_id=exp.id, run_code=f"RUN-{code.upper()}-T", status=RunStatus.SUCCEEDED.value,
        triggered_by="seed", params={"multi_arm": payload["multi_arm"]},
        srm=payload["srm"], metrics=payload["metrics"], strata=payload.get("strata"),
        comparisons=payload["comparisons"], guard=payload.get("guard"), arms=payload.get("arms"),
        verdict=payload["verdict"], verdict_reasons=payload["verdict_reasons"],
        locked=payload["locked"], started_at=utcnow(), finished_at=utcnow(),
    )
    db.add(run)
    db.commit()
    md = report_svc.build_markdown(exp.id, run.id)
    csv_text = report_svc.build_csv(exp.id, run.id)
    print(f"\n########## {code} ({'multi' if payload['multi_arm'] else 'two'}-arm) ##########")
    print("MD bytes:", len(md), "| CSV rows:", csv_text.count("\n"))
    assert "## 一、实验信息" in md
    if payload["multi_arm"]:
        assert "共同对照" in md and "全方案统一 BH" in md and "可上线状态" in md
        assert "ship_eligible" not in md  # 面向人的中文标签，不泄内部枚举
        assert "可上线（唯一赢家）" in md and "禁止上线（blocked）" in md
        # CSV 表头含多臂字段
        assert "full_bh_q_value" in csv_text and "ship_state" in csv_text and "arm_code" in csv_text
        print(md[:2600])
    else:
        assert "全方案统一误报控制" not in md
        assert "srm_verdict" in csv_text
print("\nREPORT_ASSERTIONS_PASSED")
