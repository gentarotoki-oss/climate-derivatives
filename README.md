# Climate Derivatives Pricing Dashboard

気温ベースの気候デリバティブ（HDD/CDD先物・オプション）の価格決定を、
データ取得 → モデリング → プライシング → 可視化 の一貫したパイプラインとして構築するプロジェクト。

## このプロジェクトで学べること

### 金融工学の概念
- **HDD/CDD (Heating/Cooling Degree Days)**: 気温リスクの定量化指標
- **Ornstein-Uhlenbeck過程**: 気温のような平均回帰する確率過程のモデリング
- **不完全市場 (Incomplete Market)**: 気温は取引不可 → リスク中立測度が一意でない
- **Market Price of Risk (λ)**: 実測度からリスク中立測度への変換
- **Burn Analysis**: 過去実績ベースのモデルフリーなプライシング
- **Monte Carlo法**: リスク中立測度下でのデリバティブ価格計算

### プログラミング・エンジニアリング
- **FastAPI** による非同期API設計
- **React + TypeScript + D3.js** によるインタラクティブダッシュボード
- **NumPy/SciPy** による数値計算・パラメータ推定
- **pytest** による金融計算ロジックのテスト
- 外部API (NOAA) との連携とレートリミット対応

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| Backend | Python, FastAPI, NumPy, SciPy |
| Frontend | React, TypeScript, D3.js, Vite |
| Data | NOAA Climate Data Online API |
| Testing | pytest, React Testing Library |

## セットアップ

### Backend
```bash
cd backend
pip install -e ".[dev]"
cp .env.example .env
# .env に NOAA_API_TOKEN を設定 (https://www.ncdc.noaa.gov/cdo-web/token)
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Notebooks
```bash
cd backend
pip install -e ".[notebook]"
cd ../notebooks
jupyter notebook
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/temperature/{station_id}` | 日次気温データ |
| GET | `/api/degree-days/{station_id}` | 日次HDD/CDD + 累積値 |
| GET | `/api/degree-days/{station_id}/monthly` | 月次HDD/CDD累積値 |

## ロードマップ

- [x] Step 1: 気温データ取得 & HDD/CDD計算
- [ ] Step 2: 気温の確率過程モデリング (OU過程)
- [ ] Step 3: HDD/CDD先物・オプションのプライシング
- [ ] Step 4: React + D3.js ダッシュボード
