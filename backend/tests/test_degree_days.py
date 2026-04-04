"""
HDD/CDD計算のユニットテスト

既知の入力に対して期待される出力を検証する。
金融計算のテストでは「境界値」と「既知の解析解」のテストが特に重要。
"""

from datetime import date

import pytest

from app.schemas.temperature import DailyTemperature
from app.services.degree_days import (
    DEFAULT_BASE_TEMP_C,
    calculate_cumulative,
    calculate_daily_degree_days,
    calculate_monthly_degree_days,
)


# ---------------------------------------------------------------------------
# テストデータ
# ---------------------------------------------------------------------------

def _make_temp(d: str, tavg: float) -> DailyTemperature:
    """テスト用ヘルパー: 平均気温からDailyTemperatureを生成"""
    return DailyTemperature(
        date=date.fromisoformat(d),
        tmax=tavg + 3.0,
        tmin=tavg - 3.0,
        tavg=tavg,
    )


# ---------------------------------------------------------------------------
# HDD/CDD 日次計算テスト
# ---------------------------------------------------------------------------

class TestDailyDegreeDays:
    """日次HDD/CDD計算の検証"""

    def test_cold_day_produces_hdd(self):
        """基準温度より寒い日 → HDD > 0, CDD = 0"""
        temps = [_make_temp("2024-01-15", 5.0)]  # 5°C（冬の寒い日）
        result = calculate_daily_degree_days(temps)

        assert len(result) == 1
        assert result[0].hdd == pytest.approx(DEFAULT_BASE_TEMP_C - 5.0, abs=0.01)
        assert result[0].cdd == 0.0

    def test_hot_day_produces_cdd(self):
        """基準温度より暑い日 → HDD = 0, CDD > 0"""
        temps = [_make_temp("2024-07-15", 30.0)]  # 30°C（夏の暑い日）
        result = calculate_daily_degree_days(temps)

        assert result[0].hdd == 0.0
        assert result[0].cdd == pytest.approx(30.0 - DEFAULT_BASE_TEMP_C, abs=0.01)

    def test_base_temp_day(self):
        """基準温度ちょうどの日 → HDD = 0, CDD = 0"""
        temps = [_make_temp("2024-04-15", DEFAULT_BASE_TEMP_C)]
        result = calculate_daily_degree_days(temps)

        assert result[0].hdd == 0.0
        assert result[0].cdd == 0.0

    def test_hdd_cdd_mutually_exclusive(self):
        """HDDとCDDは同時に正にならない（相互排他）"""
        temps = [
            _make_temp("2024-01-01", -10.0),
            _make_temp("2024-04-15", DEFAULT_BASE_TEMP_C),
            _make_temp("2024-07-15", 35.0),
        ]
        results = calculate_daily_degree_days(temps)

        for dd in results:
            assert not (dd.hdd > 0 and dd.cdd > 0), \
                f"HDD={dd.hdd}, CDD={dd.cdd} — 両方正になってはいけない"

    def test_custom_base_temp(self):
        """基準温度のカスタマイズ"""
        temps = [_make_temp("2024-01-15", 15.0)]

        # 基準温度20°Cの場合: HDD = 20 - 15 = 5
        result = calculate_daily_degree_days(temps, base_temp=20.0)
        assert result[0].hdd == pytest.approx(5.0, abs=0.01)
        assert result[0].cdd == 0.0

        # 基準温度10°Cの場合: CDD = 15 - 10 = 5
        result = calculate_daily_degree_days(temps, base_temp=10.0)
        assert result[0].hdd == 0.0
        assert result[0].cdd == pytest.approx(5.0, abs=0.01)


# ---------------------------------------------------------------------------
# 累積値テスト
# ---------------------------------------------------------------------------

class TestCumulative:
    """累積HDD/CDD値の検証"""

    def test_cumulative_sum(self):
        """累積値 = 日次値の単純合計"""
        temps = [
            _make_temp("2024-01-01", 0.0),   # HDD = 18.3
            _make_temp("2024-01-02", 5.0),   # HDD = 13.3
            _make_temp("2024-01-03", 10.0),  # HDD = 8.3
        ]
        daily = calculate_daily_degree_days(temps)
        cum_hdd, cum_cdd = calculate_cumulative(daily)

        expected_hdd = (18.3 - 0.0) + (18.3 - 5.0) + (18.3 - 10.0)
        assert cum_hdd == pytest.approx(expected_hdd, abs=0.1)
        assert cum_cdd == 0.0

    def test_mixed_hdd_cdd(self):
        """寒い日と暑い日が混在するケース"""
        temps = [
            _make_temp("2024-04-01", 10.0),  # HDD = 8.3
            _make_temp("2024-04-02", 25.0),  # CDD = 6.7
        ]
        daily = calculate_daily_degree_days(temps)
        cum_hdd, cum_cdd = calculate_cumulative(daily)

        assert cum_hdd == pytest.approx(18.3 - 10.0, abs=0.1)
        assert cum_cdd == pytest.approx(25.0 - 18.3, abs=0.1)


# ---------------------------------------------------------------------------
# 月次累積テスト
# ---------------------------------------------------------------------------

class TestMonthlyDegreeDays:
    """月次累積値の検証"""

    def test_monthly_aggregation(self):
        """月をまたぐデータが正しく月別に集計されること"""
        temps = [
            _make_temp("2024-01-30", 0.0),
            _make_temp("2024-01-31", 5.0),
            _make_temp("2024-02-01", 3.0),
        ]
        daily = calculate_daily_degree_days(temps)
        monthly = calculate_monthly_degree_days(daily)

        assert len(monthly) == 2

        jan = monthly[0]
        assert jan.year == 2024
        assert jan.month == 1
        assert jan.days_count == 2
        assert jan.hdd == pytest.approx((18.3 - 0.0) + (18.3 - 5.0), abs=0.1)

        feb = monthly[1]
        assert feb.year == 2024
        assert feb.month == 2
        assert feb.days_count == 1
        assert feb.hdd == pytest.approx(18.3 - 3.0, abs=0.1)
