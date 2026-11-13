"""报告导出：Markdown 实验报告 + CSV 指标对比明细（后端生成，前端只下载）。"""
from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.enums import RunStatus
from src.models.analysis_run import AnalysisRun
from src.models.decision import Decision
from src.models.experiment import Experiment
from src.utils.errors import AppError

VERDICT_LABELS = {
    "pass": "通过（pass）",
    "warn": "警告（warn）",
    "fail": "不通过（fail）",
    "unreadable": "不可读（unreadable）",
}
SRM_LABELS = {"ok": "分流正常", "detected": "SRM 失衡", "insufficient": "曝光不足"}
ROLE_LABELS = {"primary": "主指标", "guard": "守卫指标", "secondary": "辅助指标"}
DECISION_LABELS = {"ship": "上线", "kill": "下线", "continue": "继续观察"}
SHIP_STATE_LABELS = {
    "ship_eligible": "可上线（唯一赢家）",
    "watch_only": "仅可继续观察",
    "blocked": "禁止上线（blocked）",
}


def _fmt_pct(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value * 100:.{digits}f}%"


def _fmt_num(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


class ReportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _load(self, experiment_id: int, run_id: int | None) -> tuple[Experiment, AnalysisRun, Decision | None]:
        experiment = self.db.get(Experiment, experiment_id)
        if experiment is None:
            raise AppError(codes.NOT_FOUND, "实验不存在", f"experiment_id={experiment_id}", 404)
        query = (
            self.db.query(AnalysisRun)
            .filter(
                AnalysisRun.experiment_id == experiment_id,
                AnalysisRun.status == RunStatus.SUCCEEDED.value,
            )
        )
        if run_id is not None:
            query = query.filter(AnalysisRun.id == run_id)
        run = query.order_by(AnalysisRun.id.desc()).first()
        if run is None:
            raise AppError(codes.CONFLICT, "该实验还没有可导出的成功批次", None, 409)
        decision = (
            self.db.query(Decision)
            .filter(Decision.experiment_id == experiment_id)
            .order_by(Decision.id.desc())
            .first()
        )
        return experiment, run, decision

    # ------------------------------------------------------------- Markdown ----
    def build_markdown(self, experiment_id: int, run_id: int | None = None) -> str:
        experiment, run, decision = self._load(experiment_id, run_id)
        if run.arms and (run.params or {}).get("multi_arm"):
            return self._build_multi_arm_markdown(experiment, run, decision)
        return self._build_two_arm_markdown(experiment, run, decision)

    def _build_two_arm_markdown(self, experiment: Experiment, run: AnalysisRun, decision: Decision | None) -> str:
        srm = run.srm or {}
        metrics = run.metrics or []
        strata = run.strata or {}
        guard = run.guard or {}
        lines: list[str] = []
        lines.append(f"# 实验报告 · {experiment.code} {experiment.name}")
        lines.append("")
        lines.append(f"> 青柚出行 · 增长分析组 ｜ 分析批次 `{run.run_code}` ｜ 生成时间 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        lines.append("## 一、实验信息")
        lines.append("")
        lines.append("| 项 | 值 |")
        lines.append("| --- | --- |")
        lines.append(f"| 实验编号 | `{experiment.code}` |")
        lines.append(f"| 实验名称 | {experiment.name} |")
        lines.append(f"| 负责人 | {experiment.owner_name} |")
        lines.append(f"| 状态 | {experiment.status} |")
        lines.append(
            f"| 窗口 | {experiment.start_date or '—'} ~ {experiment.end_date or '—'} |"
        )
        lines.append(
            f"| 主指标 | {experiment.primary_metric.name if experiment.primary_metric else '—'} |"
        )
        guard_names = [
            entry["metric"]["name"] for entry in metrics if entry.get("family") == "guard"
        ]
        lines.append(f"| 守卫指标 | {'、'.join(guard_names) or '—'} |")
        lines.append(f"| 假设 | {experiment.hypothesis or '—'} |")
        lines.append("")
        lines.append("## 二、分流校验（SRM，曝光次数口径）")
        lines.append("")
        lines.append("| 项 | 值 |")
        lines.append("| --- | --- |")
        lines.append(f"| 判定 | {SRM_LABELS.get(srm.get('verdict', ''), srm.get('verdict', '—'))} |")
        lines.append(f"| 曝光总数 | {srm.get('total', '—')} |")
        lines.append(f"| 观测占比 | {' / '.join(_fmt_pct(v) for v in (srm.get('observed_share') or []))} |")
        lines.append(f"| 期望占比 | {' / '.join(_fmt_pct(v) for v in (srm.get('expected_share') or []))} |")
        lines.append(f"| χ² / df | {srm.get('chi2', '—')} / {srm.get('df', '—')} |")
        lines.append(f"| p 值 | {srm.get('p_value', '—')} |")
        lines.append(f"| 结论 | {srm.get('reason', '—')} |")
        lines.append("")
        lines.append("## 三、指标对比（用户级样本）")
        lines.append("")
        lines.append("| 指标 | 角色 | 口径 | 对照组 | 实验组 | 差值 | lift | lift 95% CI | p 值 | MDE(80%) |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for entry in metrics:
            stat = entry["stat"]
            metric = entry["metric"]
            if entry["kind"] == "ratio":
                control = _fmt_pct(entry["control_value"])
                treat = _fmt_pct(entry["treat_value"])
                diff = f"{stat['diff'] * 100:+.3f}pp"
                mde = _fmt_pct((stat.get("mde_required") or {}).get("relative"))
            else:
                control = _fmt_num(entry["control_value"])
                treat = _fmt_num(entry["treat_value"])
                diff = f"{stat['diff']:+.3f}"
                mde = _fmt_pct((stat.get("mde_required") or {}).get("relative"))
            ci = stat.get("lift_ci95") or [None, None]
            lines.append(
                f"| {metric['name']} | {ROLE_LABELS.get(entry['family'], entry['family'])} | "
                f"{'比例' if entry['kind'] == 'ratio' else '均值'} | {control} | {treat} | {diff} | "
                f"{_fmt_pct(stat.get('lift'))} | [{_fmt_pct(ci[0])}, {_fmt_pct(ci[1])}] | "
                f"{stat.get('p_value')} | {mde} |"
            )
        lines.append("")
        lines.append("## 四、分层分析（城市 × 客群，BH 校正）")
        lines.append("")
        summary = strata.get("summary") or {}
        lines.append(
            f"分层单元格 {summary.get('cells_total', 0)} 个，可检验 {summary.get('cells_tested', 0)} 个；"
            f"原始显著 {summary.get('raw_significant', 0)} 个，BH 校正后显著 {summary.get('bh_significant', 0)} 个；"
            f"校正后不显著 {summary.get('flagged_non_significant', 0)} 个。"
        )
        lines.append("")
        lines.append("| 分层 | 对照 n | 实验 n | 对照组 | 实验组 | lift | p 值 | q 值(BH) | 判定 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for cell in strata.get("cells", []):
            verdict_text = "不可检验"
            if cell.get("p_value") is not None:
                if cell.get("significant_bh"):
                    verdict_text = "BH 后显著"
                elif cell.get("significant_raw"):
                    verdict_text = "原始显著 / BH 不显著"
                else:
                    verdict_text = "不显著"
            control = (
                _fmt_pct(cell.get("control_value"))
                if (experiment.primary_metric and experiment.primary_metric.kind == "ratio")
                else _fmt_num(cell.get("control_value"))
            )
            treat = (
                _fmt_pct(cell.get("treat_value"))
                if (experiment.primary_metric and experiment.primary_metric.kind == "ratio")
                else _fmt_num(cell.get("treat_value"))
            )
            lines.append(
                f"| {cell['segment_city']}·{cell['segment_tenure']} | {cell['control_n']} | "
                f"{cell['treat_n']} | {control} | {treat} | {_fmt_pct(cell.get('lift'))} | "
                f"{cell.get('p_value', '—')} | {cell.get('q_value', '—')} | {verdict_text} |"
            )
        lines.append("")
        lines.append("## 五、守卫指标")
        lines.append("")
        for check in guard.get("checks", []):
            lines.append(
                f"- **{check['name']}**：{check['state']}，lift {_fmt_pct(check.get('lift'))}，"
                f"p={check.get('p_value')}；{check.get('note')}"
            )
        if not guard.get("checks"):
            lines.append("- 本实验未配置守卫指标")
        lines.append("")
        lines.append("## 六、结论与决策")
        lines.append("")
        lines.append(f"- 结论：**{VERDICT_LABELS.get(run.verdict or '', run.verdict or '—')}**")
        for reason in run.verdict_reasons or []:
            lines.append(f"- 判定依据：{reason}")
        if decision is not None:
            lines.append(
                f"- 决策：**{DECISION_LABELS.get(decision.decision, decision.decision)}**"
                f"（复核人 {decision.reviewer}，{decision.created_at.strftime('%Y-%m-%d %H:%M')}）"
            )
            lines.append(f"- 理由：{decision.rationale}")
            lines.append(f"- 守卫指标已确认：{'是' if decision.guard_ack else '否'}")
        else:
            lines.append("- 决策：尚未落决策记录")
        lines.append("")
        lines.append("---")
        lines.append(
            "口径注：SRM 以曝光次数校验；指标以用户级样本检验；"
            "比例指标用两比例 z 检验（合并方差），均值指标用 Welch t；"
            "多重比较用 Benjamini–Hochberg FDR；MDE 按 80% 功效、双侧 α 计算。"
        )
        return "\n".join(lines) + "\n"

    # ------------------------------------------------- Markdown · 多臂（共同对照）----
    def _build_multi_arm_markdown(
        self, experiment: Experiment, run: AnalysisRun, decision: Decision | None
    ) -> str:
        srm = run.srm or {}
        arms = run.arms or []
        lines: list[str] = []
        lines.append(f"# 实验报告 · {experiment.code} {experiment.name}（多方案共同对照）")
        lines.append("")
        lines.append(f"> 青柚出行 · 增长分析组 ｜ 分析批次 `{run.run_code}` ｜ 生成时间 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        lines.append("## 一、实验信息")
        lines.append("")
        lines.append("| 项 | 值 |")
        lines.append("| --- | --- |")
        lines.append(f"| 实验编号 | `{experiment.code}` |")
        lines.append(f"| 实验名称 | {experiment.name} |")
        lines.append(f"| 负责人 | {experiment.owner_name} |")
        lines.append(f"| 状态 | {experiment.status} |")
        lines.append(f"| 窗口 | {experiment.start_date or '—'} ~ {experiment.end_date or '—'} |")
        lines.append(
            f"| 主指标 | {experiment.primary_metric.name if experiment.primary_metric else '—'} |"
        )
        guard_names = [
            check["name"] for arm in arms for check in (arm.get("guard") or {}).get("checks", [])
        ]
        lines.append(f"| 守卫指标 | {'、'.join(dict.fromkeys(guard_names)) or '—'} |")
        lines.append(f"| 假设 | {experiment.hypothesis or '—'} |")
        lines.append("")

        lines.append("## 二、分流校验（SRM，曝光次数口径）")
        lines.append("")
        lines.append("### 2.1 全实验分流（df = 变体数 − 1）")
        lines.append("")
        lines.append("| 项 | 值 |")
        lines.append("| --- | --- |")
        lines.append(f"| 判定 | {SRM_LABELS.get(srm.get('verdict', ''), srm.get('verdict', '—'))} |")
        lines.append(f"| 曝光总数 | {srm.get('total', '—')} |")
        lines.append(f"| 观测占比 | {' / '.join(_fmt_pct(v) for v in (srm.get('observed_share') or []))} |")
        lines.append(f"| 期望占比 | {' / '.join(_fmt_pct(v) for v in (srm.get('expected_share') or []))} |")
        lines.append(f"| χ² / df | {srm.get('chi2', '—')} / {srm.get('df', '—')} |")
        lines.append(f"| p 值 | {srm.get('p_value', '—')} |")
        lines.append("")
        lines.append("### 2.2 逐方案配对 SRM（共同对照 vs 处理方案）")
        lines.append("")
        lines.append("| 方案 | 对照变体 | 对照曝光 | 方案曝光 | 观测占比（对照/方案） | 期望配比 | χ² | p 值 | 判定 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for arm in arms:
            pair = arm.get("srm_pair") or {}
            share = pair.get("observed_share") or [None, None]
            expect = pair.get("expected_share") or [None, None]
            lines.append(
                f"| {arm['variant']['name']}（{arm['variant']['code']}） | "
                f"{arm['control_variant']['name']} | {arm['sample']['control_exposures']} | "
                f"{arm['sample']['treat_exposures']} | "
                f"{_fmt_pct(share[0])} / {_fmt_pct(share[1])} | "
                f"{_fmt_pct(expect[0])} / {_fmt_pct(expect[1])} | "
                f"{pair.get('chi2', '—')} | {pair.get('p_value', '—')} | "
                f"{SRM_LABELS.get(pair.get('verdict', ''), pair.get('verdict', '—'))} |"
            )
        lines.append("")

        lines.append("## 三、方案对账与主指标（共同对照基准）")
        lines.append("")
        lines.append(
            "| 方案 | 对照用户 | 方案用户 | 主指标对照 | 主指标方案 | lift | lift 95% CI | 原始 p | 全方案 BH q | BH 后显著 | 结论 | 可上线状态 |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for arm in arms:
            p = arm["primary"]
            ci = p.get("lift_ci95") or [None, None]
            kind = p.get("kind")
            cv = _fmt_pct(p["control_value"]) if kind == "ratio" else _fmt_num(p["control_value"])
            tv = _fmt_pct(p["treat_value"]) if kind == "ratio" else _fmt_num(p["treat_value"])
            lines.append(
                f"| {arm['variant']['name']}（{arm['variant']['code']}） | "
                f"{arm['sample']['control_users']} | {arm['sample']['treat_users']} | "
                f"{cv} | {tv} | {_fmt_pct(p.get('lift'))} | "
                f"[{_fmt_pct(ci[0])}, {_fmt_pct(ci[1])}] | {p.get('p_value')} | "
                f"{p.get('q_value')} | {'是' if p.get('bh_reject') else '否'} | "
                f"{VERDICT_LABELS.get(arm['verdict'], arm['verdict'])} | "
                f"{SHIP_STATE_LABELS.get(arm['ship_state'], arm['ship_state'])} |"
            )
        lines.append("")

        lines.append("## 四、守卫指标（逐方案，守卫族内 BH）")
        lines.append("")
        for arm in arms:
            lines.append(f"### {arm['variant']['name']}（{arm['variant']['code']}）")
            lines.append("")
            for check in (arm.get("guard") or {}).get("checks", []):
                lines.append(
                    f"- **{check['name']}**：{check['state']}，lift {_fmt_pct(check.get('lift'))}，"
                    f"p={check.get('p_value')}，q={check.get('q_value')}；{check.get('note')}"
                )
            lines.append("")

        lines.append("## 五、分层分析（城市 × 客群，逐方案分层内 BH）")
        lines.append("")
        for arm in arms:
            strata = arm.get("strata") or {}
            summary = strata.get("summary") or {}
            lines.append(
                f"### {arm['variant']['name']}（{arm['variant']['code']}）："
                f"单元格 {summary.get('cells_total', 0)} / 可检验 {summary.get('cells_tested', 0)} / "
                f"原始显著 {summary.get('raw_significant', 0)} / 分层 BH 后显著 {summary.get('bh_significant', 0)}"
            )
            lines.append("")
            lines.append("| 分层 | 对照 n | 方案 n | lift | 原始 p | 分层内 q | 全方案 q | 判定 |")
            lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
            for cell in strata.get("cells", []):
                if cell.get("p_value") is None:
                    verdict_text = "不可检验"
                elif cell.get("significant_bh"):
                    verdict_text = "分层 BH 后显著"
                elif cell.get("significant_raw"):
                    verdict_text = "原始显著 / 分层 BH 不显著"
                else:
                    verdict_text = "不显著"
                lines.append(
                    f"| {cell['segment_city']}·{cell['segment_tenure']} | {cell['control_n']} | "
                    f"{cell['treat_n']} | {_fmt_pct(cell.get('lift'))} | {cell.get('p_value', '—')} | "
                    f"{cell.get('q_value', '—')} | {cell.get('full_bh_q_value', '—')} | {verdict_text} |"
                )
            lines.append("")

        lines.append("## 六、全方案统一误报控制（所有检验一个 BH family）")
        lines.append("")
        family = run.comparisons or []
        lines.append(
            f"合并检验 m={len(family)} 项（全部处理方案的主/守卫/辅助/分层检验），"
            "统一做 Benjamini–Hochberg FDR；任一方案只在该族校正后仍显著才可作为赢家。"
        )
        lines.append("")
        lines.append("| 方案 | 检验项 | 族 | 原始 p | 全方案 q | 秩 | BH 后显著 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for row in family:
            lines.append(
                f"| {row.get('arm_name', '—')} | {row.get('label')} | {row.get('family')} | "
                f"{row.get('p_value')} | {row.get('q_value')} | {row.get('rank')} | "
                f"{'显著' if row.get('reject') else '不显著'} |"
            )
        lines.append("")

        lines.append("## 七、结论与决策")
        lines.append("")
        lines.append(f"- 批次总判定：**{VERDICT_LABELS.get(run.verdict or '', run.verdict or '—')}**")
        for arm in arms:
            lines.append(
                f"- 方案 {arm['variant']['name']}（{arm['variant']['code']}）："
                f"**{VERDICT_LABELS.get(arm['verdict'], arm['verdict'])}** / "
                f"{SHIP_STATE_LABELS.get(arm['ship_state'], arm['ship_state'])}"
            )
            for reason in arm.get("verdict_reasons") or []:
                lines.append(f"  - 判定依据：{reason}")
        if decision is not None:
            lines.append(
                f"- 决策：**{DECISION_LABELS.get(decision.decision, decision.decision)}**"
                f"（复核人 {decision.reviewer}，{decision.created_at.strftime('%Y-%m-%d %H:%M')}）"
            )
            lines.append(f"- 理由：{decision.rationale}")
            lines.append(f"- 守卫指标已确认：{'是' if decision.guard_ack else '否'}")
        else:
            lines.append("- 决策：尚未落决策记录")
        lines.append("")
        lines.append("---")
        lines.append(
            "口径注：SRM 以曝光次数校验（全实验 + 共同对照配对两档）；指标以用户级样本检验；"
            "比例指标用两比例 z 检验（合并方差），均值指标用 Welch t；"
            "分层内/守卫族内各做一次 BH，所有方案的全部检验再合并做一次全量 BH FDR；"
            "守卫生效或全量校正后失真的方案 ship_state=blocked，不能被当成赢家。"
        )
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------ CSV ----
    def build_csv(self, experiment_id: int, run_id: int | None = None) -> str:
        experiment, run, _decision = self._load(experiment_id, run_id)
        if run.arms and (run.params or {}).get("multi_arm"):
            return self._build_multi_arm_csv(experiment, run)
        return self._build_two_arm_csv(experiment, run)

    def _build_two_arm_csv(self, experiment: Experiment, run: AnalysisRun) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "experiment_code",
                "run_code",
                "metric_code",
                "metric_name",
                "family",
                "kind",
                "test",
                "direction",
                "control_n",
                "treat_n",
                "control_value",
                "treat_value",
                "diff",
                "lift",
                "lift_ci95_low",
                "lift_ci95_high",
                "p_value",
                "mde_required_relative",
                "srm_verdict",
                "verdict",
            ]
        )
        srm = run.srm or {}
        for entry in run.metrics or []:
            stat = entry["stat"]
            ci = stat.get("lift_ci95") or [None, None]
            writer.writerow(
                [
                    experiment.code,
                    run.run_code,
                    entry["metric"]["code"],
                    entry["metric"]["name"],
                    entry["family"],
                    entry["kind"],
                    stat.get("test"),
                    entry["direction"],
                    stat.get("control_n"),
                    stat.get("treat_n"),
                    entry.get("control_value"),
                    entry.get("treat_value"),
                    stat.get("diff"),
                    stat.get("lift"),
                    ci[0],
                    ci[1],
                    stat.get("p_value"),
                    (stat.get("mde_required") or {}).get("relative"),
                    srm.get("verdict"),
                    run.verdict,
                ]
            )
        return buffer.getvalue()

    def _build_multi_arm_csv(self, experiment: Experiment, run: AnalysisRun) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "experiment_code",
                "run_code",
                "arm_code",
                "arm_name",
                "control_variant_code",
                "metric_code",
                "metric_name",
                "family",
                "kind",
                "control_n",
                "treat_n",
                "control_value",
                "treat_value",
                "diff",
                "lift",
                "lift_ci95_low",
                "lift_ci95_high",
                "p_value",
                "full_bh_q_value",
                "full_bh_reject",
                "mde_required_relative",
                "pair_srm_verdict",
                "pair_srm_p_value",
                "guard_regression",
                "bh_distorted",
                "arm_verdict",
                "ship_state",
            ]
        )
        for arm in run.arms or []:
            pair = arm.get("srm_pair") or {}
            for entry in arm.get("metrics") or []:
                stat = entry["stat"]
                ci = stat.get("lift_ci95") or [None, None]
                writer.writerow(
                    [
                        experiment.code,
                        run.run_code,
                        arm["variant"]["code"],
                        arm["variant"]["name"],
                        arm["control_variant"]["code"],
                        entry["metric"]["code"],
                        entry["metric"]["name"],
                        entry["family"],
                        entry["kind"],
                        stat.get("control_n"),
                        stat.get("treat_n"),
                        entry.get("control_value"),
                        entry.get("treat_value"),
                        stat.get("diff"),
                        stat.get("lift"),
                        ci[0],
                        ci[1],
                        stat.get("p_value"),
                        entry.get("full_bh_q_value"),
                        entry.get("full_bh_reject"),
                        (stat.get("mde_required") or {}).get("relative"),
                        pair.get("verdict"),
                        pair.get("p_value"),
                        arm.get("guard_regression"),
                        arm.get("bh_distorted"),
                        arm.get("verdict"),
                        arm.get("ship_state"),
                    ]
                )
        return buffer.getvalue()
