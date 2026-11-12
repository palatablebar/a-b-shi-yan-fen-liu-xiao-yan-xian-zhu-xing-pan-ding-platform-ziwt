"""元信息路由：概览与参数。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import meta_controller
from src.middlewares.rbac import require_permission
from src.models.user import User
from src.schemas.common import OverviewOut

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/overview", response_model=OverviewOut)
def overview(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("meta:read")),
) -> OverviewOut:
    return meta_controller.overview(db)


@router.get("/config")
def config(user: User = Depends(require_permission("meta:read"))) -> dict:
    return meta_controller.config_summary()
