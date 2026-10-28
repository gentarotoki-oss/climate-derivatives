"""
気温モデル（季節成分 + OU過程）のテスト

合成データ（既知のパラメータ）を使い、推定が正しく収束するか検証する。
金融モデルのテストでは「パラメータ回復テスト」が基本。
"""

import numpy as np
import pytest

from app.models.temperature import (
    OUParams,
    SeasonalParams,
    fit_ou,
    fit_seasonal,
    fit_temperature_model,
    simulate_temperature_paths,
)


# ---------------------------------------------------------------------------
# 季節成分のテスト
# ---------------------------------------------------------------------------

class TestSeasonalFit:
    """季節成分 θ(t) のフィット精度を検証"""

    def test_recover_known_parameters(self):
        """既知のパラメータで生成したデータから、元のパラメータを回復できるか"""
        true_params = SeasonalParams(a=10.0, b=0.001, c1=5.0, d1=-12.0, c2=1.0, d2=-0.5)

        t = np.arange(0, 365 * 3, dtype=np.float64)  # 3年分
        y = true_params.evaluate(t)

        fitted = fit_seasonal(t, y)

        assert fitted.a == pytest.approx(true_params.a, abs=0.1)
        assert fitted.b == pytest.approx(true_params.b, abs=0.0001)
        assert fitted.c1 == pytest.approx(true_params.c1, abs=0.1)
        assert fitted.d1 == pytest.approx(true_params.d1, abs=0.1)

    def test_noisy_data(self):
        """ノイズ付きデータでも主要パラメータが回復できるか"""
        rng = np.random.default_rng(42)
        true_params = SeasonalParams(a=10.0, b=0.0, c1=0.0, d1=-15.0, c2=0.0, d2=0.0)

        t = np.arange(0, 365 * 5, dtype=np.float64)
        y = true_params.evaluate(t) + rng.normal(0, 3.0, len(t))

        fitted = fit_seasonal(t, y)

        # ノイズがあっても振幅と平均は回復できるはず
        assert fitted.a == pytest.approx(true_params.a, abs=0.5)
        assert fitted.d1 == pytest.approx(true_params.d1, abs=1.0)


# ---------------------------------------------------------------------------
# OU過程パラメータ推定のテスト
# ---------------------------------------------------------------------------

class TestOUFit:
    """OU過程のパラメータ推定を検証"""

    def test_recover_kappa_sigma(self):
        """
        合成OU過程データから κ, σ を回復する。

        テスト戦略:
        - 既知の κ=0.3, σ=3.0 でパスを生成
        - 十分長いパス（10年分）なら推定が収束するはず
        """
        rng = np.random.default_rng(123)
        true_kappa = 0.3
        true_sigma = 3.0

        n = 365 * 10  # 10年分
        dt = 1.0
        x = np.zeros(n)
        for i in range(n - 1):
            x[i + 1] = x[i] - true_kappa * x[i] * dt + true_sigma * np.sqrt(dt) * rng.normal()

        result = fit_ou(x, dt=dt)

        # κ: 10%以内の誤差を許容
        assert result.kappa == pytest.approx(true_kappa, rel=0.15)
        # σ: 10%以内の誤差を許容
        assert result.sigma == pytest.approx(true_sigma, rel=0.10)

    def test_half_life(self):
        """半減期の計算が正しいか"""
        params = OUParams(kappa=0.3, sigma=3.0)
        expected_half_life = np.log(2) / 0.3
        assert params.half_life == pytest.approx(expected_half_life, abs=0.01)

    def test_stationary_variance(self):
        """定常分散の計算が正しいか"""
        params = OUParams(kappa=0.3, sigma=3.0)
        expected_var = 3.0**2 / (2 * 0.3)
        assert params.stationary_variance == pytest.approx(expected_var, abs=0.01)

    def test_too_few_data_points(self):
        """データ点が少なすぎる場合はエラー"""
        with pytest.raises(ValueError, match="最低10データポイント"):
            fit_ou(np.array([1.0, 2.0, 3.0]))


# ---------------------------------------------------------------------------
# 統合フィットのテスト
# ---------------------------------------------------------------------------

class TestIntegratedFit:
    """季節成分 + OU過程の統合フィットを検証"""

    def test_r_squared_reasonable(self):
        """サンプルデータで R² が合理的な範囲にあるか"""
        rng = np.random.default_rng(42)
        t = np.arange(0, 365 * 3, dtype=np.float64)

        # 季節成分 + OU残差で合成データを作成
        seasonal = 10.0 - 15.0 * np.cos(2 * np.pi * t / 365)
        noise = rng.normal(0, 3.0, len(t))
        temperatures = seasonal + noise

        result = fit_temperature_model(t, temperatures)

        # 季節成分が支配的なので R² は高いはず
        assert result.r_squared > 0.8


# ---------------------------------------------------------------------------
# シミュレーションのテスト
# ---------------------------------------------------------------------------

class TestSimulation:
    """モンテカルロシミュレーションの統計的性質を検証"""

    def test_simulation_shape(self):
        """出力の形状が正しいか"""
        seasonal = SeasonalParams(a=10.0, b=0.0, c1=0.0, d1=-15.0, c2=0.0, d2=0.0)
        ou = OUParams(kappa=0.3, sigma=3.0)

        paths = simulate_temperature_paths(
            seasonal=seasonal, ou=ou,
            t_start=0.0, n_days=100, n_paths=500, seed=42,
        )
        assert paths.shape == (500, 100)

    def test_mean_converges_to_seasonal(self):
        """
        十分なパス数で、平均パスは季節成分に収束するはず。

        OU過程の期待値: E[X_t] → θ(t) (t→∞ or 多数パスの平均)
        """
        seasonal = SeasonalParams(a=15.0, b=0.0, c1=0.0, d1=-10.0, c2=0.0, d2=0.0)
        ou = OUParams(kappa=0.5, sigma=2.0)

        paths = simulate_temperature_paths(
            seasonal=seasonal, ou=ou,
            t_start=0.0, n_days=365, n_paths=10000, seed=42,
        )

        # 後半（初期値の影響が薄れた部分）で確認
        t_check = np.arange(0.0, 365.0)
        theta = seasonal.evaluate(t_check)
        path_mean = np.mean(paths, axis=0)

        # 後半180日のRMSEが小さいことを確認
        rmse = np.sqrt(np.mean((path_mean[180:] - theta[180:])**2))
        assert rmse < 1.0, f"RMSE = {rmse:.2f} — 平均が季節成分に収束していない"

    def test_mean_tracks_seasonal_without_lag(self):
        """
        平均パスは季節成分 θ(t) に遅れずについて行くはず。

        dθ の項がないと、平均は θ(t) より約 θ'(t)/κ 遅れる。
        この設定では θ' の最大値が 10·2π/365 ≈ 0.17 °C/日 なので、
        遅れは最大 0.7 °C ほどになる。
        """
        seasonal = SeasonalParams(a=12.0, b=0.0, c1=0.0, d1=-10.0, c2=0.0, d2=0.0)
        ou = OUParams(kappa=0.25, sigma=2.5)

        paths = simulate_temperature_paths(
            seasonal=seasonal, ou=ou,
            t_start=0.0, n_days=365, n_paths=20000, seed=42,
        )

        theta = seasonal.evaluate(np.arange(0.0, 365.0))
        max_err = np.max(np.abs(np.mean(paths, axis=0) - theta))
        assert max_err < 0.2, f"max |E[T] - θ| = {max_err:.2f} — 平均が季節成分から遅れている"

    def test_lambda_shifts_mean_by_lambda_sigma_over_kappa(self):
        """
        Q測度下では、残差の平均が -λσ/κ に収束する。
        平均パスは θ(t) - λσ/κ について行くはず。
        """
        seasonal = SeasonalParams(a=12.0, b=0.0, c1=0.0, d1=-10.0, c2=0.0, d2=0.0)
        ou = OUParams(kappa=0.25, sigma=2.5)
        lam = 0.2

        paths = simulate_temperature_paths(
            seasonal=seasonal, ou=ou,
            t_start=0.0, n_days=365, n_paths=20000, seed=42,
            lambda_risk=lam,
        )

        theta = seasonal.evaluate(np.arange(0.0, 365.0))
        expected_shift = -lam * ou.sigma / ou.kappa  # = -2.0 °C
        # 初期値の影響が消えた後半で確認
        shift = np.mean(paths[:, 180:], axis=0) - theta[180:]
        assert np.max(np.abs(shift - expected_shift)) < 0.2

    def test_variance_matches_theory(self):
        """
        定常状態でのシミュレーション分散が理論値 σ²/(2κ) に近いか。
        """
        seasonal = SeasonalParams(a=10.0, b=0.0, c1=0.0, d1=0.0, c2=0.0, d2=0.0)
        ou = OUParams(kappa=0.3, sigma=3.0)
        theoretical_var = ou.stationary_variance

        paths = simulate_temperature_paths(
            seasonal=seasonal, ou=ou,
            t_start=0.0, n_days=500, n_paths=10000,
            T_initial=10.0, seed=42,
        )

        # 十分時間が経った時点での分散
        empirical_var = np.var(paths[:, -1])

        assert empirical_var == pytest.approx(theoretical_var, rel=0.25), \
            f"Empirical={empirical_var:.2f}, Theory={theoretical_var:.2f}"

    def test_seed_reproducibility(self):
        """同じシードなら同じ結果"""
        seasonal = SeasonalParams(a=10.0, b=0.0, c1=0.0, d1=-15.0, c2=0.0, d2=0.0)
        ou = OUParams(kappa=0.3, sigma=3.0)

        p1 = simulate_temperature_paths(seasonal=seasonal, ou=ou,
                                         t_start=0.0, n_days=30, n_paths=10, seed=99)
        p2 = simulate_temperature_paths(seasonal=seasonal, ou=ou,
                                         t_start=0.0, n_days=30, n_paths=10, seed=99)
        np.testing.assert_array_equal(p1, p2)
