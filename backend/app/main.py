"""
気候デリバティブ プライシングダッシュボード — FastAPI エントリポイント

このアプリケーションは、気温ベースの気候デリバティブ（HDD/CDD先物・オプション）の
価格決定を支援するAPIを提供する。

パイプライン:
  1. 気温データ取得 (NOAA CDO API)
  2. HDD/CDD計算
  3. 気温モデリング (OU過程)
  4. プライシング (Burn Analysis, Monte Carlo)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import degree_days, model, pricing, temperature

app = FastAPI(
    title="Climate Derivatives Pricing API",
    description="気温ベース気候デリバティブのプライシングダッシュボード",
    version="0.1.0",
)

# CORS設定（フロントエンド開発用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite default
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーター登録
app.include_router(temperature.router)
app.include_router(degree_days.router)
app.include_router(model.router)
app.include_router(pricing.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": "Climate Derivatives Pricing API",
        "docs": "/docs",
    }
