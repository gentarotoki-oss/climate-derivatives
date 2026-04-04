"""
気温データAPI

NOAA CDO APIから取得した日次気温データを提供する。
気候デリバティブの原資産データへのアクセスポイント。
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Query

from app.schemas.temperature import TemperatureResponse
from app.services.noaa_client import fetch_temperature_data

router = APIRouter(prefix="/api/temperature", tags=["temperature"])

# CME気候先物の主要都市
CITY_NAMES: dict[str, str] = {
    "CITY:US170006": "Chicago, IL",
    "CITY:US360019": "New York, NY",
    "CITY:US260006": "Detroit, MI",
    "CITY:US130001": "Atlanta, GA",
    "CITY:US420024": "Philadelphia, PA",
}


@router.get("/{station_id}", response_model=TemperatureResponse)
async def get_temperature(
    station_id: str,
    start_date: date = Query(
        default=None,
        description="取得開始日 (YYYY-MM-DD)。デフォルトは1年前。",
    ),
    end_date: date = Query(
        default=None,
        description="取得終了日 (YYYY-MM-DD)。デフォルトは昨日。",
    ),
) -> TemperatureResponse:
    """
    指定ステーションの日次気温データを取得する。

    NOAA CDO APIからGHCND (TMAX, TMIN) データを取得し、
    °C単位の日次気温データとして返す。

    station_idの例:
    - CITY:US170006 (シカゴ) — CME気候先物の最も代表的な都市
    - CITY:US360019 (ニューヨーク)
    """
    data = await fetch_temperature_data(
        station_id=station_id,
        start_date=start_date,
        end_date=end_date,
    )

    return TemperatureResponse(
        station_id=station_id,
        station_name=CITY_NAMES.get(station_id),
        unit="celsius",
        data=data,
    )
