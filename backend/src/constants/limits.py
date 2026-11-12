"""业务阈值常量：与实验级覆盖参数（alpha / srm_threshold / min_sample）区分开。"""
from __future__ import annotations

# 分层下钻最少需要每臂样本数，低于此值的分层标记为样本不足、不参与 BH
MIN_STRATUM_PER_ARM = 25

# 单次分析最多扫描的分桶记录数（防超大数据集把 worker 拖死）
MAX_ASSIGNMENTS_PER_RUN = 60000

# 导出报告最多包含的分层行数
MAX_REPORT_STRATA = 24

# 审计日志默认返回条数
DEFAULT_AUDIT_LIMIT = 50
MAX_AUDIT_LIMIT = 200
