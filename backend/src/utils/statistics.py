"""统计核（只用 Python 标准库 math，容器离线可复现）。

覆盖：
1) 分流校验 SRM：卡方拟合优度  χ² = Σ (O−E)²/E，df = k−1
2) 比例指标：两比例 z 检验（合并方差）  z = (p_t − p_c) / sqrt(p̄(1−p̄)(1/n_c+1/n_t))
3) 均值指标：Welch t 检验（不假定等方差）
4) 效应量：lift / lift 95% CI / p 值 / MDE（80% 功效）
5) 多重比较：Benjamini–Hochberg FDR 校正（q 值单调化）

所有分布函数均为自实现（erf / 正则不完全 Gamma / 正则不完全 Beta），
不依赖 scipy，保证 seed 与分析在容器里逐位可复现。
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

Z_975 = 1.959963984540054  # Φ⁻¹(0.975)
Z_80 = 0.8416212335729143  # Φ⁻¹(0.80)


# ---------------------------------------------------------------- 基础分布 ----
def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def normal_sf(x: float) -> float:
    return 0.5 * math.erfc(x / math.sqrt(2.0))


def z_ppf(p: float) -> float:
    """标准正态分位数（Acklam 有理逼近，精度 ~1e-9）。"""
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in (0,1)")
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    ]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (
        ((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1
    )


def _gammainc_lower(a: float, x: float) -> float:
    """正则化下不完全 Gamma P(a, x)（级数）。"""
    if x <= 0.0:
        return 0.0
    term = 1.0 / a
    total = term
    ap = a
    for _ in range(2000):
        ap += 1.0
        term *= x / ap
        total += term
        if abs(term) < abs(total) * 1e-16:
            break
    return total * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gammainc_upper(a: float, x: float) -> float:
    """正则化上不完全 Gamma Q(a, x)（Lentz 连分数）。"""
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 2000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def chi2_sf(x: float, df: int) -> float:
    """卡方分布上尾概率 P(χ²_df > x)。"""
    if x <= 0:
        return 1.0
    if df <= 0:
        return 1.0
    a = df / 2.0
    z = x / 2.0
    if z < a + 1.0:
        return 1.0 - _gammainc_lower(a, z)
    return _gammainc_upper(a, z)


def _betacf(a: float, b: float, x: float) -> float:
    tiny = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 2000):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def betainc_regularized(a: float, b: float, x: float) -> float:
    """正则化不完全 Beta 函数 I_x(a, b)。"""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_sf(t: float, df: float) -> float:
    """Student t 上尾概率 P(T_df > t)。"""
    if df <= 0:
        return float("nan")
    x = df / (df + t * t)
    tail = 0.5 * betainc_regularized(df / 2.0, 0.5, x)
    return tail if t >= 0 else 1.0 - tail


def t_cdf(t: float, df: float) -> float:
    return 1.0 - t_sf(t, df)


def t_ppf(p: float, df: float) -> float:
    """t 分位数（对 CDF 二分，区间 [0, 200]，精度 1e-10）。"""
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in (0,1)")
    if p < 0.5:
        return -t_ppf(1.0 - p, df)
    lo, hi = 0.0, 200.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-10:
            break
    return (lo + hi) / 2.0


# ---------------------------------------------------------------- 基础统计 ----
def series_mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def series_stdev(values: Sequence[float]) -> float:
    """样本标准差（n−1）。"""
    n = len(values)
    if n < 2:
        return 0.0
    m = series_mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (n - 1))


def round_sig(value: float | None, digits: int = 8) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value):
        return None
    return round(value, digits)


# ---------------------------------------------------------- 比例指标 z 检验 ----
def two_proportion_test(
    control_success: int,
    control_n: int,
    treat_success: int,
    treat_n: int,
    alpha: float = 0.05,
) -> dict[str, object]:
    """两比例 z 检验（合并方差）。返回 lift / lift_ci95 / p_value / mde_required。"""
    p_c = control_success / control_n
    p_t = treat_success / treat_n
    p_pool = (control_success + treat_success) / (control_n + treat_n)
    se_pool = math.sqrt(p_pool * (1 - p_pool) * (1 / control_n + 1 / treat_n))
    diff = p_t - p_c
    z = diff / se_pool if se_pool > 0 else 0.0
    p_value = 2.0 * normal_sf(abs(z))

    se_unpooled = math.sqrt(
        p_c * (1 - p_c) / control_n + p_t * (1 - p_t) / treat_n
    )
    z_crit = z_ppf(1 - alpha / 2)
    ci_low = diff - z_crit * se_unpooled
    ci_high = diff + z_crit * se_unpooled
    lift = diff / p_c if p_c else None
    lift_ci = (
        [ci_low / p_c, ci_high / p_c] if p_c else None
    )
    mde_abs = (z_crit + z_ppf(0.8)) * math.sqrt(
        p_c * (1 - p_c) * (1 / control_n + 1 / treat_n)
    )
    return {
        "test": "two_proportion_z",
        "control_n": control_n,
        "control_success": control_success,
        "control_rate": round_sig(p_c),
        "treat_n": treat_n,
        "treat_success": treat_success,
        "treat_rate": round_sig(p_t),
        "pooled_rate": round_sig(p_pool),
        "diff": round_sig(diff),
        "z": round_sig(z),
        "p_value": round_sig(p_value, 10),
        "lift": round_sig(lift, 8),
        "lift_ci95": [round_sig(lift_ci[0], 8), round_sig(lift_ci[1], 8)] if lift_ci else None,
        "mde_required": {
            "alpha": alpha,
            "power": 0.8,
            "absolute": round_sig(mde_abs, 8),
            "relative": round_sig(mde_abs / p_c, 8) if p_c else None,
        },
    }


# ------------------------------------------------------------ 均值指标 Welch ----
def welch_test(
    control_values: Sequence[float],
    treat_values: Sequence[float],
    alpha: float = 0.05,
) -> dict[str, object]:
    """Welch t 检验（不假定等方差）。返回 lift / lift_ci95 / p_value / mde_required。"""
    n_c = len(control_values)
    n_t = len(treat_values)
    m_c = series_mean(control_values)
    m_t = series_mean(treat_values)
    v_c = series_stdev(control_values) ** 2
    v_t = series_stdev(treat_values) ** 2
    se2_c = v_c / n_c
    se2_t = v_t / n_t
    se = math.sqrt(se2_c + se2_t)
    diff = m_t - m_c
    t = diff / se if se > 0 else 0.0
    df = (se2_c + se2_t) ** 2 / (
        (se2_c**2) / (n_c - 1) + (se2_t**2) / (n_t - 1)
    ) if (se2_c + se2_t) > 0 else float(n_c + n_t - 2)
    p_value = 2.0 * t_sf(abs(t), df)
    t_crit = t_ppf(1 - alpha / 2, df)
    ci_low = diff - t_crit * se
    ci_high = diff + t_crit * se
    lift = diff / m_c if m_c else None
    lift_ci = [ci_low / m_c, ci_high / m_c] if m_c else None
    mde_abs = (z_ppf(1 - alpha / 2) + z_ppf(0.8)) * se
    return {
        "test": "welch_t",
        "control_n": n_c,
        "control_mean": round_sig(m_c, 6),
        "control_sd": round_sig(math.sqrt(v_c), 6),
        "treat_n": n_t,
        "treat_mean": round_sig(m_t, 6),
        "treat_sd": round_sig(math.sqrt(v_t), 6),
        "diff": round_sig(diff, 6),
        "t": round_sig(t, 6),
        "df": round_sig(df, 4),
        "p_value": round_sig(p_value, 10),
        "lift": round_sig(lift, 8),
        "lift_ci95": [round_sig(lift_ci[0], 8), round_sig(lift_ci[1], 8)] if lift_ci else None,
        "mde_required": {
            "alpha": alpha,
            "power": 0.8,
            "absolute": round_sig(mde_abs, 6),
            "relative": round_sig(mde_abs / m_c, 8) if m_c else None,
        },
    }


# --------------------------------------------------------------- SRM 卡方 ----
def srm_test(
    observed: Sequence[int],
    expected_ratio: Sequence[float],
    threshold: float = 0.001,
    min_exposures: int = 500,
) -> dict[str, object]:
    """卡方拟合优度分流校验：χ² = Σ(O−E)²/E，df = k−1。"""
    total = sum(observed)
    if total < min_exposures:
        return {
            "verdict": "insufficient",
            "total": total,
            "min_exposures": min_exposures,
            "observed": list(observed),
            "expected": None,
            "observed_share": None,
            "expected_share": [round(r, 6) for r in expected_ratio],
            "chi2": None,
            "df": None,
            "p_value": None,
            "threshold": threshold,
            "reason": f"曝光量 {total} 低于校验下限 {min_exposures}，无法判定分流",
        }
    expected = [total * r for r in expected_ratio]
    chi2 = sum((o - e) ** 2 / e for o, e in zip(observed, expected) if e > 0)
    df = len(observed) - 1
    p_value = chi2_sf(chi2, df)
    verdict = "detected" if p_value < threshold else "ok"
    reason = (
        f"分流比例失衡：χ²={chi2:.3f}, df={df}, p={p_value:.6f} < 阈值 {threshold}"
        if verdict == "detected"
        else f"分流比例在容差内：χ²={chi2:.3f}, df={df}, p={p_value:.4f} ≥ 阈值 {threshold}"
    )
    return {
        "verdict": verdict,
        "total": total,
        "min_exposures": min_exposures,
        "observed": list(observed),
        "expected": [round(e, 3) for e in expected],
        "observed_share": [round(o / total, 6) for o in observed],
        "expected_share": [round(r, 6) for r in expected_ratio],
        "chi2": round(chi2, 4),
        "df": df,
        "p_value": round(p_value, 10),
        "threshold": threshold,
        "reason": reason,
    }


# ------------------------------------------------------ BH FDR 多重比较校正 ----
def benjamini_hochberg(
    p_values: Iterable[float],
    alpha: float = 0.05,
) -> list[dict[str, object]]:
    """Benjamini–Hochberg 校正。

    输入任意顺序的 p 值；输出与输入同序的 {p_value, rank, q_value, reject}。
    q_i = min_{k ≥ i} ( p_k · m / k )，单调化后与 alpha 比较。
    """
    p_list = [float(p) for p in p_values]
    m = len(p_list)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_list[i])
    q_sorted = [0.0] * m
    running = 1.0
    for pos in range(m - 1, -1, -1):
        idx = order[pos]
        rank = pos + 1
        value = p_list[idx] * m / rank
        running = min(running, value)
        q_sorted[pos] = min(1.0, running)
    out: list[dict[str, object]] = [{} for _ in range(m)]
    for pos, idx in enumerate(order):
        out[idx] = {
            "p_value": round_sig(p_list[idx], 10),
            "rank": pos + 1,
            "q_value": round_sig(q_sorted[pos], 10),
            "reject": bool(q_sorted[pos] <= alpha),
        }
    return out
