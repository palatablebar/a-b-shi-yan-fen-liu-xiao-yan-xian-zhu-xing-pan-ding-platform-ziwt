"""worker 侧配置：复用 backend 的 Settings（同一套环境变量）。

PYTHONPATH 已包含 /app/backend，所以 backend 的 `src` 包可直接被 worker 复用，
统计口径与事务边界只维护一份。
"""
from __future__ import annotations

from src.config.settings import settings

__all__ = ["settings"]
