"""数值展示口径：百分比、pp、p 值、样本量。后端算、后端格式化，避免前端各自拍。"""
from __future__ import annotations


def pct(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.{digits}f}%"


def pp(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value * 100:+.{digits}f}pp"


def p_value(value: float | None) -> str:
    if value is None:
        return "—"
    if value < 0.0001:
        return "<0.0001"
    return f"{value:.4f}"


def sample(n: int) -> str:
    return f"{n:,}"
