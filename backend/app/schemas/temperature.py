"""
気温データ・HDD/CDDに関するPydanticスキーマ定義

気候デリバティブでは、気温データが「原資産」にあたる。
株式デリバティブにおける株価に相当するのが、ここで定義する日次気温やHDD/CDD値。
"""

from datetime import date
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 気温データ
# ---------------------------------------------------------------------------

class DailyTemperature(BaseModel):
    """
    1日分の気温レコード。

    NOAAから取得するGHCNDデータセットでは TMAX / TMIN が
    10分の1°C単位で提供される（例: 283 → 28.3°C）。
    このスキーマではすでに°C単位に変換済みの値を保持する。
    """
    date: date
    tmax: float = Field(..., description="日最高気温 (°C)")
    tmin: float = Field(..., description="日最低気温 (°C)")
    tavg: float = Field(..., description="日平均気温 (°C) = (TMAX + TMIN) / 2")


class TemperatureResponse(BaseModel):
    """気温データAPIのレスポンス"""
    station_id: str
    station_name: str | None = None
    unit: str = "celsius"
    data: list[DailyTemperature]


# ---------------------------------------------------------------------------
# HDD / CDD (Heating / Cooling Degree Days)
# ---------------------------------------------------------------------------

class DailyDegreeDays(BaseModel):
    """
    1日分のHDD/CDD値。

    HDD (Heating Degree Days) = max(T_base - T_avg, 0)
      → 気温が基準より低い日に暖房需要が発生。HDDが大きいほど寒い。
    CDD (Cooling Degree Days) = max(T_avg - T_base, 0)
      → 気温が基準より高い日に冷房需要が発生。CDDが大きいほど暑い。

    CMEの気候先物では、特定期間（通常1ヶ月）のHDD/CDDの「累積値」が
    取引の対象になる。1 HDD/CDD = $20 の掛け目。
    """
    date: date
    tavg: float = Field(..., description="日平均気温 (°C)")
    hdd: float = Field(..., description="Heating Degree Days")
    cdd: float = Field(..., description="Cooling Degree Days")


class DegreeDaysResponse(BaseModel):
    """HDD/CDDデータAPIのレスポンス"""
    station_id: str
    base_temp: float = Field(..., description="基準温度 (°C)")
    data: list[DailyDegreeDays]
    cumulative_hdd: float = Field(..., description="期間内HDD累積値")
    cumulative_cdd: float = Field(..., description="期間内CDD累積値")


class MonthlyDegreeDays(BaseModel):
    """月次HDD/CDD累積値 — CME先物の決済単位"""
    year: int
    month: int
    hdd: float
    cdd: float
    days_count: int = Field(..., description="当月のデータ日数")
