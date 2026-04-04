"""
NOAAクライアントのテスト

実際のAPI呼び出しをモックして、パース処理やフォールバック機能を検証する。
"""

from datetime import date

import pytest

from app.services.noaa_client import _parse_results, generate_sample_data


# ---------------------------------------------------------------------------
# NOAA APIレスポンスのパース
# ---------------------------------------------------------------------------

class TestParseResults:
    """NOAA生データのパース処理を検証"""

    def test_parse_tmax_tmin_pair(self):
        """TMAX/TMINペアが正しくDailyTemperatureに変換されること"""
        raw = [
            {"date": "2024-01-15T00:00:00", "datatype": "TMAX", "value": 50},
            {"date": "2024-01-15T00:00:00", "datatype": "TMIN", "value": -30},
        ]
        result = _parse_results(raw)

        assert len(result) == 1
        assert result[0].date == date(2024, 1, 15)
        # 10分の1°C単位: 50 → 5.0°C, -30 → -3.0°C
        assert result[0].tmax == pytest.approx(5.0)
        assert result[0].tmin == pytest.approx(-3.0)
        assert result[0].tavg == pytest.approx(1.0)  # (5.0 + -3.0) / 2

    def test_skip_incomplete_records(self):
        """TMAXのみ or TMINのみのレコードはスキップされること"""
        raw = [
            {"date": "2024-01-15T00:00:00", "datatype": "TMAX", "value": 50},
            # TMINがない → この日はスキップ
            {"date": "2024-01-16T00:00:00", "datatype": "TMAX", "value": 80},
            {"date": "2024-01-16T00:00:00", "datatype": "TMIN", "value": 20},
        ]
        result = _parse_results(raw)

        assert len(result) == 1
        assert result[0].date == date(2024, 1, 16)

    def test_multiple_days(self):
        """複数日のデータが正しくパースされること"""
        raw = [
            {"date": "2024-07-01T00:00:00", "datatype": "TMAX", "value": 350},
            {"date": "2024-07-01T00:00:00", "datatype": "TMIN", "value": 220},
            {"date": "2024-07-02T00:00:00", "datatype": "TMAX", "value": 330},
            {"date": "2024-07-02T00:00:00", "datatype": "TMIN", "value": 200},
        ]
        result = _parse_results(raw)

        assert len(result) == 2
        assert result[0].tmax == pytest.approx(35.0)
        assert result[1].tmin == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# サンプルデータ生成（フォールバック）
# ---------------------------------------------------------------------------

class TestSampleData:
    """APIが使えない場合のフォールバックデータ検証"""

    def test_sample_data_length(self):
        """指定期間のデータが正しい日数分生成されること"""
        data = generate_sample_data(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )
        assert len(data) == 365

    def test_sample_data_seasonal_pattern(self):
        """サンプルデータが季節性を持つこと（夏 > 冬）"""
        data = generate_sample_data(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )

        # 1月（冬）と7月（夏）の平均を比較
        jan_avg = sum(d.tavg for d in data if d.date.month == 1) / 31
        jul_avg = sum(d.tavg for d in data if d.date.month == 7) / 31

        # シカゴ: 冬は寒く夏は暑い
        assert jul_avg > jan_avg
        assert jan_avg < 10  # 冬は10°C未満
        assert jul_avg > 20  # 夏は20°C超

    def test_sample_data_reasonable_range(self):
        """気温が現実的な範囲にあること"""
        data = generate_sample_data(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )

        for d in data:
            assert -40 < d.tavg < 50, f"非現実的な気温: {d.tavg}°C on {d.date}"
            assert d.tmax > d.tmin, f"TMAX <= TMIN on {d.date}"
