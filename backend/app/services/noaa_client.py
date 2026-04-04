"""
NOAA Climate Data Online (CDO) APIクライアント

気候デリバティブの原資産データとなる気温時系列を取得する。
データソースはNOAAのGHCND (Global Historical Climatology Network - Daily) データセット。

APIドキュメント: https://www.ncdc.noaa.gov/cdo-web/api/v2/
レートリミット: 5リクエスト/秒, 1000リクエスト/日

主要都市のステーションID (CME気候先物の対象都市):
  - シカゴ:     CITY:US170006
  - ニューヨーク: CITY:US360019
  - デトロイト:   CITY:US260006
  - アトランタ:   CITY:US130001
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, timedelta
from typing import Any

import httpx
import numpy as np
from pydantic_settings import BaseSettings

from app.schemas.temperature import DailyTemperature

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------

class NOAASettings(BaseSettings):
    """環境変数から読み取るNOAA API設定"""
    noaa_api_token: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


_settings = NOAASettings()

BASE_URL = "https://www.ncdc.noaa.gov/cdo-web/api/v2"

# レートリミット管理
_request_times: list[float] = []
MAX_REQUESTS_PER_SECOND = 5


# ---------------------------------------------------------------------------
# レートリミッター
# ---------------------------------------------------------------------------

async def _rate_limit() -> None:
    """
    NOAA APIのレートリミット (5 req/sec) を遵守するためのスロットリング。
    直近1秒以内のリクエスト数がMAX_REQUESTS_PER_SECONDに達していたら待機する。
    """
    now = time.monotonic()
    # 1秒より古い記録を除去
    while _request_times and now - _request_times[0] > 1.0:
        _request_times.pop(0)

    if len(_request_times) >= MAX_REQUESTS_PER_SECOND:
        wait = 1.0 - (now - _request_times[0]) + 0.05
        if wait > 0:
            logger.debug(f"Rate limit: waiting {wait:.2f}s")
            await asyncio.sleep(wait)

    _request_times.append(time.monotonic())


# ---------------------------------------------------------------------------
# API呼び出し
# ---------------------------------------------------------------------------

async def fetch_temperature_data(
    station_id: str = "CITY:US170006",
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[DailyTemperature]:
    """
    NOAA CDO APIから日次気温データ (TMAX, TMIN) を取得する。

    APIは1リクエストあたり最大1000レコードを返すため、
    期間が長い場合は自動的にページネーション/期間分割して取得する。
    NOAA APIが1リクエストで扱える期間は最大1年間。

    Parameters
    ----------
    station_id : str
        NOAAのロケーションID。デフォルトはシカゴ。
    start_date : date
        取得開始日。デフォルトは1年前。
    end_date : date
        取得終了日。デフォルトは昨日。

    Returns
    -------
    list[DailyTemperature]
        日次気温のリスト（°C変換済み）
    """
    if not _settings.noaa_api_token:
        logger.warning("NOAA_API_TOKEN が未設定です。サンプルデータを返します。")
        return generate_sample_data(start_date, end_date)

    if end_date is None:
        end_date = date.today() - timedelta(days=1)
    if start_date is None:
        start_date = end_date - timedelta(days=365)

    all_records: list[DailyTemperature] = []

    # NOAA APIは1リクエストで最大1年分しか取得できないため、1年ごとに分割
    chunk_start = start_date
    while chunk_start <= end_date:
        chunk_end = min(chunk_start + timedelta(days=364), end_date)
        records = await _fetch_chunk(station_id, chunk_start, chunk_end)
        all_records.extend(records)
        chunk_start = chunk_end + timedelta(days=1)

    # 日付順にソート & 重複除去
    seen: set[date] = set()
    unique: list[DailyTemperature] = []
    for rec in sorted(all_records, key=lambda r: r.date):
        if rec.date not in seen:
            seen.add(rec.date)
            unique.append(rec)

    return unique


async def _fetch_chunk(
    station_id: str,
    start_date: date,
    end_date: date,
) -> list[DailyTemperature]:
    """1年以内の期間についてページネーション付きで取得"""
    records: list[DailyTemperature] = []
    offset = 1  # NOAA APIは1始まり
    limit = 1000

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            await _rate_limit()

            params: dict[str, Any] = {
                "datasetid": "GHCND",
                "datatypeid": "TMAX,TMIN",
                "locationid": station_id,
                "startdate": start_date.isoformat(),
                "enddate": end_date.isoformat(),
                "units": "standard",  # 10分の1°C単位のまま
                "limit": limit,
                "offset": offset,
            }

            resp = await client.get(
                f"{BASE_URL}/data",
                headers={"token": _settings.noaa_api_token},
                params=params,
            )

            if resp.status_code != 200:
                logger.error(f"NOAA API error: {resp.status_code} {resp.text}")
                break

            body = resp.json()
            results = body.get("results", [])
            if not results:
                break

            # TMAX/TMINをペアにして DailyTemperature に変換
            records.extend(_parse_results(results))

            # 次ページがあるか
            metadata = body.get("metadata", {}).get("resultset", {})
            total = metadata.get("count", 0)
            offset += limit
            if offset > total:
                break

    return records


def _parse_results(results: list[dict]) -> list[DailyTemperature]:
    """
    NOAA APIの生レスポンスをDailyTemperatureに変換する。

    NOAAデータの注意点:
    - TMAX/TMINは10分の1°C単位で返される（例: 283 → 28.3°C）
    - 同じ日にTMAXとTMINが別レコードで返る
    - 一部の日はTMAXのみ or TMINのみの場合がある
    """
    from collections import defaultdict

    by_date: dict[date, dict[str, float]] = defaultdict(dict)

    for rec in results:
        d = date.fromisoformat(rec["date"][:10])
        datatype = rec["datatype"]
        # 10分の1°C → °C
        value = rec["value"] / 10.0
        by_date[d][datatype] = value

    temps: list[DailyTemperature] = []
    for d, vals in sorted(by_date.items()):
        tmax = vals.get("TMAX")
        tmin = vals.get("TMIN")
        if tmax is not None and tmin is not None:
            tavg = (tmax + tmin) / 2.0
            temps.append(DailyTemperature(date=d, tmax=tmax, tmin=tmin, tavg=tavg))

    return temps


# ---------------------------------------------------------------------------
# フォールバック: サンプルデータ生成
# ---------------------------------------------------------------------------

def generate_sample_data(
    start_date: date | None = None,
    end_date: date | None = None,
    station_id: str = "CITY:US170006",
) -> list[DailyTemperature]:
    """
    NOAA APIが使えない場合のフォールバック。
    シカゴの気温パターンを模したサンプルデータを生成する。

    モデル:
      T_avg(t) = μ + A * sin(2π(t - φ)/365) + ε
    シカゴの場合:
      μ ≈ 10°C (年平均), A ≈ 15°C (振幅), φ ≈ 110日 (最高気温が7月下旬)

    これは Step 2 で学ぶ OU過程の簡易版。
    """
    if end_date is None:
        end_date = date.today() - timedelta(days=1)
    if start_date is None:
        start_date = end_date - timedelta(days=365)

    rng = np.random.default_rng(seed=42)
    days = (end_date - start_date).days + 1

    data: list[DailyTemperature] = []
    for i in range(days):
        current_date = start_date + timedelta(days=i)
        day_of_year = current_date.timetuple().tm_yday

        # 季節成分: シカゴの気温パターン
        # 年平均10°C、振幅15°C、最高は7月下旬 (day_of_year ≈ 200)
        seasonal = 10.0 + 15.0 * np.sin(2 * np.pi * (day_of_year - 110) / 365)

        # ランダムノイズ（日較差を考慮）
        noise = rng.normal(0, 3.0)
        tavg = seasonal + noise

        # TMAX/TMIN は平均から日較差分ずらす
        daily_range = 5.0 + 2.0 * rng.random()
        tmax = tavg + daily_range / 2
        tmin = tavg - daily_range / 2

        data.append(DailyTemperature(
            date=current_date,
            tmax=round(tmax, 1),
            tmin=round(tmin, 1),
            tavg=round(tavg, 1),
        ))

    return data
