"""
気温の確率過程モデル — Ornstein-Uhlenbeck (OU) 過程

== なぜ OU過程か？ ==

株価モデルで標準的な GBM (幾何ブラウン運動) は気温に不適切:
  - GBM: dS = μS dt + σS dW → 指数的に発散しうる
  - 気温は物理的に発散しない。毎年同じ季節パターンに「戻る」

気温のような **平均回帰 (mean-reverting)** 過程には OU過程が適する:
  dT = κ(θ(t) - T) dt + σ dW

ここで:
  - κ (kappa): 平均回帰速度。大きいほど速く平均に戻る。
    直感: κ ≈ 0.3 なら「約3日で偏差が半減」(半減期 = ln2/κ)
  - θ(t): 時変の平均気温（季節成分）。sin/cos で表現。
  - σ (sigma): ボラティリティ。日々のランダムな変動の大きさ。

== モデル構成 ==

1. 季節成分 θ(t) = a + b*t + Σ[cₖsin(2πkt/365) + dₖcos(2πkt/365)]
   - a: 年平均気温のベースライン
   - b: 長期トレンド（温暖化等）
   - フーリエ項: 季節変動（年周期 + 半年周期）

2. 残差 = T_observed - θ(t)  → OU過程に従うと仮定

3. OU過程のパラメータ (κ, σ) を残差系列から OLS で推定
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import curve_fit

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# データ型
# ---------------------------------------------------------------------------

@dataclass
class SeasonalParams:
    """
    季節成分 θ(t) のパラメータ。

    θ(t) = a + b*t + c1*sin(2πt/365) + d1*cos(2πt/365)
                    + c2*sin(4πt/365) + d2*cos(4πt/365)

    第2高調波 (半年周期) を含めることで、春秋の非対称性も捉えられる。
    """
    a: float       # 定数項（年平均気温のベースライン）
    b: float       # 線形トレンド（1日あたりの変化率、温暖化の影響）
    c1: float      # sin(年周期) の係数
    d1: float      # cos(年周期) の係数
    c2: float      # sin(半年周期) の係数
    d2: float      # cos(半年周期) の係数

    def evaluate(self, t: NDArray[np.float64]) -> NDArray[np.float64]:
        """時刻 t (日数) における季節成分の値を返す"""
        return (
            self.a
            + self.b * t
            + self.c1 * np.sin(2 * np.pi * t / 365)
            + self.d1 * np.cos(2 * np.pi * t / 365)
            + self.c2 * np.sin(4 * np.pi * t / 365)
            + self.d2 * np.cos(4 * np.pi * t / 365)
        )


@dataclass
class OUParams:
    """
    Ornstein-Uhlenbeck 過程のパラメータ。

    dX = κ(0 - X) dt + σ dW  (残差 X に対して、平均0に回帰)

    κ (kappa): 平均回帰速度 [1/日]
      - 大きい → 速く平均に戻る（気温偏差が長続きしない）
      - 小さい → ゆっくり戻る（異常気温が持続しやすい）
      - 半減期 = ln(2) / κ 日

    σ (sigma): ボラティリティ [°C / √日]
      - 日々のランダムな気温変動の大きさ

    定常分散: σ² / (2κ)
      - κが大きくσが小さいほど、気温のばらつきが小さい
    """
    kappa: float
    sigma: float
    kappa_se: float = 0.0  # κの標準誤差
    sigma_se: float = 0.0  # σの標準誤差

    @property
    def half_life(self) -> float:
        """偏差の半減期 (日数)"""
        if self.kappa <= 0:
            return float("inf")
        return np.log(2) / self.kappa

    @property
    def stationary_variance(self) -> float:
        """定常分散 σ²/(2κ)"""
        if self.kappa <= 0:
            return float("inf")
        return self.sigma**2 / (2 * self.kappa)

    @property
    def stationary_std(self) -> float:
        """定常標準偏差"""
        return np.sqrt(self.stationary_variance)


@dataclass
class TemperatureModelResult:
    """季節成分 + OU過程のフィット結果をまとめたもの"""
    seasonal: SeasonalParams
    ou: OUParams
    residual_mean: float
    residual_std: float
    r_squared: float  # 季節成分フィットのR²


# ---------------------------------------------------------------------------
# 季節成分の推定
# ---------------------------------------------------------------------------

def _seasonal_func(
    t: NDArray[np.float64],
    a: float, b: float,
    c1: float, d1: float,
    c2: float, d2: float,
) -> NDArray[np.float64]:
    """curve_fit 用の季節関数"""
    return (
        a + b * t
        + c1 * np.sin(2 * np.pi * t / 365)
        + d1 * np.cos(2 * np.pi * t / 365)
        + c2 * np.sin(4 * np.pi * t / 365)
        + d2 * np.cos(4 * np.pi * t / 365)
    )


def fit_seasonal(
    t: NDArray[np.float64],
    temperatures: NDArray[np.float64],
) -> SeasonalParams:
    """
    気温の季節成分 θ(t) をフーリエ級数 + 線形トレンドでフィットする。

    Parameters
    ----------
    t : array
        基準日からの経過日数（0, 1, 2, ...）
    temperatures : array
        日平均気温 (°C)

    Returns
    -------
    SeasonalParams
        フィットされた季節成分のパラメータ

    手法メモ
    --------
    scipy.optimize.curve_fit を使用（非線形最小二乗法）。
    ただし、この問題は実際にはパラメータに対して線形なので、
    OLS (np.linalg.lstsq) でも解ける。curve_fit を使うのは
    将来的に非線形項を追加しやすくするため。
    """
    # 初期推定値
    p0 = [
        np.mean(temperatures),  # a: 年平均
        0.0,                     # b: トレンド（まず0と仮定）
        0.0, -15.0,             # c1, d1: 年周期（北半球は cos 項が支配的）
        0.0, 0.0,               # c2, d2: 半年周期
    ]

    popt, _ = curve_fit(_seasonal_func, t, temperatures, p0=p0)

    return SeasonalParams(
        a=float(popt[0]),
        b=float(popt[1]),
        c1=float(popt[2]),
        d1=float(popt[3]),
        c2=float(popt[4]),
        d2=float(popt[5]),
    )


# ---------------------------------------------------------------------------
# OU過程パラメータ推定
# ---------------------------------------------------------------------------

def fit_ou(
    residuals: NDArray[np.float64],
    dt: float = 1.0,
) -> OUParams:
    """
    残差系列（脱季節化済み気温）に対して OU過程のパラメータを推定する。

    == 推定方法: OLS回帰 ==

    離散化した OU過程:
      X_{n+1} = X_n + κ(0 - X_n)Δt + σ√(Δt) ε_n

    変形すると:
      X_{n+1} = (1 - κΔt) X_n + σ√(Δt) ε_n

    これは X_{n+1} を X_n に回帰する AR(1) モデル:
      X_{n+1} = φ X_n + ε'_n

    ここから:
      φ = 1 - κΔt  →  κ = (1 - φ) / Δt
      Var(ε'_n) = σ²Δt  →  σ = std(residuals) / √Δt

    Parameters
    ----------
    residuals : array
        脱季節化済みの気温残差
    dt : float
        時間刻み（日単位、通常1.0）

    Returns
    -------
    OUParams
        推定されたκとσ（標準誤差付き）
    """
    n = len(residuals)
    if n < 10:
        raise ValueError("推定には最低10データポイントが必要です")

    X = residuals[:-1]  # X_n
    Y = residuals[1:]   # X_{n+1}

    # OLS: Y = φ X + ε → φ = (X'X)^{-1} X'Y
    X_mat = X.reshape(-1, 1)
    phi = float(np.linalg.lstsq(X_mat, Y, rcond=None)[0][0])

    # パラメータ変換
    kappa = (1.0 - phi) / dt

    # 残差の標準偏差からσを推定
    residuals_ols = Y - phi * X
    sigma = float(np.std(residuals_ols, ddof=1)) / np.sqrt(dt)

    # 標準誤差の計算
    # φの標準誤差: SE(φ) = σ_ε / sqrt(Σ X_n²)
    se_phi = float(np.std(residuals_ols, ddof=1)) / np.sqrt(np.sum(X**2))
    kappa_se = se_phi / dt  # δ法による変換

    # σの標準誤差 (χ²分布の近似)
    sigma_se = sigma / np.sqrt(2 * (n - 2))

    # κが負（非定常）の場合は警告
    if kappa <= 0:
        logger.warning(
            f"推定されたκ={kappa:.4f}が非正。"
            "データが平均回帰していない可能性があります。"
        )

    return OUParams(
        kappa=kappa,
        sigma=sigma,
        kappa_se=kappa_se,
        sigma_se=sigma_se,
    )


# ---------------------------------------------------------------------------
# 統合フィット
# ---------------------------------------------------------------------------

def fit_temperature_model(
    t: NDArray[np.float64],
    temperatures: NDArray[np.float64],
) -> TemperatureModelResult:
    """
    気温モデル全体（季節成分 + OU過程）をフィットする。

    ステップ:
    1. 季節成分 θ(t) をフィット
    2. 残差 = T - θ(t) を計算
    3. 残差に対して OU過程のパラメータを推定

    Parameters
    ----------
    t : array
        基準日からの経過日数
    temperatures : array
        日平均気温 (°C)
    """
    # 1. 季節成分のフィット
    seasonal = fit_seasonal(t, temperatures)
    theta = seasonal.evaluate(t)

    # 2. 残差の計算
    residuals = temperatures - theta

    # R²の計算 (季節成分がどの程度説明力を持つか)
    ss_res = np.sum(residuals**2)
    ss_tot = np.sum((temperatures - np.mean(temperatures))**2)
    r_squared = 1.0 - ss_res / ss_tot

    # 3. OU過程パラメータの推定
    ou = fit_ou(residuals)

    return TemperatureModelResult(
        seasonal=seasonal,
        ou=ou,
        residual_mean=float(np.mean(residuals)),
        residual_std=float(np.std(residuals)),
        r_squared=r_squared,
    )


# ---------------------------------------------------------------------------
# モンテカルロ シミュレーション
# ---------------------------------------------------------------------------

def simulate_temperature_paths(
    seasonal: SeasonalParams,
    ou: OUParams,
    t_start: float,
    n_days: int,
    n_paths: int = 1000,
    T_initial: float | None = None,
    seed: int | None = None,
    lambda_risk: float = 0.0,
) -> NDArray[np.float64]:
    """
    Euler-Maruyama法で気温パスをシミュレートする。

    == 季節成分の傾き dθ/dt ==

    推定したモデルは「残差 X = T - θ(t) が OU過程に従う」というもの:
      dX = -κX dt + σ dW

    T = θ(t) + X なので、気温そのもののSDEは
      dT = dθ(t) + κ(θ(t) - T) dt + σ dW

    となる (Dornier & Queruel, 2000)。dθ の項を落とすと、季節成分が
    動いている時期 (春・秋) に気温の平均が θ(t) より約 θ'(t)/κ 遅れ、
    HDD/CDD の期待値がずれる。

    == Euler-Maruyama法 ==

    残差 X を離散化して θ を足し戻す:
      X_{n+1} = X_n + (-κX_n - λσ)Δt + σ√(Δt) Z_n
      T_{n+1} = θ(t_{n+1}) + X_{n+1}

    これは T の式で書くと
      T_{n+1} = T_n + [θ(t_{n+1}) - θ(t_n)] + [κ(θ(t_n) - T_n) - λσ]Δt + σ√(Δt) Z_n

    と同じで、θ の増分が dθ の項にあたる。ここで Z_n ~ N(0,1) は標準正規乱数。

    λ (Market Price of Risk) を与えると、Q測度下のパスになる
    (詳細は app.models.pricing を参照)。

    Parameters
    ----------
    seasonal : SeasonalParams
        季節成分のパラメータ
    ou : OUParams
        OU過程のパラメータ
    t_start : float
        シミュレーション開始時点（基準日からの日数）
    n_days : int
        シミュレーション日数
    n_paths : int
        生成するパス数（多いほどMC推定が正確に）
    T_initial : float or None
        初期気温。Noneの場合は季節成分の値を使用。
    seed : int or None
        乱数シード（再現性のため）
    lambda_risk : float
        Market Price of Risk。0なら実測度 P のパス。

    Returns
    -------
    NDArray of shape (n_paths, n_days)
        シミュレートされた気温パス
    """
    rng = np.random.default_rng(seed)
    dt = 1.0  # 日単位

    # 時間軸
    t = np.arange(t_start, t_start + n_days, dtype=np.float64)

    # 季節成分の値を事前計算
    theta = seasonal.evaluate(t)

    # 初期値
    if T_initial is None:
        T_initial = theta[0]

    # パスの格納配列
    paths = np.zeros((n_paths, n_days))
    paths[:, 0] = T_initial

    # 正規乱数を一括生成（効率化）
    Z = rng.standard_normal((n_paths, n_days - 1))

    # Euler-Maruyama ステップ
    kappa = ou.kappa
    sigma = ou.sigma

    for i in range(n_days - 1):
        seasonal_step = theta[i + 1] - theta[i]  # dθ の項
        drift = (kappa * (theta[i] - paths[:, i]) - lambda_risk * sigma) * dt
        diffusion = sigma * np.sqrt(dt) * Z[:, i]
        paths[:, i + 1] = paths[:, i] + seasonal_step + drift + diffusion

    return paths
