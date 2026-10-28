# Climate Derivatives Pricing

End-to-end pricing of temperature derivatives (HDD/CDD futures and options): NOAA data ingestion, a seasonal Ornstein-Uhlenbeck temperature model, Burn Analysis and Monte Carlo pricing, and an interactive dashboard.

<!-- TODO: ダッシュボードのスクリーンショットか GIF を docs/ に置いて貼る -->
<!-- ![Dashboard](docs/dashboard.png) -->

## Why this problem

Temperature cannot be traded, so a temperature derivative cannot be delta-hedged with its underlying. The market is incomplete, and the risk-neutral measure is not unique. This project makes that choice explicit: the market price of risk λ is a parameter, and the dashboard shows how prices move with it.

## Model

**Temperature.** Daily mean temperature is a deterministic seasonal mean plus a mean-reverting residual:

```
θ(t) = a + b·t + c1·sin(2πt/365) + d1·cos(2πt/365) + c2·sin(4πt/365) + d2·cos(4πt/365)
dX_t = -κ X_t dt + σ dW_t,   X_t = T_t - θ(t)
```

- θ(t) is fitted by least squares (linear trend + annual and semi-annual harmonics).
- κ and σ are estimated from the AR(1) regression of the residuals, with standard errors.

Because the model is on the residual, the temperature SDE carries the slope of the seasonal mean: dT = dθ(t) + κ(θ(t) - T)dt + σdW (Dornier and Queruel, 2000). Dropping dθ makes simulated temperatures lag θ(t) by about θ'(t)/κ. An earlier version had this bug; fixing it moved shoulder-season prices by more than 10% (see below).

**Change of measure.** Under Q the Brownian motion is shifted by λ (Girsanov), which adds a constant drift of -λσ.

**Pricing.**

| Method | Idea | Pros / cons |
|---|---|---|
| Burn Analysis | Average payoff over past seasons (optionally exponentially weighted) | Model-free; few data points, ignores trend and λ |
| Monte Carlo | Simulate temperature paths under Q, accumulate HDD/CDD, average discounted payoffs | Uses the full model and λ; subject to model risk |

Monte Carlo results are reported with standard errors.

## Results

### Effect of the dθ/dt term

`scripts/compare_seasonal_drift.py` prices futures (λ = 0, 200,000 paths) on a synthetic seasonal model (θ amplitude 10 °C, κ = 0.25, σ = 2.5) and compares them with an exact-transition reference.

| Contract | Reference | Without dθ/dt | With dθ/dt |
|---|---:|---:|---:|
| HDD Nov–Mar | 2038.4 | 2054.8 (+0.8%) | 2038.6 (+0.0%) |
| HDD April | 130.1 | 146.5 (+12.5%) | 131.7 (+1.2%) |
| CDD Jun–Aug | 277.5 | 290.8 (+4.8%) | 284.3 (+2.5%) |
| CDD September | 8.8 | 13.7 (+55.8%) | 10.6 (+20.7%) |

Max lag of the mean path behind θ(t): 0.74 °C → 0.08 °C. The remaining gap comes from Euler-Maruyama's variance inflation (see next steps).

<!-- TODO: notebooks の結果から実際の値を入れる。例:
- 対象: 観測所、期間（例: 2000–2024 年の冬季）
- 推定値: κ、σ、半減期、季節成分の R²
- 先物価格: Burn Analysis と Monte Carlo（λ = 0）の比較
- λ を変えたときの先物・オプション価格の感応度（図）
-->

## Architecture

```
NOAA CDO API ─▶ FastAPI backend (data, model fitting, pricing) ─▶ React + D3 dashboard
                     │
                     └─ notebooks/ (EDA, OU fitting, pricing experiments)
```

| Layer | Stack |
|---|---|
| Backend | Python, FastAPI, NumPy, SciPy, pandas |
| Frontend | React, TypeScript, D3.js, Vite, Tailwind CSS |
| Data | NOAA Climate Data Online API |
| Tests | pytest (degree days, temperature model, pricing, API client) |

## Getting started

```bash
# Backend
cd backend
pip install -e ".[dev]"
cp .env.example .env      # set NOAA_API_TOKEN (https://www.ncdc.noaa.gov/cdo-web/token)
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# Tests
cd backend
pytest
```

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/temperature/{station_id}` | Daily temperature |
| GET | `/api/degree-days/{station_id}` | Daily and cumulative HDD/CDD |
| GET | `/api/degree-days/{station_id}/monthly` | Monthly HDD/CDD |

<!-- TODO: model / pricing ルーターのエンドポイントも追記する -->

## Limitations and next steps

- **Exact discretization.** The OU residual has an exact Gaussian transition (φ = e^{-κΔt}); using it instead of Euler-Maruyama removes the remaining discretization bias (Euler inflates the stationary variance by 1/(1 - κ/2)), and κ should then be estimated as -ln φ.
- **Seasonal volatility.** σ is constant; temperature volatility is known to vary by season.
- **Calibrating λ.** Back out implied λ from quoted CME HDD/CDD futures instead of setting it by hand.
- **Variance reduction.** Antithetic variates or Burn Analysis as a control variate.
- **Backtesting.** Compare model forecasts with realized seasonal HDD/CDD out of sample.

## References

- Alaton, Djehiche and Stillberger (2002), *On modelling and pricing weather derivatives*
- Benth and Šaltytė Benth (2007), *The volatility of temperature and pricing of weather derivatives*
- Dornier and Queruel (2000), *Caution to the wind*
