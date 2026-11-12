"""报告导出路由：Markdown / CSV 下载 + 预览（全角色只读可用）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import report_controller
from src.middlewares.rbac import require_permission
from src.models.user import User

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/experiments/{experiment_id}.md")
def export_markdown(
    experiment_id: int,
    run_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports:export")),
) -> Response:
    return report_controller.export_markdown(experiment_id, db, run_id)


@router.get("/experiments/{experiment_id}.csv")
def export_csv(
    experiment_id: int,
    run_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports:export")),
) -> Response:
    return report_controller.export_csv(experiment_id, db, run_id)


@router.get("/experiments/{experiment_id}/preview")
def preview_markdown(
    experiment_id: int,
    run_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("reports:export")),
) -> dict:
    return report_controller.preview_markdown(experiment_id, db, run_id)
