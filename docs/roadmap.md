# Development Roadmap

## Step 1: 気温データ取得 & HDD/CDD計算 ✅
- NOAA CDO API クライアント（レートリミット対応、フォールバック付き）
- HDD/CDD計算サービス（日次・月次累積）
- FastAPI エンドポイント
- Jupyter Notebook (01_temperature_eda.ipynb)
- pytest テスト

## Step 2: 気温の確率過程モデリング
- 季節成分のフーリエ級数フィット
- Ornstein-Uhlenbeck過程のパラメータ推定
- Euler-Maruyama法による気温パスシミュレーション
- Jupyter Notebook (03_ou_process.ipynb)

## Step 3: プライシング
- Burn Analysis（ヒストリカルプライシング）
- Monte Carlo プライシング（リスク中立測度下）
- Market Price of Risk (λ) のパラメータ化
- 先物・オプション価格計算

## Step 4: フロントエンド
- React + TypeScript + D3.js ダッシュボード
- 気温時系列、HDD/CDD累積、シミュレーションFan Chart
- λスライダーによるインタラクティブプライシング
