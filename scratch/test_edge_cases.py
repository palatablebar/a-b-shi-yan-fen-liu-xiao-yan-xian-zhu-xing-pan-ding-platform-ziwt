"""边界场景：
1. 4 变体（1 对照 + 3 处理）：m=30，逐方案判定互不干扰，BH 跨三臂统一校正；
2. 全实验 SRM 失衡 → 全部方案 locked unreadable；
3. 配对曝光不足（insufficient）与全实验可读并存 → 仅该臂 unreadable/blocked；
4. 小样本两臂 → unreadable。
"""
from __future__ import annotations

import sys
from datetime import date, datetime

sys.path.insert(0, "/workspace/backend")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.models import Base, Assignment, Experiment, Metric, Variant
from src.services.analysis_service import AnalysisService

engine = create_engine(
    "sqlite+pysqlite:///:memory:", future=True,
    connect_args={"check_same_thread": False}, poolclass=StaticPool,
)
SessionLocal = sessionmaker(bind=engine, future=True)
Base.metadata.create_all(engine)
db = SessionLocal()

metric = Metric(code="conv", name="转化", kind="ratio", role="primary",
                direction="increase_good", unit="%", definition="t")
guard = Metric(code="comp", name="客诉", kind="ratio", role="guard",
               direction="decrease_good", unit="%", definition="g")
db.add_all([metric, guard])
db.flush()


def build_experiment(code: str, arms: list[dict]) -> Experiment:
    exp = Experiment(
        code=code, name=code, hypothesis="h", description="d", owner_name="o",
        status="running", primary_metric_id=metric.id, guard_metric_ids=[guard.id],
        secondary_metric_ids=[], start_date=date(2026, 11, 1), end_date=date(2026, 11, 13),
        alpha=0.05, srm_threshold=0.001, min_sample_per_arm=120, notes="", created_by="a",
    )
    db.add(exp)
    db.flush()
    variant_ids: dict[str, int] = {}
    for arm in arms:
        v = Variant(experiment_id=exp.id, code=arm["code"], name=arm["name"],
                    traffic_allocation=arm["alloc"], is_control=arm.get("control", False), description="")
        db.add(v)
        db.flush()
        variant_ids[arm["code"]] = v.id
    rows = []
    start = datetime(2026, 11, 1)
    for arm in arms:
        vid = variant_ids[arm["code"]]
        for i in range(arm["users"]):
            rows.append(Assignment(
                experiment_id=exp.id, variant_id=vid, user_key=f"{code}-{arm['code']}-{i:04d}",
                bucket=i,
                exposure_count=arm["exposures"] // arm["users"] + (1 if i < arm["exposures"] % arm["users"] else 0),
                segment_city=("一线", "新一线", "二线")[i % 3], segment_tenure=("新客", "老客")[i % 2],
                flags={"conv": i < arm["conv"], "comp": i < arm["comp"]},
                metric_value=1.0, exposed_at=start,
            ))
    db.add_all(rows)
    db.commit()
    return exp


# ---- 1) 4 变体正常数据：3 个处理臂统一 BH ----
arms4 = [
    {"code": "control", "name": "对照", "alloc": 0.25, "control": True, "users": 600, "exposures": 1200, "conv": 132, "comp": 18},
    {"code": "t1", "name": "方案一", "alloc": 0.25, "users": 600, "exposures": 1206, "conv": 168, "comp": 18},
    {"code": "t2", "name": "方案二", "alloc": 0.25, "users": 600, "exposures": 1194, "conv": 140, "comp": 19},
    {"code": "t3", "name": "方案三", "alloc": 0.25, "users": 600, "exposures": 1200, "conv": 145, "comp": 20},
]
exp4 = build_experiment("exp_four_arm", arms4)
payload = AnalysisService(db).compute(exp4)
print("4-arm overall SRM:", payload["srm"]["verdict"], "df =", payload["srm"]["df"])
assert payload["srm"]["df"] == 3 and payload["srm"]["verdict"] == "ok"
assert payload["full_family"]["m"] == 24  # 3 处理臂 × (1 主 + 1 守卫 + 0 辅助 + 6 分层)
for arm in payload["arms"]:
    print(" ", arm["variant"]["code"], "->", arm["verdict"], arm["ship_state"],
          "pair:", arm["srm_pair"]["verdict"], "p =", arm["primary"]["p_value"], "q =", arm["primary"]["q_value"])
    assert arm["srm_pair"]["verdict"] == "ok"
    assert arm["ship_state"] in {"ship_eligible", "watch_only", "blocked"}
assert {a["variant"]["code"] for a in payload["arms"]} == {"t1", "t2", "t3"}
# t1 原始 p<0.05 但跨三臂统一 BH 后 q>0.05：校正失真 → blocked，不能当赢家
t1 = next(a for a in payload["arms"] if a["variant"]["code"] == "t1")
assert t1["primary"]["p_value"] < 0.05 and t1["primary"]["q_value"] > 0.05
assert t1["bh_distorted"] is True and t1["ship_state"] == "blocked"
print("  t1 校正失真机制验证：raw p=%.4f -> joint BH q=%.4f" % (t1["primary"]["p_value"], t1["primary"]["q_value"]))

# ---- 2) 全实验 SRM 失衡：对照臂曝光异常 → 全部 unreadable ----
arms_bad = [
    {"code": "control", "name": "对照", "alloc": 0.34, "control": True, "users": 600, "exposures": 2600, "conv": 132, "comp": 18},
    {"code": "t1", "name": "方案一", "alloc": 0.33, "users": 600, "exposures": 1180, "conv": 168, "comp": 18},
    {"code": "t2", "name": "方案二", "alloc": 0.33, "users": 600, "exposures": 1220, "conv": 140, "comp": 19},
]
exp_bad = build_experiment("exp_global_srm", arms_bad)
p2 = AnalysisService(db).compute(exp_bad)
print("\nglobal SRM:", p2["srm"]["verdict"], "p =", p2["srm"]["p_value"], "locked =", p2["locked"])
assert p2["srm"]["verdict"] == "detected"
assert p2["locked"] is True and p2["verdict"] == "unreadable"
assert all(a["verdict"] == "unreadable" and a["ship_state"] == "blocked" for a in p2["arms"])

# ---- 3) 配对曝光不足：全实验总量够（三臂均 ≥240 曝光、配比与 0.05/0.05/0.90 一致），
#       control+t1 配对合计 470 < min_exposures(500) → t1 单独不可读，t2 正常 ----
arms_ins = [
    {"code": "control", "name": "对照", "alloc": 0.05, "control": True, "users": 600, "exposures": 240, "conv": 132, "comp": 18},
    {"code": "t1", "name": "方案一·小流量", "alloc": 0.05, "users": 600, "exposures": 235, "conv": 168, "comp": 18},
    {"code": "t2", "name": "方案二", "alloc": 0.90, "users": 600, "exposures": 4275, "conv": 140, "comp": 19},
]
exp_ins = build_experiment("exp_pair_insufficient", arms_ins)
p3 = AnalysisService(db).compute(exp_ins)
print("\npair-insufficient global:", p3["srm"]["verdict"], "total =", p3["srm"]["total"])
assert p3["srm"]["verdict"] == "ok" and p3["locked"] is False
by_code = {a["variant"]["code"]: a for a in p3["arms"]}
print("  t1 pair SRM:", by_code["t1"]["srm_pair"]["verdict"], "-> arm verdict:", by_code["t1"]["verdict"])
print("  t2 pair SRM:", by_code["t2"]["srm_pair"]["verdict"], "-> arm verdict:", by_code["t2"]["verdict"])
assert by_code["t1"]["srm_pair"]["verdict"] == "insufficient"
assert by_code["t1"]["verdict"] == "unreadable" and by_code["t1"]["ship_state"] == "blocked"
assert by_code["t2"]["srm_pair"]["verdict"] == "ok"
assert by_code["t2"]["verdict"] != "unreadable"
# 总判定：存在不可读臂但也有可读臂 → 不锁定，按可读臂的最优档
assert p3["verdict"] != "unreadable"

# ---- 4) 小样本两臂 ----
arms_small = [
    {"code": "control", "name": "对照", "alloc": 0.5, "control": True, "users": 50, "exposures": 50, "conv": 11, "comp": 2},
    {"code": "t1", "name": "方案一", "alloc": 0.5, "users": 50, "exposures": 50, "conv": 14, "comp": 2},
]
exp_small = build_experiment("exp_small", arms_small)
p4 = AnalysisService(db).compute(exp_small)
assert p4["multi_arm"] is False and p4["arms"][0]["verdict"] == "unreadable"
assert p4["verdict"] == "unreadable"
print("\nsmall-sample:", p4["arms"][0]["verdict_reasons"][0])

print("\nEDGE_CASE_ASSERTIONS_PASSED")
