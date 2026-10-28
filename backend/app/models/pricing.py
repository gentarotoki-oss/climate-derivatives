"""
HDD/CDD先物・オプションのプライシングモデル

== 不完全市場 (Incomplete Market) と Market Price of Risk ==

株式デリバティブでは、原資産（株）を売買してデルタヘッジできるため、
リスク中立測度 Q が一意に決まり、「正しい価格」が1つ存在する。

しかし、気候デリバティブの原資産は「気温」。気温は売買できない。
→ デルタヘッジ不可能 → Q が一意に決まらない → 「唯一の正解」がない。

この不確定性を解決するために、Market Price of Risk λ を導入する:

  P測度 (実世界):   dT = κ(θ(t) - T)dt + σdW^P
  Q測度 (リスク中立): dT = [κ(θ(t) - T) - λσ]dt + σdW^Q

λ の解釈:
  - λ = 0: リスクプレミアムなし（実測度と同じ）
  - λ > 0: 高温リスクに対するプレミアム（CDD先物が割高に）
  - λ < 0: 低温リスクに対するプレミアム（HDD先物が割高に）

実務では λ は市場価格から逆算（implied λ）するか、
リスク許容度に基づいて設定する。

== プライシング手法 ==

1. Burn Analysis: 過去N年の実績値の平均（モデルフリー）
2. Monte Carlo: Q測度下でパスをシミュレートし、ペイオフの期待値を取る
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
from numpy.typing import NDArray

from app.models.temperature import (
    SeasonalParams,
    OUParams,
    TemperatureModelResult,
    simulate_temperature_paths,
)
from app.services.degree_days import DEFAULT_BASE_TEMP_C


# ---------------------------------------------------------------------------
# データ型
# ---------------------------------------------------------------------------

@dataclass
class BurnAnalysisResult:
    """Burn Analysisの結果"""
    futures_price: float         # 先物価格（累積HDD or CDDの推定値）
    futures_price_weighted: float  # 重み付き平均による先物価格
    std: float                   # 標準偏差
    historical_values: list[float]  # 各年の累積値
    years: list[int]             # 対応する年
    call_price: float = 0.0     # コールオプション価格
    put_price: float = 0.0      # プットオプション価格
    confidence_interval: tuple[float, float] = (0.0, 0.0)  # 95%信頼区間


@dataclass
class MonteCarloPricingResult:
    """Monte Carloプライシングの結果"""
    futures_price: float         # 先物価格 = E^Q[Σ DD]
    futures_se: float            # 標準誤差
    call_price: float            # コール価格 = E^Q[max(Σ DD - K, 0)] * df
    call_se: float               # コール標準誤差
    put_price: float             # プット価格 = E^Q[max(K - Σ DD, 0)] * df
    put_se: float                # プット標準誤差
    n_paths: int
    lambda_risk: float           # 使用した Market Price of Risk
    distribution: NDArray[np.float64]  # 累積DD分布（全パス）


# ---------------------------------------------------------------------------
# Burn Analysis
# ---------------------------------------------------------------------------

def burn_analysis(
    historical_dd_by_year: dict[int, float],
    strike: float = 0.0,
    discount_factor: float = 1.0,
    decay_factor: float = 0.0,
) -> BurnAnalysisResult:
    """
    Burn Analysis: 過去実績からの直接プライシング。

    == Burn Analysisとは ==

    最もシンプルなプライシング手法。確率過程のモデルを使わず、
    過去N年の実績HDD/CDD累積値から直接価格を推定する。

    先物価格 = 過去N年の累積値の平均（= ヒストリカル期待値）

    長所:
      - モデルリスクがない（確率過程の仮定不要）
      - 計算が簡単で直感的
    短所:
      - 気候変動トレンドに対応しにくい
      - データが少ないと不安定
      - Market Price of Risk を反映できない

    Parameters
    ----------
    historical_dd_by_year : dict[int, float]
        年 → 対象期間の累積HDD or CDD
    strike : float
        オプションの行使価格。0ならオプション価格は計算しない。
    discount_factor : float
        割引ファクター exp(-rT)。デフォルトは1.0（割引なし）。
    decay_factor : float
        指数減衰の重み付け係数 (0~1)。0なら等重み、1に近いほど最近の年を重視。
        重み: w_i = exp(-decay * (N - i)) を正規化。
    """
    years = sorted(historical_dd_by_year.keys())
    values = np.array([historical_dd_by_year[y] for y in years])
    n = len(values)

    if n == 0:
        raise ValueError("ヒストリカルデータが空です")

    # 単純平均
    futures_simple = float(np.mean(values))

    # 重み付き平均（最近の年を重視）
    if decay_factor > 0 and n > 1:
        weights = np.exp(-decay_factor * np.arange(n - 1, -1, -1, dtype=np.float64))
        weights /= weights.sum()
        futures_weighted = float(np.dot(weights, values))
    else:
        futures_weighted = futures_simple

    # 標準偏差
    std = float(np.std(values, ddof=1)) if n > 1 else 0.0

    # 95%信頼区間（t分布の近似として ±2σ/√n）
    margin = 2.0 * std / np.sqrt(n) if n > 1 else 0.0
    ci = (futures_simple - margin, futures_simple + margin)

    # オプション価格（ヒストリカル分布から）
    call_price = 0.0
    put_price = 0.0
    if strike > 0:
        # ヒストリカル分布の各年でペイオフを計算して平均
        call_payoffs = np.maximum(values - strike, 0.0)
        put_payoffs = np.maximum(strike - values, 0.0)
        call_price = float(np.mean(call_payoffs)) * discount_factor
        put_price = float(np.mean(put_payoffs)) * discount_factor

    return BurnAnalysisResult(
        futures_price=round(futures_simple, 4),
        futures_price_weighted=round(futures_weighted, 4),
        std=round(std, 4),
        historical_values=[round(v, 4) for v in values],
        years=years,
        call_price=round(call_price, 4),
        put_price=round(put_price, 4),
        confidence_interval=(round(ci[0], 4), round(ci[1], 4)),
    )


# ---------------------------------------------------------------------------
# Monte Carlo プライシング
# ---------------------------------------------------------------------------

def monte_carlo_pricing(
    seasonal: SeasonalParams,
    ou: OUParams,
    t_start: float,
    n_days: int,
    T_initial: float,
    dd_type: str = "hdd",
    base_temp: float = DEFAULT_BASE_TEMP_C,
    strike: float = 0.0,
    discount_factor: float = 1.0,
    lambda_risk: float = 0.0,
    n_paths: int = 10000,
    seed: int | None = None,
) -> MonteCarloPricingResult:
    """
    Monte Carlo法による HDD/CDD 先物・オプションのプライシング。

    == Q測度下でのシミュレーション ==

    P測度（実世界）での OU過程:
      dT = dθ(t) + κ(θ(t) - T)dt + σdW^P

    Q測度（リスク中立）への変換（Girsanov の定理）:
      dW^Q = dW^P + λdt

    Q測度下でのダイナミクス:
      dT = dθ(t) + [κ(θ(t) - T) - λσ]dt + σdW^Q

    λσ は「リスクプレミアム項」。実質的にドリフトをシフトさせる効果がある。

    パスの生成は simulate_temperature_paths に任せる
    (dθ の項と Euler-Maruyama 離散化の説明もそちらにある)。

    Parameters
    ----------
    seasonal, ou : モデルパラメータ
    t_start : シミュレーション開始時点
    n_days : 対象期間の日数
    T_initial : 初期気温
    dd_type : "hdd" or "cdd"
    base_temp : HDD/CDDの基準温度
    strike : オプション行使価格（0なら先物のみ）
    discount_factor : 割引ファクター
    lambda_risk : Market Price of Risk
    n_paths : シミュレーションパス数
    seed : 乱数シード
    """
    # パスの生成（Q測度下）
    paths = simulate_temperature_paths(
        seasonal,
        ou,
        t_start,
        n_days,
        n_paths=n_paths,
        T_initial=T_initial,
        seed=seed,
        lambda_risk=lambda_risk,
    )

    # 日次 HDD/CDD を計算
    if dd_type.lower() == "hdd":
        daily_dd = np.maximum(base_temp - paths, 0.0)
    else:
        daily_dd = np.maximum(paths - base_temp, 0.0)

    # 各パスの累積値
    cumulative_dd = np.sum(daily_dd, axis=1)  # shape: (n_paths,)

    # 先物価格 = E^Q[Σ DD]
    futures_price = float(np.mean(cumulative_dd))
    futures_se = float(np.std(cumulative_dd, ddof=1) / np.sqrt(n_paths))

    # オプション価格
    call_payoffs = np.maximum(cumulative_dd - strike, 0.0)
    put_payoffs = np.maximum(strike - cumulative_dd, 0.0)

    call_price = float(np.mean(call_payoffs)) * discount_factor
    call_se = float(np.std(call_payoffs, ddof=1) / np.sqrt(n_paths)) * discount_factor

    put_price = float(np.mean(put_payoffs)) * discount_factor
    put_se = float(np.std(put_payoffs, ddof=1) / np.sqrt(n_paths)) * discount_factor

    return MonteCarloPricingResult(
        futures_price=round(futures_price, 4),
        futures_se=round(futures_se, 4),
        call_price=round(call_price, 4),
        call_se=round(call_se, 4),
        put_price=round(put_price, 4),
        put_se=round(put_se, 4),
        n_paths=n_paths,
        lambda_risk=lambda_risk,
        distribution=cumulative_dd,
    )
