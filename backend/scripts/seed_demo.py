"""青柚出行 · abcheck 演示数据（幂等）。

自然键：
  User.email / Metric.code / Experiment.code / Variant(experiment_id, code) /
  Assignment(experiment_id, user_key) / AnalysisRun.run_code / Decision(experiment_id, run_id)

演示事实（与 batch-plan gb-573 一致）：
- 实验 A `exp_home_feed_1101`：曝光埋点重复上报 → 曝光口径 52.3% / 47.7%（6536 次曝光），
  SRM χ²≈13.77、p≈0.0002 < 0.001 → 结论锁定 unreadable；
- 实验 B `exp_coupon_default_1105`：主指标 arpu lift +4.2%、p≈0.0311，
  6 个分层中 2 个原始显著但 BH 校正后不显著，守卫指标无回归 → verdict=warn；
- 实验 C `exp_reco_rank_1022`：主指标 retention_d1 lift +50%、p≈0.0034，分层方向一致 → pass，
  已由增长负责人落「上线」决策；
- 实验 D `exp_onboard_modal_1108`：刚开跑，只有 100 条分桶（每臂 50），尚无分析批次。

赋值数据全部由固定种子确定性生成并在落库前按目标均值/标准差标准化，
因此同一份 seed 在任意机器上算出同一组 p 值/CI（可复现）。
"""
from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta
from typing import Any

from src.config.database import session_scope
from src.constants.enums import (
    DecisionKind,
    ExperimentStatus,
    MetricDirection,
    MetricKind,
    MetricRole,
    RunStatus,
)
from src.constants.roles import ROLE_ADMIN, ROLE_ANALYST, ROLE_PM
from src.models import (
    AnalysisRun,
    Assignment,
    Decision,
    Experiment,
    Metric,
    User,
    Variant,
)
from src.models.base import utcnow
from src.services.analysis_service import AnalysisService
from src.utils.password import hash_password

BRAND = "abcheck"
DEMO_PASSWORD = "Demo@2026"
SEED_MARK = "seed"

DEMO_USERS = [
    ("admin@abcheck.io", "青柚出行 · 增长负责人", ROLE_ADMIN),
    ("analyst@abcheck.io", "青柚出行 · 数据分析师", ROLE_ANALYST),
    ("pm@abcheck.io", "青柚出行 · 产品经理", ROLE_PM),
]

METRIC_SPECS = [
    {
        "code": "order_conversion",
        "name": "下单转化率",
        "kind": MetricKind.RATIO.value,
        "role": MetricRole.PRIMARY.value,
        "direction": MetricDirection.INCREASE_GOOD.value,
        "unit": "%",
        "definition": "支付成功用户数 / 分桶曝光用户数（用户级口径）",
    },
    {
        "code": "arpu",
        "name": "曝光人均 GMV",
        "kind": MetricKind.MEAN.value,
        "role": MetricRole.PRIMARY.value,
        "direction": MetricDirection.INCREASE_GOOD.value,
        "unit": "元",
        "definition": "分桶用户窗口内 GMV 均值（用户级均值口径，Welch t 检验）",
    },
    {
        "code": "complaint_rate",
        "name": "客诉率",
        "kind": MetricKind.RATIO.value,
        "role": MetricRole.GUARD.value,
        "direction": MetricDirection.DECREASE_GOOD.value,
        "unit": "%",
        "definition": "发生有效客诉的用户数 / 分桶曝光用户数（守卫指标：显著变差则结论降级）",
    },
    {
        "code": "ticket_rate",
        "name": "客服工单率",
        "kind": MetricKind.RATIO.value,
        "role": MetricRole.GUARD.value,
        "direction": MetricDirection.DECREASE_GOOD.value,
        "unit": "%",
        "definition": "转人工工单用户数 / 分桶曝光用户数（守卫指标）",
    },
    {
        "code": "retention_d1",
        "name": "次日留存率",
        "kind": MetricKind.RATIO.value,
        "role": MetricRole.SECONDARY.value,
        "direction": MetricDirection.INCREASE_GOOD.value,
        "unit": "%",
        "definition": "次日回访用户数 / 分桶曝光用户数",
    },
]

CELLS = [
    ("一线", "新客"),
    ("一线", "老客"),
    ("新一线", "新客"),
    ("新一线", "老客"),
    ("二线", "新客"),
    ("二线", "老客"),
]
BASE_MEAN = 185.0
DEFAULT_SD = 67.1
# B 实验的分层目标：前两层显著（p≈0.014 / 0.040），BH 校正后不显著
B_CELL_SIZES = [150, 130, 120, 110, 100, 90]
B_CELL_LIFTS = [0.104, 0.093, 0.023, -0.005, 0.003, -0.010]

EXPERIMENT_SPECS: list[dict[str, Any]] = [
    {
        "code": "exp_home_feed_1101",
        "name": "首页信息流改版",
        "hypothesis": "新版信息流提高浏览深度，从而提升下单转化率，且不增加客诉。",
        "description": "首页第二屏改为双列信息流卡片，对照组保留单列列表。",
        "owner_name": "林蔚然 · 增长负责人",
        "status": ExperimentStatus.ANALYZING.value,
        "primary_metric": "order_conversion",
        "guard_metrics": ["complaint_rate", "ticket_rate"],
        "secondary_metrics": [],
        "start_date": date(2026, 10, 27),
        "end_date": date(2026, 11, 3),
        "notes": "变体 B 的曝光埋点存在重复上报（同一次会话被计数 2~3 次），先按曝光口径校验分流。",
        "variants": [
            ("control", "分组 A · 原版信息流", 0.5, True, "单列列表，保留原交互"),
            ("treatment", "分组 B · 新版信息流", 0.5, False, "双列卡片 + 自动翻页"),
        ],
        "arms": {
            "control": {
                "users": 950,
                "exposures": 3118,
                "flags": {
                    "order_conversion": 213,
                    "complaint_rate": 31,
                    "ticket_rate": 22,
                    "retention_d1": 300,
                },
                "mean": BASE_MEAN,
                "sd": DEFAULT_SD,
                "seed_base": 1000,
                "step": 17,
            },
            "treatment": {
                "users": 950,
                "exposures": 3418,
                "flags": {
                    "order_conversion": 215,
                    "complaint_rate": 33,
                    "ticket_rate": 24,
                    "retention_d1": 306,
                },
                "mean": BASE_MEAN,
                "sd": DEFAULT_SD,
                "seed_base": 5000,
                "step": 31,
            },
        },
        "seed_run": True,
    },
    {
        "code": "exp_coupon_default_1105",
        "name": "收银台优惠券默认档位",
        "hypothesis": "默认勾选更大的优惠券档位能拉高客单价，而且不会带来客诉与工单上升。",
        "description": "收银台优惠券默认档位从「满 30 减 3」改为「满 60 减 8」，券成本按比例上调。",
        "owner_name": "陈嘉禾 · 数据分析师",
        "status": ExperimentStatus.RUNNING.value,
        "primary_metric": "arpu",
        "guard_metrics": ["complaint_rate", "ticket_rate"],
        "secondary_metrics": ["order_conversion"],
        "start_date": date(2026, 11, 4),
        "end_date": date(2026, 11, 11),
        "notes": "主指标为均值口径（人均 GMV），分层按城市 × 新老客下钻做 BH 校正。",
        "variants": [
            ("control", "分组 A · 满 30 减 3", 0.5, True, "原默认档位"),
            ("treatment", "分组 B · 满 60 减 8", 0.5, False, "更高档位默认勾选"),
        ],
        "arms": {
            "control": {
                "users": 700,
                "exposures": 1400,
                "flags": {
                    "order_conversion": 168,
                    "complaint_rate": 15,
                    "ticket_rate": 24,
                    "retention_d1": 200,
                },
                "mean": BASE_MEAN,
                "sd": DEFAULT_SD,
                "seed_base": 1000,
                "step": 17,
                "cell_sizes": B_CELL_SIZES,
                "cell_lifts": [0.0] * 6,
            },
            "treatment": {
                "users": 700,
                "exposures": 1430,
                "flags": {
                    "order_conversion": 178,
                    "complaint_rate": 16,
                    "ticket_rate": 26,
                    "retention_d1": 206,
                },
                "mean": BASE_MEAN,
                "sd": DEFAULT_SD,
                "seed_base": 5000,
                "step": 31,
                "cell_sizes": B_CELL_SIZES,
                "cell_lifts": B_CELL_LIFTS,
            },
        },
        "seed_run": True,
    },
    {
        "code": "exp_reco_rank_1022",
        "name": "推荐位排序权重调优",
        "hypothesis": "提高近场商品权重，次日留存提升。",
        "description": "推荐位排序权重：近场 0.35 → 0.50，长尾 0.20 → 0.12。",
        "owner_name": "周慕青 · 增长负责人",
        "status": ExperimentStatus.DECIDED.value,
        "primary_metric": "retention_d1",
        "guard_metrics": ["complaint_rate"],
        "secondary_metrics": ["order_conversion"],
        "start_date": date(2026, 10, 20),
        "end_date": date(2026, 10, 27),
        "notes": "已复盘：结论 pass，增长负责人裁决上线，进入灰度放量。",
        "variants": [
            ("control", "分组 A · 原排序权重", 0.5, True, "近场 0.35 / 长尾 0.20"),
            ("treatment", "分组 B · 近场加权", 0.5, False, "近场 0.50 / 长尾 0.12"),
        ],
        "arms": {
            "control": {
                "users": 200,
                "exposures": 402,
                "flags": {
                    "order_conversion": 44,
                    "complaint_rate": 6,
                    "ticket_rate": 9,
                    "retention_d1": 56,
                },
                "mean": BASE_MEAN,
                "sd": DEFAULT_SD,
                "seed_base": 1000,
                "step": 17,
            },
            "treatment": {
                "users": 200,
                "exposures": 398,
                "flags": {
                    "order_conversion": 50,
                    "complaint_rate": 7,
                    "ticket_rate": 10,
                    "retention_d1": 84,
                },
                "mean": BASE_MEAN,
                "sd": DEFAULT_SD,
                "seed_base": 5000,
                "step": 31,
            },
        },
        "seed_run": True,
        "seed_decision": {
            "decision": DecisionKind.SHIP.value,
            "rationale": "主指标次日留存提升 50.0%（p=0.0033，MDE 44.9%），分层方向一致，客诉率无回归，按灰度 20% 放量。",
            "guard_ack": True,
        },
    },
    {
        "code": "exp_onboard_modal_1108",
        "name": "新客引导弹窗文案",
        "hypothesis": "更直接的领券文案提升首单转化。",
        "description": "新客首次进入首页的引导弹窗文案 A/B（「先逛逛」vs「领 8 元券」）。",
        "owner_name": "许一诺 · 产品经理",
        "status": ExperimentStatus.RUNNING.value,
        "primary_metric": "order_conversion",
        "guard_metrics": ["complaint_rate"],
        "secondary_metrics": [],
        "start_date": date(2026, 11, 8),
        "end_date": date(2026, 11, 15),
        "notes": "刚开跑第 1 天，样本未达下限，等待分析师触发首批分析。",
        "variants": [
            ("control", "分组 A · 先逛逛", 0.5, True, "温和引导文案"),
            ("treatment", "分组 B · 领 8 元券", 0.5, False, "直接利益点文案"),
        ],
        "arms": {
            "control": {
                "users": 50,
                "exposures": 50,
                "flags": {
                    "order_conversion": 11,
                    "complaint_rate": 2,
                    "ticket_rate": 2,
                    "retention_d1": 16,
                },
                "mean": BASE_MEAN,
                "sd": DEFAULT_SD,
                "seed_base": 1000,
                "step": 17,
            },
            "treatment": {
                "users": 50,
                "exposures": 50,
                "flags": {
                    "order_conversion": 12,
                    "complaint_rate": 2,
                    "ticket_rate": 2,
                    "retention_d1": 17,
                },
                "mean": BASE_MEAN,
                "sd": DEFAULT_SD,
                "seed_base": 5000,
                "step": 31,
            },
        },
        "seed_run": False,
    },
]

RATIO_METRIC_CODES = [spec["code"] for spec in METRIC_SPECS if spec["kind"] == MetricKind.RATIO.value]

CREATED = 0
SKIPPED = 0


def _log(kind: str, entity: str, key: str) -> None:
    global CREATED, SKIPPED
    if kind == "SEED_CREATED":
        CREATED += 1
    else:
        SKIPPED += 1
    print(f"{kind} entity={entity} key={key}", flush=True)


def _created(entity: str, key: str) -> None:
    _log("SEED_CREATED", entity, key)


def _skipped(entity: str, key: str) -> None:
    _log("SEED_SKIPPED", entity, key)


# ---------------------------------------------------------------- 数据生成 ----
def _standardized(n: int, mean: float, sd: float, seed: int) -> list[float]:
    """固定种子生成后标准化：样本均值/标准差精确等于目标值，保证 p 值可复现。"""
    rng = random.Random(seed)
    raw = [rng.gauss(0.0, 1.0) for _ in range(n)]
    m = sum(raw) / n
    var = sum((value - m) ** 2 for value in raw) / (n - 1)
    scale = math.sqrt(var)
    return [mean + sd * (value - m) / scale for value in raw]


def _spread_flags(n: int, k: int) -> list[bool]:
    """n 行里精确挑 k 行为 True，且均匀铺开（避免与分层/曝光顺序相关）。"""
    if k <= 0:
        return [False] * n
    if k >= n:
        return [True] * n
    flags = [False] * n
    for j in range(k):
        flags[(j * n) // k] = True
    return flags


def _exposure_series(rows: int, total: int) -> list[int]:
    """把 total 次曝光分摊到 rows 条记录上，余数均匀铺开。"""
    base = total // rows
    remainder = total - base * rows
    extra = _spread_flags(rows, remainder)
    return [base + (1 if flag else 0) for flag in extra]


def _cell_sizes(users: int, given: list[int] | None) -> list[int]:
    if given:
        return list(given)
    base = users // len(CELLS)
    remainder = users - base * len(CELLS)
    return [base + (1 if index < remainder else 0) for index in range(len(CELLS))]


def _build_assignments(spec: dict[str, Any], experiment_id: int, variant_ids: dict[str, int]) -> list[Assignment]:
    rows: list[Assignment] = []
    start = spec["start_date"] or date(2026, 11, 1)
    for arm_key, variant_code in (("control", "control"), ("treatment", "treatment")):
        arm = spec["arms"][arm_key]
        users = int(arm["users"])
        sizes = _cell_sizes(users, arm.get("cell_sizes"))
        cell_lifts = arm.get("cell_lifts") or [0.0] * len(CELLS)
        values: list[float] = []
        segments: list[tuple[str, str]] = []
        for index, (city, tenure) in enumerate(CELLS):
            n = sizes[index]
            cell_mean = float(arm.get("mean", BASE_MEAN)) * (1.0 + cell_lifts[index])
            values.extend(
                _standardized(n, cell_mean, float(arm.get("sd", DEFAULT_SD)), int(arm["seed_base"]) + index * int(arm.get("step", 17)))
            )
            segments.extend([(city, tenure)] * n)
        metric_flags = {
            code: _spread_flags(users, int(arm["flags"].get(code, 0))) for code in RATIO_METRIC_CODES
        }
        exposures = _exposure_series(users, int(arm["exposures"]))
        variant_id = variant_ids[variant_code]
        for index in range(users):
            city, tenure = segments[index]
            rows.append(
                Assignment(
                    experiment_id=experiment_id,
                    variant_id=variant_id,
                    user_key=f"{spec['code'].upper()}-{variant_code.upper()}-{index:04d}",
                    bucket=(index * 7919 + variant_id * 13) % 10000,
                    exposure_count=exposures[index],
                    segment_city=city,
                    segment_tenure=tenure,
                    flags={code: metric_flags[code][index] for code in RATIO_METRIC_CODES},
                    metric_value=round(values[index], 6),
                    exposed_at=datetime.combine(start, datetime.min.time())
                    + timedelta(minutes=(index * 37) % (6 * 24 * 60)),
                )
            )
    return rows


# -------------------------------------------------------------------- seed ----
def seed_users(db) -> dict[str, User]:
    users: dict[str, User] = {}
    for email, display_name, role in DEMO_USERS:
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(DEMO_PASSWORD),
                display_name=display_name,
                role=role,
                is_active=True,
            )
            db.add(user)
            db.flush()
            _created("User", email)
        else:
            _skipped("User", email)
        users[role] = user
    db.commit()
    return users


def seed_metrics(db) -> dict[str, Metric]:
    metrics: dict[str, Metric] = {}
    for spec in METRIC_SPECS:
        metric = db.query(Metric).filter(Metric.code == spec["code"]).one_or_none()
        if metric is None:
            metric = Metric(
                code=spec["code"],
                name=spec["name"],
                kind=spec["kind"],
                role=spec["role"],
                direction=spec["direction"],
                unit=spec["unit"],
                definition=spec["definition"],
            )
            db.add(metric)
            db.flush()
            _created("Metric", spec["code"])
        else:
            _skipped("Metric", spec["code"])
        metrics[spec["code"]] = metric
    db.commit()
    return metrics


def seed_experiments(db, metrics: dict[str, Metric]) -> dict[str, dict[str, Any]]:
    """实验 + 变体 + 分桶曝光。"""
    result: dict[str, dict[str, Any]] = {}
    for spec in EXPERIMENT_SPECS:
        experiment = db.query(Experiment).filter(Experiment.code == spec["code"]).one_or_none()
        if experiment is None:
            experiment = Experiment(
                code=spec["code"],
                name=spec["name"],
                hypothesis=spec["hypothesis"],
                description=spec["description"],
                owner_name=spec["owner_name"],
                status=spec["status"],
                primary_metric_id=metrics[spec["primary_metric"]].id,
                guard_metric_ids=[metrics[code].id for code in spec["guard_metrics"]],
                secondary_metric_ids=[metrics[code].id for code in spec["secondary_metrics"]],
                start_date=spec["start_date"],
                end_date=spec["end_date"],
                alpha=0.05,
                srm_threshold=0.001,
                min_sample_per_arm=120,
                notes=spec["notes"],
                created_by="admin@abcheck.io",
            )
            db.add(experiment)
            db.flush()
            _created("Experiment", spec["code"])
        else:
            _skipped("Experiment", spec["code"])

        variant_ids: dict[str, int] = {}
        for code, name, allocation, is_control, description in spec["variants"]:
            variant = (
                db.query(Variant)
                .filter(Variant.experiment_id == experiment.id, Variant.code == code)
                .one_or_none()
            )
            if variant is None:
                variant = Variant(
                    experiment_id=experiment.id,
                    code=code,
                    name=name,
                    traffic_allocation=allocation,
                    is_control=is_control,
                    description=description,
                )
                db.add(variant)
                db.flush()
                _created("Variant", f"{spec['code']}/{code}")
            else:
                _skipped("Variant", f"{spec['code']}/{code}")
            variant_ids[code] = variant.id

        db.commit()

        expected = sum(int(spec["arms"][arm]["users"]) for arm in ("control", "treatment"))
        existing_keys = {
            key
            for (key,) in db.query(Assignment.user_key)
            .filter(Assignment.experiment_id == experiment.id)
            .all()
        }
        if len(existing_keys) >= expected:
            _skipped("Assignment", spec["code"])
        else:
            todo = [
                row
                for row in _build_assignments(spec, experiment.id, variant_ids)
                if row.user_key not in existing_keys
            ]
            db.add_all(todo)
            db.commit()
            _created("Assignment", f"{spec['code']} (+{len(todo)})")

        result[spec["code"]] = {"experiment": experiment, "variant_ids": variant_ids}
    return result


def seed_runs(db, seeded: dict[str, dict[str, Any]], users: dict[str, User]) -> None:
    """用真实分析服务算批次并落库（A/B/C 各 1 个批次）。"""
    admin_email = users[ROLE_ADMIN].email
    for spec in EXPERIMENT_SPECS:
        if not spec.get("seed_run"):
            continue
        experiment: Experiment = seeded[spec["code"]]["experiment"]
        run_code = f"RUN-{spec['code'].upper()}-001"
        run = db.query(AnalysisRun).filter(AnalysisRun.run_code == run_code).one_or_none()
        if run is not None:
            _skipped("AnalysisRun", run_code)
        else:
            run = AnalysisRun(
                experiment_id=experiment.id,
                run_code=run_code,
                status=RunStatus.RUNNING.value,
                triggered_by=SEED_MARK,
                params={
                    "alpha": experiment.alpha,
                    "srm_threshold": experiment.srm_threshold,
                    "min_sample_per_arm": experiment.min_sample_per_arm,
                    "srm_unit": "exposure",
                    "metric_unit": "user",
                    "mde_power": 0.8,
                },
                started_at=utcnow(),
            )
            db.add(run)
            db.flush()
            payload = AnalysisService(db).compute(experiment)
            run.srm = payload["srm"]
            run.metrics = payload["metrics"]
            run.strata = payload["strata"]
            run.comparisons = payload["comparisons"]
            run.guard = payload["guard"]
            run.verdict = payload["verdict"]
            run.verdict_reasons = payload["verdict_reasons"]
            run.locked = payload["locked"]
            run.status = RunStatus.SUCCEEDED.value
            run.finished_at = utcnow()
            db.commit()
            _created("AnalysisRun", f"{run_code} verdict={run.verdict}")
            print(
                f"SEED_ANALYSIS run={run_code} verdict={run.verdict} "
                f"srm_p={(run.srm or {}).get('p_value')}",
                flush=True,
            )

        decision_spec = spec.get("seed_decision")
        if decision_spec:
            stored_run = db.query(AnalysisRun).filter(AnalysisRun.run_code == run_code).one()
            decision = (
                db.query(Decision)
                .filter(Decision.experiment_id == experiment.id, Decision.run_id == stored_run.id)
                .one_or_none()
            )
            if decision is None:
                db.add(
                    Decision(
                        experiment_id=experiment.id,
                        run_id=stored_run.id,
                        decision=decision_spec["decision"],
                        rationale=decision_spec["rationale"],
                        reviewer=admin_email,
                        guard_ack=bool(decision_spec["guard_ack"]),
                        exported_formats=["md", "csv"],
                    )
                )
                db.commit()
                _created("Decision", f"{spec['code']}/{decision_spec['decision']}")
            else:
                _skipped("Decision", spec["code"])


def print_summary(db) -> str:
    codes = [spec["code"] for spec in EXPERIMENT_SPECS]
    experiment_ids = [row[0] for row in db.query(Experiment.id).filter(Experiment.code.in_(codes)).all()]
    experiments = len(experiment_ids)
    variants = (
        db.query(Variant).filter(Variant.experiment_id.in_(experiment_ids)).count()
        if experiment_ids
        else 0
    )
    metrics = db.query(Metric).filter(Metric.code.in_([m["code"] for m in METRIC_SPECS])).count()
    assignments = (
        db.query(Assignment).filter(Assignment.experiment_id.in_(experiment_ids)).count()
        if experiment_ids
        else 0
    )
    runs = db.query(AnalysisRun).filter(AnalysisRun.triggered_by == SEED_MARK).count()
    emails = [email for email, _name, _role in DEMO_USERS]
    users = db.query(User).filter(User.email.in_(emails)).count()
    line = (
        f"SEED_SUMMARY brand={BRAND} experiments={experiments} variants={variants} "
        f"metrics={metrics} assignments={assignments} runs={runs} users={users}"
    )
    print(line, flush=True)
    return line


def seed_all() -> dict[str, Any]:
    with session_scope() as db:
        users = seed_users(db)
        metrics = seed_metrics(db)
        seeded = seed_experiments(db, metrics)
        seed_runs(db, seeded, users)
        summary = print_summary(db)
    return {"created": CREATED, "skipped": SKIPPED, "summary": summary}


if __name__ == "__main__":
    result = seed_all()
    print(f"SEED_DONE created={result['created']} skipped={result['skipped']}", flush=True)
