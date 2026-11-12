"""多重比较族管理：把 family 的 p 值批量交给 BH，并回填 q 值与显著性标记。"""
from __future__ import annotations

from typing import Iterable

from src.utils.statistics import benjamini_hochberg


def adjust_family(rows: Iterable[dict], p_key: str = "p_value", alpha: float = 0.05) -> dict:
    """对 rows 中每个 dict 的 p_key 做 BH 校正，原地写入 q_value/reject。

    返回 family 级汇总（m、alpha、method、最小 q）。
    """
    rows = list(rows)
    usable = [row for row in rows if row.get(p_key) is not None]
    adjusted = benjamini_hochberg([row[p_key] for row in usable], alpha=alpha)
    for row, adj in zip(usable, adjusted):
        row["q_value"] = adj["q_value"]
        row["rank"] = adj["rank"]
        row["reject"] = adj["reject"]
    q_values = [row["q_value"] for row in usable]
    return {
        "method": "benjamini_hochberg",
        "alpha": alpha,
        "m": len(usable),
        "min_q": min(q_values) if q_values else None,
        "rejected": sum(1 for row in usable if row.get("reject")),
    }
