"""端到端验证：SQLite 内存库跑 seed 生成 + AnalysisService.compute。

覆盖：
1. 三臂 exp_home_copy_1113：SRM(df=2)、逐臂配对 SRM、统一 BH、短文案 pass/ship_eligible、
   领券文案 fail/blocked（守卫回归 + 校正失真）、顶层 arms 结构完整；
2. 两臂历史实验 A/B/C：payload 结构与判定保持原口径（unreadable/warn/pass）。
"""
from __future__ import annotations

import sys

sys.path.insert(0, "/workspace/backend")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, Experiment, Metric, Variant
from scripts.seed_demo import (
    EXPERIMENT_SPECS,
    METRIC_SPECS,
    _build_assignments,
)
from src.services.analysis_service import AnalysisService

engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
SessionLocal = sessionmaker(bind=engine, future=True)
Base.metadata.create_all(engine)

db = SessionLocal()

# ---- 指标 ----
metric_objs: dict[str, Metric] = {}
for spec in METRIC_SPECS:
    metric = Metric(**{k: spec[k] for k in ("code", "name", "kind", "role", "direction", "unit", "definition")})
    db.add(metric)
    db.flush()
    metric_objs[spec["code"]] = metric

# ---- 实验 + 变体 + 分桶 ----
exp_objs: dict[str, Experiment] = {}
for spec in EXPERIMENT_SPECS:
    exp = Experiment(
        code=spec["code"],
        name=spec["name"],
        hypothesis=spec["hypothesis"],
        description=spec["description"],
        owner_name=spec["owner_name"],
        status=spec["status"],
        primary_metric_id=metric_objs[spec["primary_metric"]].id,
        guard_metric_ids=[metric_objs[c].id for c in spec["guard_metrics"]],
        secondary_metric_ids=[metric_objs[c].id for c in spec["secondary_metrics"]],
        start_date=spec["start_date"],
        end_date=spec["end_date"],
        alpha=0.05,
        srm_threshold=0.001,
        min_sample_per_arm=120,
        notes=spec["notes"],
        created_by="admin@abcheck.io",
    )
    db.add(exp)
    db.flush()
    variant_ids: dict[str, int] = {}
    for code, name, allocation, is_control, description in spec["variants"]:
        v = Variant(
            experiment_id=exp.id,
            code=code,
            name=name,
            traffic_allocation=allocation,
            is_control=is_control,
            description=description,
        )
        db.add(v)
        db.flush()
        variant_ids[code] = v.id
    db.add_all(_build_assignments(spec, exp.id, variant_ids))
    db.commit()
    exp_objs[spec["code"]] = exp

svc = AnalysisService(db)

print("================ 三臂：exp_home_copy_1113 ================")
payload = svc.compute(exp_objs["exp_home_copy_1113"])
srm = payload["srm"]
print("overall SRM:", srm["verdict"], "df=", srm["df"], "p=", round(srm["p_value"], 6), "share=", srm["observed_share"])
assert srm["verdict"] == "ok" and srm["df"] == 2
assert payload["multi_arm"] is True and payload["locked"] is False
print("full family m =", payload["full_family"]["m"], "rejected =", payload["full_family"]["rejected"])
assert payload["full_family"]["m"] == 20  # 2 处理臂 × (1 主 + 2 守卫 + 1 辅助 + 6 分层)

for arm in payload["arms"]:
    p = arm["primary"]
    print(
        f"\n[{arm['variant']['code']}] verdict={arm['verdict']} ship={arm['ship_state']}\n"
        f"  pair SRM: {arm['srm_pair']['verdict']} p={arm['srm_pair']['p_value']:.4f}\n"
        f"  primary: control={p['control_value']} treat={p['treat_value']} "
        f"lift={p['lift']:.4f} p={p['p_value']:.5f} q={p['q_value']:.5f} reject={p['bh_reject']}\n"
        f"  guard regression={arm['guard']['regression']} "
        f"checks={[(c['code'], c['state'], round(c['q_value'], 4)) for c in arm['guard']['checks']]}\n"
        f"  strata raw_sig={arm['strata']['summary']['raw_significant']} "
        f"bh_sig={arm['strata']['summary']['bh_significant']}"
    )
    for reason in arm["verdict_reasons"]:
        print("   -", reason)

short = next(a for a in payload["arms"] if a["variant"]["code"] == "short_copy")
coupon = next(a for a in payload["arms"] if a["variant"]["code"] == "coupon_copy")

assert short["verdict"] == "pass" and short["ship_state"] == "ship_eligible"
assert short["primary"]["p_value"] < 0.05 and short["primary"]["q_value"] <= 0.05
assert short["guard"]["regression"] is False
assert coupon["verdict"] == "fail" and coupon["ship_state"] == "blocked"
assert coupon["primary"]["p_value"] < 0.05 and coupon["primary"]["q_value"] > 0.05, "校正后应失真"
assert coupon["guard"]["regression"] is True
assert coupon["guard"]["checks"][0]["state"] == "regression"
# 顶层汇总
assert payload["verdict"] == "pass"
assert payload["metrics"] == [] and payload["strata"] is None and payload["guard"] is None
assert len(payload["comparisons"]) == 20
assert all({"arm_code", "arm_name", "cell_key"} <= set(row) for row in payload["comparisons"])

print("\n================ 两臂历史实验回归 ================")
expect = {
    "exp_home_feed_1101": "unreadable",
    "exp_coupon_default_1105": "warn",
    "exp_reco_rank_1022": "pass",
    "exp_onboard_modal_1108": "unreadable",
}
for code, want in expect.items():
    p2 = svc.compute(exp_objs[code])
    print(code, "->", p2["verdict"], "| srm df =", p2["srm"]["df"], "| multi =", p2["multi_arm"], "| arms =", len(p2["arms"]))
    assert p2["verdict"] == want, (code, p2["verdict"])
    assert p2["multi_arm"] is False
    assert len(p2["arms"]) == 1
    # 历史结构字段保持
    assert isinstance(p2["metrics"], list) and len(p2["metrics"]) >= 1
    assert p2["strata"] is not None and p2["guard"] is not None
    assert set(p2["variant_codes"]) == {v[0] for v in EXPERIMENT_SPECS[[s["code"] for s in EXPERIMENT_SPECS].index(code)]["variants"]}
    only = p2["arms"][0]
    assert only["verdict"] == p2["verdict"]
    assert only["ship_state"] in {"ship_eligible", "watch_only", "blocked"}

# 文档口径事实复核
pb = svc.compute(exp_objs["exp_coupon_default_1105"])
prim = next(m for m in pb["metrics"] if m["family"] == "primary")
print("\nB 实验 arpu lift =", round(prim["stat"]["lift"], 4), "p =", round(prim["stat"]["p_value"], 4))
assert abs(prim["stat"]["lift"] - 0.0419) < 0.001
assert abs(prim["stat"]["p_value"] - 0.0311) < 0.002
pa = svc.compute(exp_objs["exp_home_feed_1101"])
print("A 实验 SRM chi2 =", pa["srm"]["chi2"], "p =", round(pa["srm"]["p_value"], 7), "locked =", pa["locked"])
assert abs(pa["srm"]["chi2"] - 13.7699) < 0.01
assert pa["locked"] is True

print("\nALL_ASSERTIONS_PASSED")
