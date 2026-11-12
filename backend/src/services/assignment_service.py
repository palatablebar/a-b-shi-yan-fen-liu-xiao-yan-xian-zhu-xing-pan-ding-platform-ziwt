"""分桶曝光服务：变体计数、SRM 快照、分层单元格。"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.limits import MAX_ASSIGNMENTS_PER_RUN, MIN_STRATUM_PER_ARM
from src.models.assignment import Assignment
from src.models.experiment import Experiment
from src.models.variant import Variant
from src.schemas.assignment import AssignmentSummary, VariantBucket
from src.utils.errors import AppError
from src.utils.statistics import srm_test

CITY_ORDER = ["一线", "新一线", "二线"]
TENURE_ORDER = ["新客", "老客"]


def ordered_variants(experiment: Experiment) -> list[Variant]:
    """对照组在前、处理组在后：统计与展示统一按此顺序。"""
    variants = list(experiment.variants)
    if len(variants) < 2:
        raise AppError(codes.VALIDATION_FAILED, "实验至少需要 2 个变体", f"experiment={experiment.code}", 422)
    control = [v for v in variants if v.is_control]
    treat = [v for v in variants if not v.is_control]
    return (control[:1] + treat) if control else variants[:2]


def load_assignments(db: Session, experiment_id: int) -> list[Assignment]:
    rows = (
        db.query(Assignment)
        .filter(Assignment.experiment_id == experiment_id)
        .order_by(Assignment.id.asc())
        .limit(MAX_ASSIGNMENTS_PER_RUN)
        .all()
    )
    if not rows:
        raise AppError(codes.CONFLICT, "该实验还没有分桶曝光数据，无法分析", f"experiment_id={experiment_id}", 409)
    return rows


def variant_counts(assignments: list[Assignment]) -> dict[int, dict[str, int]]:
    counts: dict[int, dict[str, int]] = defaultdict(lambda: {"users": 0, "exposures": 0})
    for row in assignments:
        counts[row.variant_id]["users"] += 1
        counts[row.variant_id]["exposures"] += int(row.exposure_count or 0)
    return counts


class AssignmentService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def summary(self, experiment: Experiment) -> AssignmentSummary:
        variants = ordered_variants(experiment)
        assignments = load_assignments(self.db, experiment.id)
        counts = variant_counts(assignments)
        observed = [counts[v.id]["exposures"] for v in variants]
        expected_ratio = [v.traffic_allocation for v in variants]
        total_ratio = sum(expected_ratio) or 1.0
        expected_ratio = [r / total_ratio for r in expected_ratio]
        srm = srm_test(
            observed,
            expected_ratio,
            threshold=experiment.srm_threshold,
            min_exposures=500,
        )
        total_exposures = sum(observed)
        buckets = []
        for index, variant in enumerate(variants):
            share = observed[index] / total_exposures if total_exposures else 0.0
            buckets.append(
                VariantBucket(
                    variant_code=variant.code,
                    variant_name=variant.name,
                    is_control=variant.is_control,
                    users=counts[variant.id]["users"],
                    exposures=observed[index],
                    observed_share=round(share, 6),
                    expected_share=round(expected_ratio[index], 6),
                    deviation_pp=round((share - expected_ratio[index]) * 100, 4),
                )
            )
        return AssignmentSummary(
            experiment_id=experiment.id,
            unit="exposure",
            total_users=sum(counts[v.id]["users"] for v in variants),
            total_exposures=total_exposures,
            variants=buckets,
            srm=srm,
        )

    def segment_cells(self, experiment: Experiment) -> list[dict]:
        """按 城市 × 客群 分组，返回单元格样本量（用于分层页头部）。"""
        assignments = load_assignments(self.db, experiment.id)
        variants = ordered_variants(experiment)
        control_id, treat_id = variants[0].id, variants[1].id
        cells: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"control": 0, "treat": 0})
        for row in assignments:
            key = (row.segment_city, row.segment_tenure)
            if row.variant_id == control_id:
                cells[key]["control"] += 1
            elif row.variant_id == treat_id:
                cells[key]["treat"] += 1
        ordered_keys = [
            (city, tenure)
            for city in CITY_ORDER
            for tenure in TENURE_ORDER
            if (city, tenure) in cells
        ]
        out = []
        for city, tenure in ordered_keys:
            counts = cells[(city, tenure)]
            out.append(
                {
                    "segment_city": city,
                    "segment_tenure": tenure,
                    "control_n": counts["control"],
                    "treat_n": counts["treat"],
                    "testable": min(counts["control"], counts["treat"]) >= MIN_STRATUM_PER_ARM,
                }
            )
        return out
