"""
プライシングAPI

Burn Analysis と Monte Carlo 法による
HDD/CDD先物・オプションの価格計算を提供する。
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date

import numpy as np
from fastapi import APIRouter

from app.models.pricing import burn_analysis, monte_carlo_pricing
from app.models.temperature import fit_temperature_model
from app.schemas.pricing import (
    BurnAnalysisRequest,
    BurnAnalysisResponse,
    MonteCarloPricingResponse,
    MonteCarloRequest,
)
from app.services.degree_days import calculate_daily_degree_days
from app.services.noaa_client import fetch_temperature_data

router = APIRouter(prefix="/api/pricing", tags=["pricing"])

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


@router.post("/burn-analysis/{station_id}", response_model=BurnAnalysisResponse)
async def run_burn_analysis(
    station_id: str,
    request: BurnAnalysisRequest,
) -> BurnAnalysisResponse:
    """
    Burn Analysis による HDD/CDD 先物・オプション価格を計算する。

    過去N年の実績値から直接プライシング。モデルフリーのベンチマーク。
    """
    # 過去N年+1年分のデータを取得（余裕を持って）
    end = date.today()
    start = date(end.year - request.n_years - 1, 1, 1)

    temperatures = await fetch_temperature_data(
        station_id=station_id, start_date=start, end_date=end,
    )

    # HDD/CDD を日次計算
    daily_dd = calculate_daily_degree_days(temperatures, base_temp=request.base_temp)

    # 年×月でグループ化し、対象月の累積値を年ごとに集計
    yearly_cumulative: dict[int, float] = defaultdict(float)
    for dd in daily_dd:
        m = dd.date.month
        if request.start_month <= request.end_month:
            in_period = request.start_month <= m <= request.end_month
        else:
            # 冬季 (e.g., 11月〜3月) の場合
            in_period = m >= request.start_month or m <= request.end_month

        if in_period:
            val = dd.hdd if request.dd_type == "hdd" else dd.cdd
            yearly_cumulative[dd.date.year] += val

    # 最新N年分を使用
    available_years = sorted(yearly_cumulative.keys())
    if len(available_years) > request.n_years:
        available_years = available_years[-request.n_years:]

    historical = {y: yearly_cumulative[y] for y in available_years}

    result = burn_analysis(
        historical_dd_by_year=historical,
        strike=request.strike,
        discount_factor=request.discount_factor,
        decay_factor=request.decay_factor,
    )

    period_str = MONTH_NAMES[request.start_month]
    if request.start_month != request.end_month:
        period_str += f" - {MONTH_NAMES[request.end_month]}"

    return BurnAnalysisResponse(
        station_id=station_id,
        dd_type=request.dd_type,
        period=period_str,
        futures_price=result.futures_price,
        futures_price_weighted=result.futures_price_weighted,
        std=result.std,
        confidence_interval_95=list(result.confidence_interval),
        call_price=result.call_price,
        put_price=result.put_price,
        strike=request.strike,
        historical_values=result.historical_values,
        historical_years=result.years,
    )


@router.post("/monte-carlo/{station_id}", response_model=MonteCarloPricingResponse)
async def run_monte_carlo(
    station_id: str,
    request: MonteCarloRequest,
) -> MonteCarloPricingResponse:
    """
    Monte Carlo法による HDD/CDD 先物・オプション価格を計算する。

    Q測度下で気温パスをシミュレートし、ペイオフの期待値を取る。
    λ (Market Price of Risk) で実測度→リスク中立測度の変換を制御。
    """
    # モデルフィット用データを取得
    end = date.today()
    start = date(end.year - 5, 1, 1)

    temperatures = await fetch_temperature_data(
        station_id=station_id, start_date=start, end_date=end,
    )

    t = np.arange(len(temperatures), dtype=np.float64)
    tavg = np.array([temp.tavg for temp in temperatures])

    # モデルフィット
    model_result = fit_temperature_model(t, tavg)

    # 対象月の開始日を計算
    target_year = end.year
    target_start = date(target_year, request.target_month, 1)
    n_days = calendar.monthrange(target_year, request.target_month)[1]

    # t_start を基準日からのオフセットに変換
    t_start = (target_start - start).days

    # 初期気温 = 季節成分の値
    T_initial = float(model_result.seasonal.evaluate(np.array([float(t_start)]))[0])

    result = monte_carlo_pricing(
        seasonal=model_result.seasonal,
        ou=model_result.ou,
        t_start=float(t_start),
        n_days=n_days,
        T_initial=T_initial,
        dd_type=request.dd_type,
        base_temp=request.base_temp,
        strike=request.strike,
        discount_factor=request.discount_factor,
        lambda_risk=request.lambda_risk,
        n_paths=request.n_paths,
        seed=request.seed,
    )

    # 分布のパーセンタイル
    dist = result.distribution
    percentiles = {
        "p5": round(float(np.percentile(dist, 5)), 2),
        "p25": round(float(np.percentile(dist, 25)), 2),
        "p50": round(float(np.percentile(dist, 50)), 2),
        "p75": round(float(np.percentile(dist, 75)), 2),
        "p95": round(float(np.percentile(dist, 95)), 2),
    }

    return MonteCarloPricingResponse(
        station_id=station_id,
        dd_type=request.dd_type,
        period=MONTH_NAMES[request.target_month],
        futures_price=result.futures_price,
        futures_se=result.futures_se,
        call_price=result.call_price,
        call_se=result.call_se,
        put_price=result.put_price,
        put_se=result.put_se,
        strike=request.strike,
        lambda_risk=result.lambda_risk,
        n_paths=result.n_paths,
        distribution_percentiles=percentiles,
    )
