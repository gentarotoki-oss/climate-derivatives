"""
HDD/CDD (Heating Degree Days / Cooling Degree Days) 計算サービス

== なぜ HDD/CDD が重要なのか ==

エネルギー会社にとって、冬の暖房需要や夏の冷房需要は気温に直結する。
HDD/CDDはこの「気温リスク」を定量化する指標であり、
CME (シカゴ・マーカンタイル取引所) ではこれを原資産とした先物・オプションが取引される。

== 計算式 ==

基準温度を T_base とすると:
  HDD = max(T_base - T_avg, 0)  ... 寒い日ほど大きい
  CDD = max(T_avg - T_base, 0)  ... 暑い日ほど大きい

CME標準の基準温度は 65°F (≈ 18.3°C)。
65°Fは「暖房も冷房も不要な快適温度」として歴史的に使われてきた値。

== 累積値 ==

先物の原資産は、特定期間（通常1ヶ月）のHDD/CDDの「累積値」。
例: 2024年1月のシカゴHDD先物 = Σ(1月1日〜31日の日次HDD)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from app.schemas.temperature import (
    DailyDegreeDays,
    DailyTemperature,
    MonthlyDegreeDays,
)

# CME標準の基準温度（摂氏）
DEFAULT_BASE_TEMP_C = 18.3  # 65°F ≈ 18.3°C


def calculate_daily_degree_days(
    temperatures: list[DailyTemperature],
    base_temp: float = DEFAULT_BASE_TEMP_C,
) -> list[DailyDegreeDays]:
    """
    日次のHDD/CDDを計算する。

    Parameters
    ----------
    temperatures : list[DailyTemperature]
        日次気温データのリスト
    base_temp : float
        基準温度 (°C)。デフォルトは18.3°C (65°F)。
        基準温度を変えると、異なるリスクプロファイルを分析できる。

    Returns
    -------
    list[DailyDegreeDays]
        日次HDD/CDDのリスト

    理論メモ
    --------
    HDD/CDDは「エネルギー需要の代理変数」として機能する。
    - HDD = max(T_base - T_avg, 0): 気温がT_base以下のとき暖房が必要
    - CDD = max(T_avg - T_base, 0): 気温がT_base以上のとき冷房が必要
    - HDD, CDDは同時に正になることはない（互いに排他的）
    """
    results: list[DailyDegreeDays] = []

    for temp in temperatures:
        hdd = max(base_temp - temp.tavg, 0.0)
        cdd = max(temp.tavg - base_temp, 0.0)

        results.append(DailyDegreeDays(
            date=temp.date,
            tavg=temp.tavg,
            hdd=round(hdd, 2),
            cdd=round(cdd, 2),
        ))

    return results


def calculate_cumulative(
    degree_days: list[DailyDegreeDays],
) -> tuple[float, float]:
    """
    期間内のHDD/CDD累積値を計算する。

    累積値が気候先物の原資産になる。
    例えば「2024年1月シカゴHDD先物」の決済価格は、
    1月の全日のHDDを合計した値 × $20。

    Returns
    -------
    (cumulative_hdd, cumulative_cdd) : tuple[float, float]
    """
    cum_hdd = sum(dd.hdd for dd in degree_days)
    cum_cdd = sum(dd.cdd for dd in degree_days)
    return round(cum_hdd, 2), round(cum_cdd, 2)


def calculate_monthly_degree_days(
    degree_days: list[DailyDegreeDays],
) -> list[MonthlyDegreeDays]:
    """
    月次のHDD/CDD累積値を計算する。

    CME気候先物は月単位で取引されるため、
    月次累積値は最も実務的に重要な集計レベル。

    HDD先物は主に冬季 (10月〜4月) に活発に取引され、
    CDD先物は夏季 (5月〜9月) に活発に取引される。
    """
    monthly: dict[tuple[int, int], list[DailyDegreeDays]] = defaultdict(list)

    for dd in degree_days:
        key = (dd.date.year, dd.date.month)
        monthly[key].append(dd)

    results: list[MonthlyDegreeDays] = []
    for (year, month), days in sorted(monthly.items()):
        hdd_sum = sum(d.hdd for d in days)
        cdd_sum = sum(d.cdd for d in days)
        results.append(MonthlyDegreeDays(
            year=year,
            month=month,
            hdd=round(hdd_sum, 2),
            cdd=round(cdd_sum, 2),
            days_count=len(days),
        ))

    return results
