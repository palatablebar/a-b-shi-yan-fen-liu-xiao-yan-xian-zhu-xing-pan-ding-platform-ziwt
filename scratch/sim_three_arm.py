"""模拟 3 臂首页文案实验 v2：确定 seed 参数与目标判定。

目标场景：
- control 原版（共同对照）
- short 短文案：主指标原始显著 + 全量 BH 后仍显著 + 守卫无回归 → pass（唯一赢家）
- coupon 领券文案：主指标原始显著但全量 BH 后失真 + 客诉守卫显著变差 → fail（不能当赢家）
"""
from __future__ import annotations

import math
import random
import sys

sys.path.insert(0, "/workspace/backend")

from src.utils.statistics import (  # noqa: E402
    benjamini_hochberg,
    srm_test,
    two_proportion_test,
    welch_test,
)


def standardized(n: int, mean: float, sd: float, seed: int) -> list[float]:
    rng = random.Random(seed)
    raw = [rng.gauss(0.0, 1.0) for _ in range(n)]
    m = sum(raw) / n
    var = sum((v - m) ** 2 for v in raw) / (n - 1)
    scale = math.sqrt(var)
    return [mean + sd * (v - m) / scale for v in raw]


def spread_flags(n: int, k: int) -> list[bool]:
    if k <= 0:
        return [False] * n
    if k >= n:
        return [True] * n
    flags = [False] * n
    for j in range(k):
        flags[(j * n) // k] = True
    return flags


N = 1200
arms = {
    "control": {"conv": 0.224, "complaint": 0.030, "ticket": 0.022, "retention": 0.318, "mean": 185.0, "seed": 1000},
    "short":   {"conv": 0.286, "complaint": 0.030, "ticket": 0.0225, "retention": 0.325, "mean": 185.0, "seed": 5000},
    "coupon":  {"conv": 0.264, "complaint": 0.055, "ticket": 0.024, "retention": 0.321, "mean": 185.0, "seed": 9000},
}

data: dict[str, dict] = {}
for key, spec in arms.items():
    data[key] = {
        "n": N,
        "conv": sum(spread_flags(N, round(spec["conv"] * N))),
        "comp": sum(spread_flags(N, round(spec["complaint"] * N))),
        "ticket": sum(spread_flags(N, round(spec["ticket"] * N))),
        "retain": sum(spread_flags(N, round(spec["retention"] * N))),
        "values": standardized(N, spec["mean"], 67.1, spec["seed"]),
    }

alpha = 0.05

# ---- SRM：34/33/33，曝光轻微偏差 ----
exposures = [2420, 2350, 2380]
srm = srm_test(exposures, [0.34, 0.33, 0.33], threshold=0.001)
print("=== overall SRM ===", {k: srm[k] for k in ("verdict", "chi2", "p_value", "observed_share")})
for pair, obs in ((("control", "short"), [2420, 2350]), (("control", "coupon"), [2420, 2380])):
    r = srm_test(obs, [0.5, 0.5], threshold=0.001)
    print(f"pair SRM {pair}: p={r['p_value']:.4f} share={r['observed_share']}")

all_p: list[tuple[str, str, float]] = []
arm_stats: dict[str, dict] = {}
for arm_key in ("short", "coupon"):
    c, t = data["control"], data[arm_key]
    conv = two_proportion_test(c["conv"], c["n"], t["conv"], t["n"], alpha)
    comp = two_proportion_test(c["comp"], c["n"], t["comp"], t["n"], alpha)
    tick = two_proportion_test(c["ticket"], c["n"], t["ticket"], t["n"], alpha)
    retain = two_proportion_test(c["retain"], c["n"], t["retain"], t["n"], alpha)
    arpu = welch_test(c["values"], t["values"], alpha)
    arm_stats[arm_key] = {"conv": conv, "comp": comp, "tick": tick, "retain": retain, "arpu": arpu}
    print(f"\n=== {arm_key} vs control ===")
    print(f"primary order_conversion x={c['conv']}/{t['conv']} lift={conv['lift']:.4f} p={conv['p_value']:.5f} mde_rel={conv['mde_required']['relative']:.4f} ci={conv['lift_ci95']}")
    print(f"guard   complaint_rate   x={c['comp']}/{t['comp']} lift={comp['lift']:.4f} p={comp['p_value']:.5f}")
    print(f"guard   ticket_rate      x={c['ticket']}/{t['ticket']} lift={tick['lift']:.4f} p={tick['p_value']:.5f}")
    print(f"second  retention_d1     x={c['retain']}/{t['retain']} lift={retain['lift']:.4f} p={retain['p_value']:.5f}")
    print(f"second  arpu             p={arpu['p_value']:.4f}")
    all_p += [
        (arm_key, "primary", conv["p_value"]),
        (arm_key, "guard", comp["p_value"]),
        (arm_key, "guard", tick["p_value"]),
        (arm_key, "secondary", retain["p_value"]),
        (arm_key, "secondary", arpu["p_value"]),
    ]
    g_adj = benjamini_hochberg([comp["p_value"], tick["p_value"]], alpha)
    print(f"guard-family BH q={[round(r['q_value'], 5) for r in g_adj]} reject={[r['reject'] for r in g_adj]}")

# ---- 分层（6 格，每格 200），主指标 ----
CELLS = [("一线", "新客"), ("一线", "老客"), ("新一线", "新客"), ("新一线", "老客"), ("二线", "新客"), ("二线", "老客")]
n_cell = N // 6
for arm_key in ("short", "coupon"):
    pvals, lifts = [], []
    for city, tenure in CELLS:
        xc = round(arms["control"]["conv"] * n_cell)
        xt = round(arms[arm_key]["conv"] * n_cell)
        st = two_proportion_test(xc, n_cell, xt, n_cell, alpha)
        pvals.append(st["p_value"])
        lifts.append(st["lift"])
        all_p.append((arm_key, f"strata-{city}{tenure}", st["p_value"]))
    adj = benjamini_hochberg(pvals, alpha)
    raw_sig = sum(1 for p in pvals if p < alpha)
    print(f"\n{arm_key} strata raw_sig={raw_sig} p={[round(p, 4) for p in pvals]}")
    print(f"{arm_key} strata BH q={[round(r['q_value'], 4) for r in adj]}")

# ---- 全量 BH：两臂全部检验一个 family ----
print("\n=== full-family BH (m = %d) ===" % len(all_p))
adj = benjamini_hochberg([p for _, _, p in all_p], alpha)
for (arm, fam, p), r in sorted(zip(all_p, adj), key=lambda x: x[1]["rank"]):
    print(f"rank={r['rank']:2d} {arm:7s} {fam:22s} p={p:.5f} q={r['q_value']:.5f} reject={r['reject']}")
