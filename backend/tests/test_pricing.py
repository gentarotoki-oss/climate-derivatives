"""
プライシングモデルのテスト

Burn Analysis の計算検証、Monte Carlo の収束性、
λ=0 での整合性チェックを行う。
"""

import numpy as np
import pytest

from app.models.pricing import burn_analysis, monte_carlo_pricing
from app.models.temperature import SeasonalParams, OUParams


# ---------------------------------------------------------------------------
# Burn Analysis テスト
# ---------------------------------------------------------------------------

class TestBurnAnalysis:
    """Burn Analysisの計算検証"""

    def test_simple_average(self):
        """単純平均の先物価格"""
        data = {2020: 100.0, 2021: 120.0, 2022: 110.0}
        result = burn_analysis(data)
        assert result.futures_price == pytest.approx(110.0, abs=0.01)

    def test_weighted_average(self):
        """重み付き平均は最近の年を重視する"""
        data = {2019: 100.0, 2020: 100.0, 2021: 100.0, 2022: 200.0}
        result = burn_analysis(data, decay_factor=0.5)
        # 2022年 (200) の重みが大きいので、単純平均 (125) より大きいはず
        assert result.futures_price_weighted > result.futures_price

    def test_call_option_itm(self):
        """In-the-moneyのコールオプション"""
        # 全年のHDDが100以上 → strike=50なら全てITM
        data = {2020: 100.0, 2021: 120.0, 2022: 110.0}
        result = burn_analysis(data, strike=50.0)
        # call = avg(max(v - 50, 0)) = avg(50, 70, 60) = 60
        assert result.call_price == pytest.approx(60.0, abs=0.01)

    def test_put_option_otm(self):
        """Out-of-the-moneyのプットオプション"""
        # 全年のHDDが100以上 → strike=50なら全てOTM
        data = {2020: 100.0, 2021: 120.0, 2022: 110.0}
        result = burn_analysis(data, strike=50.0)
        assert result.put_price == 0.0

    def test_call_put_mixed(self):
        """strike が分布の中にある場合"""
        data = {2020: 80.0, 2021: 120.0, 2022: 100.0}
        result = burn_analysis(data, strike=100.0)
        # call: max(80-100,0) + max(120-100,0) + max(100-100,0) = 0 + 20 + 0 = 20/3
        assert result.call_price == pytest.approx(20.0 / 3, abs=0.01)
        # put: max(100-80,0) + max(100-120,0) + max(100-100,0) = 20 + 0 + 0 = 20/3
        assert result.put_price == pytest.approx(20.0 / 3, abs=0.01)

    def test_confidence_interval(self):
        """信頼区間が平均を含むこと"""
        data = {y: 100.0 + y % 5 * 10 for y in range(2015, 2023)}
        result = burn_analysis(data)
        ci_low, ci_high = result.confidence_interval
        assert ci_low < result.futures_price < ci_high

    def test_discount_factor(self):
        """割引ファクターがオプション価格に適用されること"""
        data = {2020: 100.0, 2021: 120.0, 2022: 110.0}
        result_no_disc = burn_analysis(data, strike=50.0, discount_factor=1.0)
        result_disc = burn_analysis(data, strike=50.0, discount_factor=0.95)
        assert result_disc.call_price < result_no_disc.call_price
        assert result_disc.call_price == pytest.approx(
            result_no_disc.call_price * 0.95, abs=0.01
        )

    def test_empty_data_raises(self):
        """空データでエラー"""
        with pytest.raises(ValueError, match="空"):
            burn_analysis({})


# ---------------------------------------------------------------------------
# Monte Carlo プライシング テスト
# ---------------------------------------------------------------------------

# テスト用の固定パラメータ
_seasonal = SeasonalParams(a=10.0, b=0.0, c1=0.0, d1=-15.0, c2=0.0, d2=0.0)
_ou = OUParams(kappa=0.3, sigma=3.0)


class TestMonteCarloPricing:
    """Monte Carloプライシングの検証"""

    def test_futures_price_positive(self):
        """先物価格は正"""
        result = monte_carlo_pricing(
            seasonal=_seasonal, ou=_ou,
            t_start=0.0, n_days=31, T_initial=-5.0,
            dd_type="hdd", strike=0.0,
            n_paths=5000, seed=42,
        )
        assert result.futures_price > 0

    def test_standard_error_decreases_with_paths(self):
        """パス数を増やすと標準誤差が減少する"""
        se_values = []
        for n in [1000, 5000, 20000]:
            result = monte_carlo_pricing(
                seasonal=_seasonal, ou=_ou,
                t_start=0.0, n_days=31, T_initial=-5.0,
                dd_type="hdd", n_paths=n, seed=42,
            )
            se_values.append(result.futures_se)

        # SE は 1/√n に比例 → パスが増えれば減る
        assert se_values[0] > se_values[1] > se_values[2]

    def test_lambda_zero_is_physical_measure(self):
        """λ=0 は実測度でのプライシングに対応"""
        result_lam0 = monte_carlo_pricing(
            seasonal=_seasonal, ou=_ou,
            t_start=0.0, n_days=31, T_initial=-5.0,
            dd_type="hdd", lambda_risk=0.0,
            n_paths=10000, seed=42,
        )
        # λ=0 の先物価格は正のHDD値であるべき
        assert result_lam0.futures_price > 0

    def test_lambda_effect_on_hdd(self):
        """
        λの効果: HDD先物の場合

        λ > 0 → Q測度でドリフトが下方シフト → 気温が低めに
        → HDD = max(T_base - T, 0) は増加 → HDD先物価格が上がる

        λ < 0 → 逆の効果 → HDD先物価格が下がる
        """
        # 冬月（t_start=0, 低い初期気温）でテスト
        results = {}
        for lam in [-0.5, 0.0, 0.5]:
            r = monte_carlo_pricing(
                seasonal=_seasonal, ou=_ou,
                t_start=0.0, n_days=31, T_initial=-5.0,
                dd_type="hdd", lambda_risk=lam,
                n_paths=20000, seed=42,
            )
            results[lam] = r.futures_price

        # λ > 0 → 気温下がる → HDD上がる
        assert results[0.5] > results[0.0]
        # λ < 0 → 気温上がる → HDD下がる
        assert results[-0.5] < results[0.0]

    def test_call_put_parity_like(self):
        """
        コール-プットの整合性チェック。

        C - P = (Futures - K) * df  (先物のcall-put parity)
        """
        K = 500.0
        df = 0.99
        result = monte_carlo_pricing(
            seasonal=_seasonal, ou=_ou,
            t_start=0.0, n_days=31, T_initial=-5.0,
            dd_type="hdd", strike=K, discount_factor=df,
            n_paths=50000, seed=42,
        )

        # C - P ≈ (F - K) * df （MC誤差を許容）
        lhs = result.call_price - result.put_price
        rhs = (result.futures_price - K) * df
        assert lhs == pytest.approx(rhs, abs=5.0)  # MC誤差を考慮

    def test_cdd_in_summer(self):
        """夏月のCDDが正の値を返すこと"""
        result = monte_carlo_pricing(
            seasonal=_seasonal, ou=_ou,
            t_start=180.0, n_days=31, T_initial=25.0,
            dd_type="cdd",
            n_paths=5000, seed=42,
        )
        assert result.futures_price > 0

    def test_distribution_shape(self):
        """分布の長さがn_pathsと一致"""
        result = monte_carlo_pricing(
            seasonal=_seasonal, ou=_ou,
            t_start=0.0, n_days=31, T_initial=-5.0,
            dd_type="hdd", n_paths=1000, seed=42,
        )
        assert len(result.distribution) == 1000
