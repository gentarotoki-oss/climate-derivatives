"""
気温モデル（季節成分 + OU過程）に関するPydanticスキーマ
"""

from pydantic import BaseModel, Field


class SeasonalParamsSchema(BaseModel):
    """季節成分 θ(t) = a + b*t + c1*sin + d1*cos + c2*sin + d2*cos"""
    a: float = Field(..., description="定数項（年平均気温のベースライン °C）")
    b: float = Field(..., description="線形トレンド（°C/日）")
    c1: float = Field(..., description="sin(年周期) の係数")
    d1: float = Field(..., description="cos(年周期) の係数")
    c2: float = Field(..., description="sin(半年周期) の係数")
    d2: float = Field(..., description="cos(半年周期) の係数")
    amplitude: float = Field(..., description="年周期の振幅 √(c1² + d1²)")


class OUParamsSchema(BaseModel):
    """Ornstein-Uhlenbeck 過程のパラメータ"""
    kappa: float = Field(..., description="平均回帰速度 (1/日)")
    sigma: float = Field(..., description="ボラティリティ (°C/√日)")
    kappa_se: float = Field(..., description="κの標準誤差")
    sigma_se: float = Field(..., description="σの標準誤差")
    half_life_days: float = Field(..., description="偏差の半減期 (日)")
    stationary_std: float = Field(..., description="定常標準偏差 (°C)")


class ModelFitResponse(BaseModel):
    """モデルフィット結果のAPIレスポンス"""
    station_id: str
    n_observations: int
    seasonal: SeasonalParamsSchema
    ou: OUParamsSchema
    residual_mean: float
    residual_std: float
    r_squared: float = Field(..., description="季節成分のR² (説明力)")


class SimulationRequest(BaseModel):
    """シミュレーションのリクエストパラメータ"""
    n_days: int = Field(default=365, ge=1, le=3650, description="シミュレーション日数")
    n_paths: int = Field(default=1000, ge=10, le=50000, description="パス数")
    seed: int | None = Field(default=None, description="乱数シード")


class SimulationResponse(BaseModel):
    """シミュレーション結果のAPIレスポンス"""
    station_id: str
    n_days: int
    n_paths: int
    percentiles: dict[str, list[float]] = Field(
        ..., description="パーセンタイル (p5, p25, p50, p75, p95)"
    )
    mean: list[float]
    seasonal: list[float] = Field(..., description="季節成分の値")
    dates_offset: list[int] = Field(..., description="開始日からのオフセット日数")
