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

    # ------------------------------------------------------------------ CSV ----
    def build_csv(self, experiment_id: int, run_id: int | None = None) -> str:
        experiment, run, _decision = self._load(experiment_id, run_id)
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
