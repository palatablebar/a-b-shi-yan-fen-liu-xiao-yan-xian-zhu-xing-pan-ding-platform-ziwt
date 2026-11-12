"""分析任务：worker 里真算 SRM / 指标检验 / 分层 BH / 守卫回归 / 结论。"""
from __future__ import annotations

from worker_src.config.celery_app import celery_app
from worker_src.core.progress import mark

from src.config.database import session_scope
from src.services.analysis_service import AnalysisService
from src.utils.logger import get_logger

logger = get_logger("abcheck.worker.analysis")


@celery_app.task(name="abcheck.run_analysis", bind=True, max_retries=0)
def run_analysis(self, run_id: int) -> dict:
    mark(run_id, "running")
    try:
        with session_scope() as db:
            verdict = AnalysisService(db).execute(run_id)
        mark(run_id, "succeeded", {"verdict": verdict})
        logger.info("run_finished run_id=%s verdict=%s", run_id, verdict)
        return {"run_id": run_id, "verdict": verdict}
    except Exception as exc:  # noqa: BLE001 - 失败已落库，任务不再重试避免雪崩
        mark(run_id, "failed", {"error": str(exc)[:200]})
        logger.warning("run_failed run_id=%s error=%s", run_id, exc)
        return {"run_id": run_id, "error": str(exc)[:400]}
