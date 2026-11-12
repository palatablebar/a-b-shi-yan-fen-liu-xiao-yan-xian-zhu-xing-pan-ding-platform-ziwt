"""backend 侧任务声明：只声明任务名，真正实现注册在 worker 容器。"""
from __future__ import annotations

from src.config.celery_app import TASK_ANALYSIS_RUN, celery_app


@celery_app.task(name=TASK_ANALYSIS_RUN, bind=True, max_retries=1)
def run_analysis(self, run_id: int) -> dict:
    """占位实现：worker 容器里同名任务会覆盖实际执行逻辑。"""
    return {"run_id": run_id, "dispatched": True}
