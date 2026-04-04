"""
プライシングに関するPydanticスキーマ
"""

from pydantic import BaseModel, Field

from app.services.degree_days import DEFAULT_BASE_TEMP_C


# ---------------------------------------------------------------------------
# リクエスト
# ---------------------------------------------------------------------------

class BurnAnalysisRequest(BaseModel):
    """Burn Analysisのリクエスト"""
    start_month: int = Field(default=1, ge=1, le=12, description="対象期間の開始月")
    end_month: int = Field(default=1, ge=1, le=12, description="対象期間の終了月")
    dd_type: str = Field(default="hdd", pattern="^(hdd|cdd)$", description="hdd or cdd")
    base_temp: float = Field(default=DEFAULT_BASE_TEMP_C, description="基準温度 (°C)")
    strike: float = Field(default=0.0, ge=0, description="オプション行使価格 (0=先物のみ)")
    discount_factor: float = Field(default=1.0, gt=0, le=1, description="割引ファクター")
    decay_factor: float = Field(default=0.0, ge=0, le=1, description="重み付け減衰率 (0=等重み)")
    n_years: int = Field(default=10, ge=2, le=30, description="使用する過去年数")


class MonteCarloRequest(BaseModel):
    """Monte Carloプライシングのリクエスト"""
    target_month: int = Field(default=1, ge=1, le=12, description="プライシング対象月")
    dd_type: str = Field(default="hdd", pattern="^(hdd|cdd)$", description="hdd or cdd")
    base_temp: float = Field(default=DEFAULT_BASE_TEMP_C, description="基準温度 (°C)")
    strike: float = Field(default=0.0, ge=0, description="オプション行使価格")
    discount_factor: float = Field(default=1.0, gt=0, le=1, description="割引ファクター")
    lambda_risk: float = Field(
        default=0.0,
        description="Market Price of Risk. λ=0は実測度。"
        "不完全市場では唯一の正解がない。λは市場参加者のリスク許容度を反映する。",
    )
    n_paths: int = Field(default=10000, ge=100, le=100000, description="シミュレーションパス数")
    seed: int | None = Field(default=None, description="乱数シード")


# ---------------------------------------------------------------------------
# レスポンス
# ---------------------------------------------------------------------------

class BurnAnalysisResponse(BaseModel):
    """Burn Analysis結果"""
    station_id: str
    dd_type: str
    period: str = Field(..., description="対象期間 (例: 'January')")
    futures_price: float = Field(..., description="先物価格（単純平均）")
    futures_price_weighted: float = Field(..., description="先物価格（重み付き平均）")
    std: float = Field(..., description="ヒストリカル標準偏差")
    confidence_interval_95: list[float] = Field(..., description="95%信頼区間 [lower, upper]")
    call_price: float = Field(default=0.0, description="コールオプション価格")
    put_price: float = Field(default=0.0, description="プットオプション価格")
    strike: float
    historical_values: list[float]
    historical_years: list[int]


class MonteCarloPricingResponse(BaseModel):
    """Monte Carlo結果"""
    station_id: str
    dd_type: str
    period: str
    futures_price: float = Field(..., description="先物価格 E^Q[Σ DD]")
    futures_se: float = Field(..., description="標準誤差")
    call_price: float
    call_se: float
    put_price: float
    put_se: float
    strike: float
    lambda_risk: float
    n_paths: int
    distribution_percentiles: dict[str, float] = Field(
        ..., description="累積DD分布のパーセンタイル"
    )
