"""
HDD/CDD (Degree Days) 計算API

気候デリバティブの原資産となるHDD/CDD値を計算して返す。
日次値・累積値・月次累積値を提供する。
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from app.schemas.temperature import DegreeDaysResponse, MonthlyDegreeDays
from app.services.degree_days import (
    DEFAULT_BASE_TEMP_C,
    calculate_cumulative,
    calculate_daily_degree_days,
    calculate_monthly_degree_days,
)
from app.services.noaa_client import fetch_temperature_data

router = APIRouter(prefix="/api/degree-days", tags=["degree-days"])


@router.get("/{station_id}", response_model=DegreeDaysResponse)
async def get_degree_days(
    station_id: str,
    start_date: date = Query(default=None, description="取得開始日"),
    end_date: date = Query(default=None, description="取得終了日"),
    base_temp: float = Query(
        default=DEFAULT_BASE_TEMP_C,
        description="基準温度 (°C)。CME標準は18.3°C (65°F)。",
    ),
) -> DegreeDaysResponse:
    """
    日次HDD/CDDと期間累積値を返す。

    HDD = max(base_temp - T_avg, 0)  暖房需要の指標
    CDD = max(T_avg - base_temp, 0)  冷房需要の指標

    CME気候先物は、この累積値に対してプライシングされる。
    """
    temperatures = await fetch_temperature_data(
        station_id=station_id,
        start_date=start_date,
        end_date=end_date,
    )

    daily = calculate_daily_degree_days(temperatures, base_temp=base_temp)
    cum_hdd, cum_cdd = calculate_cumulative(daily)

    return DegreeDaysResponse(
        station_id=station_id,
        base_temp=base_temp,
        data=daily,
        cumulative_hdd=cum_hdd,
        cumulative_cdd=cum_cdd,
    )


@router.get("/{station_id}/monthly", response_model=list[MonthlyDegreeDays])
async def get_monthly_degree_days(
    station_id: str,
    start_date: date = Query(default=None, description="取得開始日"),
    end_date: date = Query(default=None, description="取得終了日"),
    base_temp: float = Query(default=DEFAULT_BASE_TEMP_C, description="基準温度 (°C)"),
) -> list[MonthlyDegreeDays]:
    """
    月次HDD/CDD累積値を返す。

    CME気候先物は月単位で取引されるため、
    この月次累積値が先物の決済対象になる。

    例: 2024年1月シカゴHDD先物の決済値 = 1月の日次HDDの合計
    """
    temperatures = await fetch_temperature_data(
        station_id=station_id,
        start_date=start_date,
        end_date=end_date,
    )

    daily = calculate_daily_degree_days(temperatures, base_temp=base_temp)
    return calculate_monthly_degree_days(daily)
