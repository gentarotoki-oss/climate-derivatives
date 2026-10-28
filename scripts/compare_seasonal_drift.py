"""
monte_carlo_pricing の結果を、独立に組んだ参照実装と比べるスクリプト。

参照実装: 残差 X = T - θ(t) を OU 過程の厳密な遷移でシミュレートし、θ(t) を足し戻す。
  X_{n+1} = e^{-κ} X_n - (λσ/κ)(1 - e^{-κ}) + σ √((1 - e^{-2κ}) / (2κ)) Z_n

季節成分の傾き dθ/dt を無視したシミュレーションでは、気温の平均が θ(t) より遅れ、
先物価格がずれる。

実行: cd backend && python ../scripts/compare_seasonal_drift.py
"""

from __future__ import annotations

import numpy as np

from app.models.pricing import monte_carlo_pricing
from app.models.temperature import OUParams, SeasonalParams, simulate_temperature_paths
from app.services.degree_days import DEFAULT_BASE_TEMP_C

N_PATHS = 200_000
SEED = 0

# 中緯度の都市を想定した仮のパラメータ（1月1日に最も寒い）
SEASONAL = SeasonalParams(a=12.0, b=0.0, c1=0.0, d1=-10.0, c2=0.0, d2=0.0)
OU = OUParams(kappa=0.25, sigma=2.5)

CONTRACTS = [
    # (名前, 種類, 開始日 t, 日数)
    ("HDD Nov-Mar", "hdd", 304, 151),
    ("HDD April", "hdd", 90, 30),
    ("CDD Jun-Aug", "cdd", 151, 92),
    ("CDD September", "cdd", 243, 30),
]


def reference_paths(t_start: int, n_days: int, lambda_risk: float, rng) -> np.ndarray:
    t = np.arange(t_start, t_start + n_days, dtype=np.float64)
    theta = SEASONAL.evaluate(t)
    k, s = OU.kappa, OU.sigma
    phi = np.exp(-k)
    shift = -(lambda_risk * s / k) * (1.0 - phi)
    sd = s * np.sqrt((1.0 - phi**2) / (2.0 * k))

    x = np.zeros((N_PATHS, n_days))
    z = rng.standard_normal((N_PATHS, n_days - 1))
    for i in range(n_days - 1):
        x[:, i + 1] = phi * x[:, i] + shift + sd * z[:, i]
    return theta + x


def degree_days(paths: np.ndarray, dd_type: str) -> np.ndarray:
    if dd_type == "hdd":
        return np.maximum(DEFAULT_BASE_TEMP_C - paths, 0.0).sum(axis=1)
    return np.maximum(paths - DEFAULT_BASE_TEMP_C, 0.0).sum(axis=1)


def main() -> None:
    # 平均パスの遅れ（λ = 0）
    t = np.arange(0, 365, dtype=np.float64)
    paths = simulate_temperature_paths(SEASONAL, OU, 0, 365, n_paths=20_000, seed=SEED)
    lag = np.abs(paths.mean(axis=0) - SEASONAL.evaluate(t)).max()
    print(f"平均パスと θ(t) の差の最大値: {lag:.2f} °C\n")

    print(f"{'契約':<16}{'λ':>5}{'参照':>10}{'MC':>10}{'差':>9}{'差(%)':>8}")
    for name, dd_type, t_start, n_days in CONTRACTS:
        for lam in (0.0, 0.1):
            ref = degree_days(
                reference_paths(t_start, n_days, lam, np.random.default_rng(SEED)), dd_type
            ).mean()
            mc = monte_carlo_pricing(
                SEASONAL, OU, t_start, n_days,
                T_initial=float(SEASONAL.evaluate(np.array([float(t_start)]))[0]),
                dd_type=dd_type, lambda_risk=lam, n_paths=N_PATHS, seed=SEED,
            ).futures_price
            diff = mc - ref
            print(f"{name:<16}{lam:>5.1f}{ref:>10.1f}{mc:>10.1f}{diff:>9.1f}{100 * diff / ref:>7.1f}%")


if __name__ == "__main__":
    main()
