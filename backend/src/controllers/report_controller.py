"""报告控制器：Markdown / CSV 下载 + 预览文本。"""
from __future__ import annotations

from fastapi import Response
from sqlalchemy.orm import Session

from src.models.experiment import Experiment
from src.services.report_service import ReportService


def _filename(db: Session, experiment_id: int, suffix: str) -> str:
    experiment = db.get(Experiment, experiment_id)
    code = experiment.code if experiment else f"experiment-{experiment_id}"
    return f"abcheck-{code}-report.{suffix}"


def export_markdown(experiment_id: int, db: Session, run_id: int | None = None) -> Response:
    content = ReportService(db).build_markdown(experiment_id, run_id)
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{_filename(db, experiment_id, "md")}"'
        },
    )


def export_csv(experiment_id: int, db: Session, run_id: int | None = None) -> Response:
    content = ReportService(db).build_csv(experiment_id, run_id)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{_filename(db, experiment_id, "csv")}"'
        },
    )


def preview_markdown(experiment_id: int, db: Session, run_id: int | None = None) -> dict:
    return {"markdown": ReportService(db).build_markdown(experiment_id, run_id)}
