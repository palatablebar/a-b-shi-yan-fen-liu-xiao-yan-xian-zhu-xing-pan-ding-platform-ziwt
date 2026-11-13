"""分析编排：SRM → 逐方案指标对比 → 分层 BH → 守卫指标回归 → 全方案统一 BH → 固定规则结论。

支持两种形态：
- 两臂（对照 + 单一处理）：沿用历史口径，主指标按原始 p 判定（单一预注册主指标），
  批次顶层字段（srm/metrics/strata/comparisons/guard/verdict…）结构保持不变；
- 多臂（共同对照 + ≥2 个处理方案）：每个处理方案都以同一个对照臂为基准做
  配对 SRM 与指标检验；所有方案的主/守卫/辅助/分层检验合并进**同一个 BH family**
  做一次多重比较校正；逐方案给出 verdict 与 ship_state（可上线状态），
  守卫生效或校正后失真的方案一律 blocked，不能被当成赢家。

计算口径（写进 README/报告）：
- SRM：曝光次数口径（exposure），全实验 χ² = Σ(O−E)²/E，df=k−1，p < srm_threshold 判 SRM 并锁定结论；
  多臂时额外对「共同对照 vs 每个处理方案」做配对 SRM
- 指标：用户级样本；比例用两比例 z（合并方差），均值用 Welch t
- 效应：lift = (处理组 − 对照组) / 对照组；lift_ci95 由 diff 的 95% CI 同除对照组基准
- MDE：80% 功效、双侧 α，比例/均值分别按各自标准误计算
- 多重比较：分层内 BH（family=strata，逐方案各自一个族）+ 守卫族内 BH（逐方案）+
  全量 BH（多臂时跨全部方案的 primary/guard/secondary/strata 合并为一个族）
- 结论固定规则：SRM/样本不足 → unreadable（SRM 时 locked）；
  守卫回归或主指标不显著（多臂还要求全量 BH 后仍显著）→ fail；分层异质性
  （≥2 个分层原始显著但 BH 后不显著）、分层反向显著、观测效应低于 MDE → warn；其余 pass
"""
from __future__ import annotations

from collections import defaultdict
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
    ShipState,
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
    """按 城市 × 客群 分层，执行主指标检验 + 分层内 BH（单个方案一个族）。"""
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


def _variant_brief(variant: Any) -> dict[str, Any]:
    return {
        "id": variant.id,
        "code": variant.code,
        "name": variant.name,
        "traffic_allocation": variant.traffic_allocation,
        "is_control": variant.is_control,
        "description": variant.description or "",
    }


def _decide_arm(
    *,
    variant_code: str,
    srm_global: dict[str, Any],
    srm_pair: dict[str, Any],
    primary: dict[str, Any],
    guards: dict[str, Any],
    strata: dict[str, Any],
    alpha: float,
    min_sample: int,
    control_n: int,
    treat_n: int,
    multi_arm: bool,
    primary_q: float | None,
) -> tuple[str, list[str], str]:
    """单个处理方案的固定规则判定，返回 (verdict, reasons, ship_state)。"""
    reasons: list[str] = []
    stat = primary["stat"]

    if srm_global["verdict"] == SrmVerdict.DETECTED.value:
        reasons.append(f"全实验 SRM 分流失衡：{srm_global['reason']}")
        reasons.append("分流失衡期间指标不可采信 → 该方案结论锁定为「不可读」，需先修分流器/埋点后重跑")
        return Verdict.UNREADABLE.value, reasons, ShipState.BLOCKED.value
    if srm_global["verdict"] == SrmVerdict.INSUFFICIENT.value:
        reasons.append(f"曝光量不足：{srm_global['reason']}")
        return Verdict.UNREADABLE.value, reasons, ShipState.BLOCKED.value
    if srm_pair["verdict"] == SrmVerdict.DETECTED.value:
        reasons.append(
            f"方案 {variant_code} 相对共同对照的配对分流校验失衡：{srm_pair['reason']}"
            " → 该方案不可读，需先修分流器/埋点后重跑"
        )
        return Verdict.UNREADABLE.value, reasons, ShipState.BLOCKED.value
    if srm_pair["verdict"] == SrmVerdict.INSUFFICIENT.value:
        reasons.append(
            f"方案 {variant_code} 配对曝光量不足：{srm_pair['reason']} → 该方案不可读"
        )
        return Verdict.UNREADABLE.value, reasons, ShipState.BLOCKED.value
    if min(control_n, treat_n) < min_sample:
        reasons.append(
            f"样本不足：最小臂样本 {min(control_n, treat_n)} < 阈值 {min_sample} → 结论不可读"
        )
        return Verdict.UNREADABLE.value, reasons, ShipState.BLOCKED.value

    if guards["regression"]:
        bad = [check for check in guards["checks"] if check["state"] == GuardState.REGRESSION.value]
        reasons.append(
            "守卫指标显著变差：" + "，".join(f"{c['code']}" for c in bad) + " → 禁止上线，结论 fail"
        )
        if multi_arm and (primary_q is None or primary_q > alpha):
            reasons.append(
                f"同时主指标全方案统一 BH 校正后失真（q={primary_q:.4f} > α={alpha}），"
                "原始显著不能作为上线依据"
            )
        return Verdict.FAIL.value, reasons, ShipState.BLOCKED.value

    if stat["p_value"] is None or stat["p_value"] >= alpha:
        reasons.append(
            f"主指标未达显著：p={stat['p_value']:.4f} ≥ α={alpha} → 不能判定上线"
        )
        return Verdict.FAIL.value, reasons, ShipState.BLOCKED.value

    if multi_arm and (primary_q is None or primary_q > alpha):
        reasons.append(
            f"主指标原始显著（p={stat['p_value']:.4f}），但全方案统一 BH 校正后 q={primary_q:.4f} > α={alpha}"
            "：校正后失真，不能当赢家 → 结论 fail"
        )
        return Verdict.FAIL.value, reasons, ShipState.BLOCKED.value

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

    primary_head = (
        f"主指标显著（lift={stat['lift'] * 100:+.2f}%, p={stat['p_value']:.4f}"
        + (f", 全方案 BH q={primary_q:.4f}）" if multi_arm else "）")
    )
    if warn_reasons:
        reasons.append(primary_head)
        reasons.extend(warn_reasons)
        reasons.append("按固定规则判定为 warn：仅可继续观察/带风险评审，不可直接放量")
        return Verdict.WARN.value, reasons, ShipState.WATCH_ONLY.value

    reasons.append(primary_head)
    tail = "分层方向一致、守卫指标无回归"
    if multi_arm:
        tail += "、全方案 BH 校正后仍显著"
    reasons.append(tail + " → 判定 pass")
    return Verdict.PASS.value, reasons, ShipState.SHIP_ELIGIBLE.value


class AnalysisService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------- 创建批次 ----
    def create_run(self, experiment: Experiment, actor_email: str) -> AnalysisRun:
        if len(experiment.variants) < 2:
            raise AppError(
                codes.VALIDATION_FAILED,
                "统计判定至少需要 2 个变体（1 个共同对照 + ≥1 个处理方案）",
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
                "multi_arm": len(experiment.variants) > 2,
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
        run.arms = payload.get("arms")
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
        control = variants[0]
        treats = variants[1:]
        multi_arm = len(treats) > 1

        assignments = load_assignments(self.db, experiment.id)
        counts = variant_counts(assignments)
        grouped = _rows_by_variant(assignments)
        control_rows = grouped[control.id]

        metrics_by_id = {m.id: m for m in self.db.query(Metric).all()}
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

        # ---- 1) 全实验 SRM（曝光口径，df=k−1）----
        observed_all = [counts[v.id]["exposures"] for v in variants]
        ratio_all = [v.traffic_allocation for v in variants]
        total_ratio = sum(ratio_all) or 1.0
        srm_global = srm_test(
            observed_all,
            [r / total_ratio for r in ratio_all],
            threshold=srm_threshold,
            min_exposures=settings.min_srm_exposures,
        )
        srm_global["unit"] = "exposure"
        srm_global["variant_codes"] = [v.code for v in variants]
        srm_global["variant_names"] = [v.name for v in variants]

        # ---- 2) 逐方案：配对 SRM + 指标 + 守卫族 BH + 分层内 BH ----
        arm_pieces: list[dict[str, Any]] = []
        all_tests: list[dict[str, Any]] = []
        for treat in treats:
            treat_rows = grouped[treat.id]

            pair_ratio = [control.traffic_allocation, treat.traffic_allocation]
            pair_total = sum(pair_ratio) or 1.0
            srm_pair = srm_test(
                [counts[control.id]["exposures"], counts[treat.id]["exposures"]],
                [r / pair_total for r in pair_ratio],
                threshold=srm_threshold,
                min_exposures=settings.min_srm_exposures,
            )
            srm_pair["unit"] = "exposure"
            srm_pair["variant_codes"] = [control.code, treat.code]
            srm_pair["variant_names"] = [control.name, treat.name]

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

            guards = _evaluate_guards(guard_metrics, comparisons, alpha)
            strata = _strata_tests(primary_metric, assignments, control.id, treat.id, alpha)

            family_label = {"primary": "主指标", "guard": "守卫指标", "secondary": "辅助指标"}
            for entry in metric_payload:
                label = (
                    f"{treat.name} · {entry['metric']['name']}（{family_label[entry['family']]}）"
                    if multi_arm
                    else f"{entry['metric']['name']}（{entry['family']}）"
                )
                all_tests.append(
                    {
                        "arm_code": treat.code,
                        "arm_name": treat.name,
                        "family": entry["family"],
                        "label": label,
                        "metric_code": entry["metric"]["code"],
                        "cell_key": None,
                        "p_value": entry["stat"]["p_value"],
                    }
                )
            for cell in strata["cells"]:
                if cell.get("p_value") is None:
                    continue
                cell_key = f"{cell['segment_city']}|{cell['segment_tenure']}"
                label = (
                    f"{treat.name} · {cell['segment_city']}·{cell['segment_tenure']} 分层"
                    if multi_arm
                    else f"{cell['segment_city']}·{cell['segment_tenure']} 分层"
                )
                all_tests.append(
                    {
                        "arm_code": treat.code,
                        "arm_name": treat.name,
                        "family": "strata",
                        "label": label,
                        "metric_code": primary_metric.code,
                        "cell_key": cell_key,
                        "p_value": cell["p_value"],
                    }
                )

            arm_pieces.append(
                {
                    "treat": treat,
                    "srm_pair": srm_pair,
                    "metrics": metric_payload,
                    "guard": guards,
                    "strata": strata,
                    "comparisons": comparisons,
                    "control_n": len(control_rows),
                    "treat_n": len(treat_rows),
                    "control_exposures": counts[control.id]["exposures"],
                    "treat_exposures": counts[treat.id]["exposures"],
                }
            )

        # ---- 3) 全量 BH：两臂时与历史口径一致；多臂时跨全部方案合并一个 family ----
        full_family = adjust_family(all_tests, alpha=alpha)
        full_index: dict[tuple[str, str, str | None], dict[str, Any]] = {
            (row["arm_code"], row["family"], row.get("metric_code") if row["family"] != "strata" else row.get("cell_key")): row
            for row in all_tests
        }

        # ---- 4) 回填全量 BH 结果并逐方案判定 ----
        arm_payloads: list[dict[str, Any]] = []
        rollup: dict[str, int] = defaultdict(int)
        rollup_reasons: list[str] = []
        for piece in arm_pieces:
            treat = piece["treat"]
            for entry in piece["metrics"]:
                row = full_index[(treat.code, entry["family"], entry["metric"]["code"])]
                entry["full_bh_q_value"] = row["q_value"]
                entry["full_bh_rank"] = row["rank"]
                entry["full_bh_reject"] = row["reject"]
            for cell in piece["strata"]["cells"]:
                if cell.get("p_value") is None:
                    cell["full_bh_q_value"] = None
                    cell["full_bh_rank"] = None
                    cell["full_bh_reject"] = False
                    continue
                row = full_index[
                    (treat.code, "strata", f"{cell['segment_city']}|{cell['segment_tenure']}")
                ]
                cell["full_bh_q_value"] = row["q_value"]
                cell["full_bh_rank"] = row["rank"]
                cell["full_bh_reject"] = row["reject"]

            primary_entry = piece["comparisons"][primary_metric.id]
            primary_row = full_index[(treat.code, "primary", primary_metric.code)]
            primary_q = primary_row["q_value"]
            verdict, reasons, ship_state = _decide_arm(
                variant_code=treat.code,
                srm_global=srm_global,
                srm_pair=piece["srm_pair"],
                primary=primary_entry,
                guards=piece["guard"],
                strata=piece["strata"],
                alpha=alpha,
                min_sample=min_sample,
                control_n=piece["control_n"],
                treat_n=piece["treat_n"],
                multi_arm=multi_arm,
                primary_q=primary_q,
            )
            rollup[verdict] += 1
            pstat = primary_entry["stat"]
            lift_text = (
                "—" if pstat["lift"] is None else f"{pstat['lift'] * 100:+.2f}%"
            )
            rollup_reasons.append(
                f"方案 {treat.name}（{treat.code}）→ {verdict} / {ship_state}："
                f"主指标 lift={lift_text}"
                f"，p={pstat['p_value']}，全方案 BH q={primary_q}"
                + ("，守卫回归" if piece["guard"]["regression"] else "，守卫无回归")
            )

            arm_payloads.append(
                {
                    "variant": _variant_brief(treat),
                    "control_variant": _variant_brief(control),
                    "srm_pair": piece["srm_pair"],
                    "sample": {
                        "control_users": piece["control_n"],
                        "treat_users": piece["treat_n"],
                        "control_exposures": piece["control_exposures"],
                        "treat_exposures": piece["treat_exposures"],
                        "min_sample_per_arm": min_sample,
                    },
                    "metrics": piece["metrics"],
                    "guard": piece["guard"],
                    "strata": piece["strata"],
                    "guard_regression": bool(piece["guard"]["regression"]),
                    "bh_distorted": bool(
                        pstat["p_value"] is not None
                        and pstat["p_value"] < alpha
                        and (primary_q is None or primary_q > alpha)
                    ),
                    "primary": {
                        "metric_code": primary_metric.code,
                        "metric_name": primary_metric.name,
                        "kind": primary_metric.kind,
                        "control_value": primary_entry["control_value"],
                        "treat_value": primary_entry["treat_value"],
                        "diff": pstat["diff"],
                        "lift": pstat["lift"],
                        "lift_ci95": pstat["lift_ci95"],
                        "p_value": pstat["p_value"],
                        "q_value": primary_q,
                        "bh_reject": bool(primary_row["reject"]),
                        "bh_rank": primary_row["rank"],
                        "mde_required": pstat.get("mde_required"),
                    },
                    "verdict": verdict,
                    "verdict_reasons": reasons,
                    "ship_state": ship_state,
                }
            )

        # ---- 5) 批次级结论与锁定 ----
        locked = srm_global["verdict"] in (
            SrmVerdict.DETECTED.value,
            SrmVerdict.INSUFFICIENT.value,
        )
        if locked:
            overall_verdict = Verdict.UNREADABLE.value
            overall_reasons = [
                f"SRM 分流失衡/曝光不足：{srm_global['reason']}",
                "全实验结论锁定为「不可读」，所有方案均不可采信，需先修分流器/埋点后重跑",
            ] + rollup_reasons
        elif not multi_arm:
            overall_verdict = arm_payloads[0]["verdict"]
            overall_reasons = arm_payloads[0]["verdict_reasons"]
        else:
            # 多臂：各方案独立判定。只要存在可上线/可观察方案，就按最优可读档给总判定；
            # 全部方案都不可读时才整体 unreadable
            if rollup.get(Verdict.PASS.value):
                overall_verdict = Verdict.PASS.value
            elif rollup.get(Verdict.WARN.value):
                overall_verdict = Verdict.WARN.value
            elif rollup.get(Verdict.FAIL.value):
                overall_verdict = Verdict.FAIL.value
            else:
                overall_verdict = Verdict.UNREADABLE.value
            winners = [a["variant"]["name"] for a in arm_payloads if a["verdict"] == Verdict.PASS.value]
            overall_reasons = [
                "多臂实验：所有处理方案以同一对照臂为共同对照，全部检验合并进同一个 BH family "
                f"（m={full_family['m']}，α={alpha}）做误报控制。"
            ]
            overall_reasons.extend(rollup_reasons)
            overall_reasons.append(
                "可上线方案：" + ("、".join(winners) if winners else "无（守卫生效或校正后失真的方案均被 blocked，不能当赢家）")
            )

        payload: dict[str, Any] = {
            "srm": srm_global,
            "full_family": full_family,
            "arms": arm_payloads,
            "verdict": overall_verdict,
            "verdict_reasons": overall_reasons,
            "locked": locked,
            "multi_arm": multi_arm,
        }

        if not multi_arm:
            # 两臂：顶层字段保持历史结构，老前端/老报告无感知
            only = arm_pieces[0]
            payload.update(
                {
                    "metrics": only["metrics"],
                    "strata": only["strata"],
                    "guard": only["guard"],
                    "comparisons": all_tests,
                    "sample": {
                        "control_users": only["control_n"],
                        "treat_users": only["treat_n"],
                        "control_exposures": only["control_exposures"],
                        "treat_exposures": only["treat_exposures"],
                        "min_sample_per_arm": min_sample,
                    },
                    "variant_codes": [control.code, only["treat"].code],
                }
            )
        else:
            # 多臂：顶层只放全实验 SRM 与跨方案 BH 明细，逐方案细节在 arms
            payload.update(
                {
                    "metrics": [],
                    "strata": None,
                    "guard": None,
                    "comparisons": all_tests,
                    "sample": {
                        "total_users": sum(counts[v.id]["users"] for v in variants),
                        "total_exposures": sum(observed_all),
                        "min_sample_per_arm": min_sample,
                    },
                    "variant_codes": [v.code for v in variants],
                }
            )
        return payload
