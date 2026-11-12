"""日志模板集中处：统一 key=value 风格，便于 grep 与日志仪表盘对齐。"""
from __future__ import annotations

LOG_TEMPLATES = {
    "login_ok": "login_ok email={email} role={role}",
    "login_fail": "login_fail email={email} reason={reason}",
    "run_created": "run_created run_code={run_code} experiment={experiment} actor={actor}",
    "run_finished": "run_finished run_code={run_code} verdict={verdict} srm={srm}",
    "run_failed": "run_failed run_code={run_code} error={error}",
    "decision_created": "decision_created experiment={experiment} decision={decision} reviewer={reviewer}",
    "rate_limited": "rate_limited actor={actor} key={key}",
    "seed_summary": "seed_summary {summary}",
}
