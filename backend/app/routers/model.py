"""
気温モデル（季節成分 + OU過程）のAPI

フィット結果の取得とモンテカルロシミュレーションを提供する。
"""

from __future__ import annotations

from datetime import date

import numpy as np
from fastapi import APIRouter, Query

from app.models.temperature import (
    fit_temperature_model,
    simulate_temperature_paths,
)
from app.schemas.model import (
    ModelFitResponse,
    OUParamsSchema,
    SeasonalParamsSchema,
    SimulationRequest,
    SimulationResponse,
)
from app.services.noaa_client import fetch_temperature_data

router = APIRouter(prefix="/api/model", tags=["model"])


async def _get_model_data(
    station_id: str,
    start_date: date | None,
    end_date: date | None,
) -> tuple[np.ndarray, np.ndarray, "from app.models.temperature import TemperatureModelResult"]:
    """気温データを取得してモデルフィットを実行する共通ヘルパー"""
    temperatures = await fetch_temperature_data(
        station_id=station_id,
        start_date=start_date,
        end_date=end_date,
    )

    t = np.arange(len(temperatures), dtype=np.float64)
    tavg = np.array([temp.tavg for temp in temperatures])

    from app.models.temperature import fit_temperature_model
    result = fit_temperature_model(t, tavg)

    return t, tavg, result


@router.get("/fit/{station_id}", response_model=ModelFitResponse)
async def get_model_fit(
    station_id: str,
    start_date: date = Query(default=None, description="取得開始日"),
    end_date: date = Query(default=None, description="取得終了日"),
) -> ModelFitResponse:
    """
    気温モデル（季節成分 + OU過程）のフィット結果を返す。

    1. 季節成分 θ(t) をフーリエ級数でフィット
    2. 残差に対して OU過程のパラメータ (κ, σ) を推定
    """
    t, tavg, result = await _get_model_data(station_id, start_date, end_date)

    s = result.seasonal
    amplitude = float(np.sqrt(s.c1**2 + s.d1**2))

    return ModelFitResponse(
        station_id=station_id,
        n_observations=len(tavg),
        seasonal=SeasonalParamsSchema(
            a=round(s.a, 4),
            b=round(s.b, 6),
            c1=round(s.c1, 4),
            d1=round(s.d1, 4),
            c2=round(s.c2, 4),
            d2=round(s.d2, 4),
            amplitude=round(amplitude, 4),
        ),
        ou=OUParamsSchema(
            kappa=round(result.ou.kappa, 6),
            sigma=round(result.ou.sigma, 4),
            kappa_se=round(result.ou.kappa_se, 6),
            sigma_se=round(result.ou.sigma_se, 4),
            half_life_days=round(result.ou.half_life, 2),
            stationary_std=round(result.ou.stationary_std, 4),
        ),
        residual_mean=round(result.residual_mean, 4),
        residual_std=round(result.residual_std, 4),
        r_squared=round(result.r_squared, 4),
    )


@router.post("/simulate/{station_id}", response_model=SimulationResponse)
async def simulate_paths(
    station_id: str,
    request: SimulationRequest = SimulationRequest(),
    start_date: date = Query(default=None, description="学習データ開始日"),
    end_date: date = Query(default=None, description="学習データ終了日"),
) -> SimulationResponse:
    """
    モンテカルロシミュレーションで気温パスを生成する。

    推定済みモデルのパラメータを使い、Euler-Maruyama法で
    指定日数のパスを生成。パーセンタイルバンドとして返す。
    """
    t, tavg, result = await _get_model_data(station_id, start_date, end_date)

    # シミュレーション開始地点 = 学習データの最終時点
    t_start = float(t[-1])
    T_initial = float(tavg[-1])

    paths = simulate_temperature_paths(
        seasonal=result.seasonal,
        ou=result.ou,
        t_start=t_start,
        n_days=request.n_days,
        n_paths=request.n_paths,
        T_initial=T_initial,
        seed=request.seed,
    )

    # パーセンタイルを計算
    percentiles = {
        "p5": np.percentile(paths, 5, axis=0).round(2).tolist(),
        "p25": np.percentile(paths, 25, axis=0).round(2).tolist(),
        "p50": np.percentile(paths, 50, axis=0).round(2).tolist(),
        "p75": np.percentile(paths, 75, axis=0).round(2).tolist(),
        "p95": np.percentile(paths, 95, axis=0).round(2).tolist(),
    }

    # 季節成分の値
    t_sim = np.arange(t_start, t_start + request.n_days, dtype=np.float64)
    seasonal_values = result.seasonal.evaluate(t_sim).round(2).tolist()

    return SimulationResponse(
        station_id=station_id,
        n_days=request.n_days,
        n_paths=request.n_paths,
        percentiles=percentiles,
        mean=np.mean(paths, axis=0).round(2).tolist(),
        seasonal=seasonal_values,
        dates_offset=list(range(request.n_days)),
    )
