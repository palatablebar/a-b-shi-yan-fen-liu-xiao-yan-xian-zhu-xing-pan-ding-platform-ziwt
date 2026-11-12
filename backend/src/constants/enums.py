"""领域枚举（后端权威定义）。

前端副本：frontend/src/constants/enums.ts —— 两处必须一致，README 列出全部出现位置。
"""
from __future__ import annotations

from enum import Enum


class MetricKind(str, Enum):
    RATIO = "ratio"          # 比例指标：转化/客诉等
    MEAN = "mean"            # 均值指标：人均 GMV 等


class MetricRole(str, Enum):
    PRIMARY = "primary"      # 主指标
    GUARD = "guard"          # 守卫指标：显著变差则结论降级
    SECONDARY = "secondary"  # 辅助指标


class MetricDirection(str, Enum):
    INCREASE_GOOD = "increase_good"
    DECREASE_GOOD = "decrease_good"


class ExperimentStatus(str, Enum):
    DRAFT = "draft"          # 草稿：尚未开跑
    RUNNING = "running"      # 进行中：等待分析
    ANALYZING = "analyzing"  # 分析中/待处置（如 SRM 锁定）
    DECIDED = "decided"      # 已裁决
    ARCHIVED = "archived"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SrmVerdict(str, Enum):
    OK = "ok"                    # 分流正常
    DETECTED = "detected"        # SRM：分流失衡
    INSUFFICIENT = "insufficient"  # 曝光量不足


class Verdict(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    UNREADABLE = "unreadable"


class DecisionKind(str, Enum):
    SHIP = "ship"        # 上线
    KILL = "kill"        # 下线
    CONTINUE = "continue"  # 继续观察


class GuardState(str, Enum):
    OK = "ok"
    IMPROVED = "improved"
    REGRESSION = "regression"
    INCONCLUSIVE = "inconclusive"
