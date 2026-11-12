"""分析编排：SRM → 指标对比 → 分层 BH → 守卫指标回归 → 固定规则结论。

计算口径（写进 README/报告）：
- SRM：曝光次数口径（exposure），χ² = Σ(O−E)²/E，df = k−1，p < srm_threshold 判 SRM 并锁定结论
- 指标：用户级样本；比例用两比例 z（合并方差），均值用 Welch t
- 效应：lift = (处理组 − 对照组) / 对照组；lift_ci95 由 diff 的 95% CI 同除对照组基准
- MDE：80% 功效、双侧 α，比例/均值分别按各自标准误计算
- 多重比较：分层内 BH（family=strata）+ 全量 BH（primary/guard/secondary/strata 合并）；
  守卫指标在守卫族内单独 BH，任一显著变差 → 结论 fail
- 结论固定规则：SRM/样本不足 → unreadable（SRM 时 locked）；
  守卫回归或主指标不显著 → fail；分层异质性（≥2 个分层原始显著但 BH 后不显著）、
  分层反向显著、观测效应低于 MDE → warn；其余 pass
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants import error_codes as codes
from src.constants.enums import (
    ExperimentStatus,
    GuardState,
    MetricKind,
    RunStatus,
    SrmVerdict,
    Verdict,
)
from src.constants.limits import MIN_STRATUM_PER_ARM
from src.models.analysis_run import AnalysisRun
from src.models.assignment import Assignment
from src.models.experiment import Experiment
from src.models.metric import Metric
from src.models.base import utcnow
from src.services.assignment_service import (
    CITY_ORDER,
    TENURE_ORDER,
    ordered_variants,
    variant_counts,
    load_assignments,
)
from src.services.fdr_service import adjust_family
from src.utils.errors import AppError
from src.utils.statistics import (
    srm_test,
    two_proportion_test,
    welch_test,
)


def _metric_dict(metric: Metric) -> dict[str, Any]:
    return {
        "id": metric.id,
        "code": metric.code,
        "name": metric.name,
        "kind": metric.kind,
        "role": metric.role,
        "direction": metric.direction,
        "unit": metric.unit,
        "definition": metric.definition or "",
    }


def _rows_by_variant(assignments: list[Assignment]) -> dict[int, list[Assignment]]:
    grouped: dict[int, list[Assignment]] = defaultdict(list)
    for row in assignments:
        grouped[row.variant_id].append(row)
    return grouped


def _compute_metric(
    metric: Metric,
    control_rows: list[Assignment],
    treat_rows: list[Assignment],
    alpha: float,
) -> dict[str, Any]:
    """按指标口径选择检验方法，返回统一口径的效应量结构。"""
    if not control_rows or not treat_rows:
        raise AppError(codes.CONFLICT, "对照组或实验组没有样本，无法检验", f"metric={metric.code}", 409)

    if metric.kind == MetricKind.RATIO.value:
        control_success = sum(1 for row in control_rows if (row.flags or {}).get(metric.code))
        treat_success = sum(1 for row in treat_rows if (row.flags or {}).get(metric.code))
        stat = two_proportion_test(
            control_success, len(control_rows), treat_success, len(treat_rows), alpha
        )
        control_value = stat["control_rate"]
        treat_value = stat["treat_rate"]
        point_label = "转化率"
    else:
        control_values = [float(row.metric_value or 0.0) for row in control_rows]
        treat_values = [float(row.metric_value or 0.0) for row in treat_rows]
        stat = welch_test(control_values, treat_values, alpha)
        control_value = stat["control_mean"]
        treat_value = stat["treat_mean"]
        point_label = "均值"

    return {
        "metric": _metric_dict(metric),
        "kind": metric.kind,
        "direction": metric.direction,
        "point_label": point_label,
        "control_value": control_value,
        "treat_value": treat_value,
        "stat": stat,
    }


def _is_bad_direction(metric: Metric, diff: float) -> bool:
    if metric.direction == "decrease_good":
        return diff > 0
    return diff < 0


def _strata_tests(
    primary: Metric,
    assignments: list[Assignment],
    control_id: int,
    treat_id: int,
    alpha: float,
) -> dict[str, Any]:
    """按 城市 × 客群 分层，执行主指标检验 + 分层内 BH。"""
    grouped: dict[tuple[str, str], dict[int, list[Assignment]]] = defaultdict(
        lambda: {control_id: [], treat_id: []}
    )
    for row in assignments:
        if row.variant_id not in (control_id, treat_id):
            continue
        key = (row.segment_city, row.segment_tenure)
        grouped[key][row.variant_id].append(row)

    keys = [
        (city, tenure)
        for city in CITY_ORDER
        for tenure in TENURE_ORDER
        if (city, tenure) in grouped
    ]
    # 兜底：出现枚举之外的组合也要展示，放在最后
    for key in grouped:
        if key not in keys:
            keys.append(key)

    cells: list[dict[str, Any]] = []
    for city, tenure in keys:
        control_rows = grouped[(city, tenure)][control_id]
        treat_rows = grouped[(city, tenure)][treat_id]
        cell: dict[str, Any] = {
            "segment_city": city,
            "segment_tenure": tenure,
            "control_n": len(control_rows),
            "treat_n": len(treat_rows),
            "testable": min(len(control_rows), len(treat_rows)) >= MIN_STRATUM_PER_ARM,
        }
        if not cell["testable"]:
            cell.update(
                {
                    "control_value": None,
                    "treat_value": None,
                    "diff": None,
                    "lift": None,
                    "p_value": None,
                    "q_value": None,
                    "significant_raw": False,
                    "significant_bh": False,
                    "note": f"每臂样本 < {MIN_STRATUM_PER_ARM}，该分层不参与多重比较",
                }
            )
            cells.append(cell)
            continue

        computed = _compute_metric(primary, control_rows, treat_rows, alpha)
        stat = computed["stat"]
        cell.update(
            {
                "control_value": computed["control_value"],
                "treat_value": computed["treat_value"],
                "diff": stat["diff"],
                "lift": stat["lift"],
                "p_value": stat["p_value"],
                "significant_raw": bool(stat["p_value"] is not None and stat["p_value"] < alpha),
                "stat": stat,
                "note": "",
            }
        )
        cells.append(cell)

    tested = [cell for cell in cells if cell.get("p_value") is not None]
    family = adjust_family(tested, alpha=alpha)
    for cell in tested:
        cell["significant_bh"] = bool(cell.get("q_value") is not None and cell["q_value"] <= alpha)
        if cell["significant_raw"] and not cell["significant_bh"]:
            cell["note"] = "原始显著但 BH 校正后不显著"

    raw_sig = sum(1 for cell in tested if cell["significant_raw"])
    bh_sig = sum(1 for cell in tested if cell["significant_bh"])
    return {
        "dimensions": ["segment_city", "segment_tenure"],
        "alpha": alpha,
        "cells": cells,
        "family": family,
        "summary": {
            "cells_total": len(cells),
            "cells_tested": len(tested),
            "insufficient_cells": len(cells) - len(tested),
            "raw_significant": raw_sig,
            "bh_significant": bh_sig,
            "flagged_non_significant": raw_sig - bh_sig,
        },
    }


def _evaluate_guards(
    guard_metrics: list[Metric],
    comparisons: dict[int, dict[str, Any]],
    alpha: float,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for metric in guard_metrics:
        computed = comparisons[metric.id]
        stat = computed["stat"]
        diff = stat["diff"]
        bad = _is_bad_direction(metric, diff)
        checks.append(
            {
                "code": metric.code,
                "name": metric.name,
                "direction": metric.direction,
                "diff": diff,
                "lift": stat["lift"],
                "p_value": stat["p_value"],
                "bad_direction": bad,
                "state": GuardState.INCONCLUSIVE.value,
                "note": "",
            }
        )

    family = adjust_family([check for check in checks], alpha=alpha)
    for check in checks:
        significant = bool(check["p_value"] is not None and check["p_value"] < alpha)
        significant_bh = bool(check.get("q_value") is not None and check["q_value"] <= alpha)
        check["significant"] = significant_bh
        if not significant:
            check["state"] = GuardState.INCONCLUSIVE.value
            check["note"] = "无显著变化"
        elif check["bad_direction"]:
            check["state"] = GuardState.REGRESSION.value
            check["note"] = "显著变差：触发结论降级"
        else:
            check["state"] = GuardState.IMPROVED.value
            check["note"] = "显著变好"
        del check["significant"]

    regression = any(check["state"] == GuardState.REGRESSION.value for check in checks)
    return {"checks": checks, "regression": regression, "family": family}


def _decide(
    experiment: Experiment,
    srm: dict[str, Any],
    primary: dict[str, Any],
    guards: dict[str, Any],
    strata: dict[str, Any],
    alpha: float,
    min_sample: int,
    control_n: int,
    treat_n: int,
) -> tuple[str, list[str], bool]:
    reasons: list[str] = []
    if srm["verdict"] == SrmVerdict.DETECTED.value:
        reasons.append(f"SRM 分流失衡：{srm['reason']}")
        reasons.append("分流失衡期间指标不可采信 → 结论锁定为「不可读」，需先修分流器/埋点后重跑")
        return Verdict.UNREADABLE.value, reasons, True
    if srm["verdict"] == SrmVerdict.INSUFFICIENT.value:
        reasons.append(f"曝光量不足：{srm['reason']}")
        return Verdict.UNREADABLE.value, reasons, True
    if min(control_n, treat_n) < min_sample:
        reasons.append(
            f"样本不足：最小臂样本 {min(control_n, treat_n)} < 阈值 {min_sample} → 结论不可读"
        )
        return Verdict.UNREADABLE.value, reasons, False

    if guards["regression"]:
        bad = [check for check in guards["checks"] if check["state"] == GuardState.REGRESSION.value]
        reasons.append(
            "守卫指标显著变差：" + "，".join(f"{c['code']}" for c in bad) + " → 结论 fail"
        )
        return Verdict.FAIL.value, reasons, False

    stat = primary["stat"]
    if stat["p_value"] is None or stat["p_value"] >= alpha:
        reasons.append(
            f"主指标未达显著：p={stat['p_value']:.4f} ≥ α={alpha} → 不能判定上线"
        )
        return Verdict.FAIL.value, reasons, False

    warn_reasons: list[str] = []
    flagged = [
        cell
        for cell in strata["cells"]
        if cell.get("p_value") is not None
        and cell["significant_raw"]
        and not cell["significant_bh"]
    ]
    if len(flagged) >= 2:
        labels = "、".join(f"{c['segment_city']}·{c['segment_tenure']}" for c in flagged)
        warn_reasons.append(
            f"分层异质性：{len(flagged)} 个分层原始显著但 BH 校正后不显著（{labels}）"
        )

    primary_sign = 1 if (stat["lift"] or 0) >= 0 else -1
    opposite = [
        cell
        for cell in strata["cells"]
        if cell.get("p_value") is not None
        and cell["p_value"] < alpha
        and cell.get("lift") is not None
        and (1 if cell["lift"] >= 0 else -1) != primary_sign
    ]
    if opposite:
        warn_reasons.append(
            "存在方向相反的分层显著项："
            + "、".join(f"{c['segment_city']}·{c['segment_tenure']}" for c in opposite)
        )

    mde_rel = (stat.get("mde_required") or {}).get("relative")
    if mde_rel and stat["lift"] is not None and abs(stat["lift"]) < mde_rel:
        warn_reasons.append(
            f"观测效应 {stat['lift'] * 100:+.2f}% 低于 80% 功效所需 MDE {mde_rel * 100:.2f}%"
            "（结论处于功效边界，建议延长实验）"
        )

    if warn_reasons:
        reasons.append(f"主指标显著（lift={stat['lift'] * 100:+.2f}%, p={stat['p_value']:.4f}）")
        reasons.extend(warn_reasons)
        reasons.append("按固定规则判定为 warn：可继续观察/带风险上线，需记录决策理由")
        return Verdict.WARN.value, reasons, False

    reasons.append(f"主指标显著（lift={stat['lift'] * 100:+.2f}%, p={stat['p_value']:.4f}）")
    reasons.append("分层方向一致、守卫指标无回归 → 判定 pass")
    return Verdict.PASS.value, reasons, False


class AnalysisService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------- 创建批次 ----
    def create_run(self, experiment: Experiment, actor_email: str) -> AnalysisRun:
        if len(experiment.variants) != 2:
            raise AppError(
                codes.VALIDATION_FAILED,
                "统计判定需要恰好 2 个变体（对照组 + 实验组）",
                f"experiment={experiment.code}",
                422,
            )
        seq = (
            self.db.query(func.count(AnalysisRun.id))
            .filter(AnalysisRun.experiment_id == experiment.id)
            .scalar()
            or 0
        )
        run = AnalysisRun(
            experiment_id=experiment.id,
            run_code=f"RUN-{experiment.code.upper()}-{seq + 1:03d}",
            status=RunStatus.PENDING.value,
            triggered_by=actor_email,
            params={
                "alpha": experiment.alpha,
                "srm_threshold": experiment.srm_threshold,
                "min_sample_per_arm": experiment.min_sample_per_arm,
                "srm_unit": "exposure",
                "metric_unit": "user",
                "mde_power": 0.8,
            },
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        from src.config.celery_app import TASK_ANALYSIS_RUN, celery_app

        try:
            celery_app.send_task(TASK_ANALYSIS_RUN, args=[run.id])
        except Exception as exc:  # noqa: BLE001 - 投递失败要落库，前端可见
            run.status = RunStatus.FAILED.value
            run.error = f"任务投递失败：{exc}"
            run.finished_at = utcnow()
            self.db.commit()
            raise AppError(
                codes.INTERNAL_ERROR, "分析任务投递失败，请稍后重试", str(exc), 503
            ) from exc
        return run

    # ------------------------------------------------------------- 执行计算 ----
    def execute(self, run_id: int) -> str:
        run = self.db.get(AnalysisRun, run_id)
        if run is None:
            raise AppError(codes.NOT_FOUND, "分析批次不存在", f"run_id={run_id}", 404)
        run.status = RunStatus.RUNNING.value
        run.started_at = utcnow()
        self.db.commit()
        try:
            payload = self.compute(run.experiment)
        except AppError as exc:
            run.status = RunStatus.FAILED.value
            run.error = f"{exc.message}（{exc.detail or ''}）"
            run.finished_at = utcnow()
            self.db.commit()
            raise
        except Exception as exc:  # noqa: BLE001
            run.status = RunStatus.FAILED.value
            run.error = f"分析异常：{exc}"
            run.finished_at = utcnow()
            self.db.commit()
            raise

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

        experiment = run.experiment
        if payload["verdict"] == Verdict.UNREADABLE.value:
            experiment.status = ExperimentStatus.ANALYZING.value
        self.db.commit()
        return run.verdict or ""

    # --------------------------------------------------------------- 核心算 ----
    def compute(self, experiment: Experiment) -> dict[str, Any]:
        alpha = float(experiment.alpha or settings.default_alpha)
        srm_threshold = float(experiment.srm_threshold or settings.default_srm_threshold)
        min_sample = int(experiment.min_sample_per_arm or settings.min_sample_per_arm)

        variants = ordered_variants(experiment)
        control, treat = variants[0], variants[1]
        assignments = load_assignments(self.db, experiment.id)
        counts = variant_counts(assignments)

        # ---- 1) SRM 分流校验（曝光次数口径）----
        expected_ratio = [control.traffic_allocation, treat.traffic_allocation]
        total_ratio = sum(expected_ratio) or 1.0
        expected_ratio = [r / total_ratio for r in expected_ratio]
        srm = srm_test(
            [counts[control.id]["exposures"], counts[treat.id]["exposures"]],
            expected_ratio,
            threshold=srm_threshold,
            min_exposures=settings.min_srm_exposures,
        )
        srm["unit"] = "exposure"
        srm["variant_codes"] = [control.code, treat.code]
        srm["variant_names"] = [control.name, treat.name]

        # ---- 2) 指标对比（用户级样本）----
        metrics_by_id = {m.id: m for m in self.db.query(Metric).all()}
        grouped = _rows_by_variant(assignments)
        control_rows = grouped[control.id]
        treat_rows = grouped[treat.id]

        primary_metric = metrics_by_id.get(experiment.primary_metric_id)
        if primary_metric is None:
            raise AppError(
                codes.CONFLICT, "实验未设置主指标，无法判定显著性", f"experiment={experiment.code}", 409
            )
        guard_metrics = [
            metrics_by_id[mid] for mid in (experiment.guard_metric_ids or []) if mid in metrics_by_id
        ]
        secondary_metrics = [
            metrics_by_id[mid]
            for mid in (experiment.secondary_metric_ids or [])
            if mid in metrics_by_id
        ]

        comparisons: dict[int, dict[str, Any]] = {}
        metric_payload: list[dict[str, Any]] = []
        for metric, family in (
            [(primary_metric, "primary")]
            + [(m, "guard") for m in guard_metrics]
            + [(m, "secondary") for m in secondary_metrics]
        ):
            if metric.id in comparisons:
                continue
            computed = _compute_metric(metric, control_rows, treat_rows, alpha)
            computed["family"] = family
            comparisons[metric.id] = computed
            metric_payload.append(computed)

        # ---- 3) 守卫指标回归判定（守卫族内 BH）----
        guards = _evaluate_guards(guard_metrics, comparisons, alpha)

        # ---- 4) 分层分析（城市 × 客群，分层内 BH）----
        strata = _strata_tests(primary_metric, assignments, control.id, treat.id, alpha)

        # ---- 5) 全量 BH：primary + guards + secondary + 分层合并一个 family ----
        all_tests: list[dict[str, Any]] = []
        for entry in metric_payload:
            stat = entry["stat"]
            all_tests.append(
                {
                    "family": entry["family"],
                    "label": f"{entry['metric']['name']}（{entry['family']}）",
                    "metric_code": entry["metric"]["code"],
                    "p_value": stat["p_value"],
                }
            )
        for cell in strata["cells"]:
            if cell.get("p_value") is None:
                continue
            all_tests.append(
                {
                    "family": "strata",
                    "label": f"{cell['segment_city']}·{cell['segment_tenure']} 分层",
                    "metric_code": primary_metric.code,
                    "p_value": cell["p_value"],
                }
            )
        full_family = adjust_family(all_tests, alpha=alpha)

        # ---- 6) 固定规则结论 ----
        verdict, reasons, locked = _decide(
            experiment,
            srm,
            comparisons[primary_metric.id],
            guards,
            strata,
            alpha,
            min_sample,
            len(control_rows),
            len(treat_rows),
        )

        return {
            "srm": srm,
            "metrics": metric_payload,
            "strata": strata,
            "guard": guards,
            "comparisons": all_tests,
            "full_family": full_family,
            "verdict": verdict,
            "verdict_reasons": reasons,
            "locked": locked,
            "sample": {
                "control_users": len(control_rows),
                "treat_users": len(treat_rows),
                "control_exposures": counts[control.id]["exposures"],
                "treat_exposures": counts[treat.id]["exposures"],
                "min_sample_per_arm": min_sample,
            },
            "variant_codes": [control.code, treat.code],
        }
