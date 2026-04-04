/**
 * バックエンドAPI呼び出しの型定義とフェッチ関数
 */

const BASE = "/api";

// ---------------------------------------------------------------------------
// 型定義
// ---------------------------------------------------------------------------

export interface DailyTemperature {
  date: string;
  tmax: number;
  tmin: number;
  tavg: number;
}

export interface TemperatureResponse {
  station_id: string;
  station_name: string | null;
  unit: string;
  data: DailyTemperature[];
}

export interface DailyDegreeDays {
  date: string;
  tavg: number;
  hdd: number;
  cdd: number;
}

export interface DegreeDaysResponse {
  station_id: string;
  base_temp: number;
  data: DailyDegreeDays[];
  cumulative_hdd: number;
  cumulative_cdd: number;
}

export interface MonthlyDegreeDays {
  year: number;
  month: number;
  hdd: number;
  cdd: number;
  days_count: number;
}

export interface ModelFitResponse {
  station_id: string;
  n_observations: number;
  seasonal: {
    a: number;
    b: number;
    c1: number;
    d1: number;
    c2: number;
    d2: number;
    amplitude: number;
  };
  ou: {
    kappa: number;
    sigma: number;
    kappa_se: number;
    sigma_se: number;
    half_life_days: number;
    stationary_std: number;
  };
  residual_mean: number;
  residual_std: number;
  r_squared: number;
}

export interface SimulationResponse {
  station_id: string;
  n_days: number;
  n_paths: number;
  percentiles: Record<string, number[]>;
  mean: number[];
  seasonal: number[];
  dates_offset: number[];
}

export interface BurnAnalysisResponse {
  station_id: string;
  dd_type: string;
  period: string;
  futures_price: number;
  futures_price_weighted: number;
  std: number;
  confidence_interval_95: [number, number];
  call_price: number;
  put_price: number;
  strike: number;
  historical_values: number[];
  historical_years: number[];
}

export interface MonteCarloPricingResponse {
  station_id: string;
  dd_type: string;
  period: string;
  futures_price: number;
  futures_se: number;
  call_price: number;
  call_se: number;
  put_price: number;
  put_se: number;
  strike: number;
  lambda_risk: number;
  n_paths: number;
  distribution_percentiles: Record<string, number>;
}

// ---------------------------------------------------------------------------
// フェッチ関数
// ---------------------------------------------------------------------------

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, init);
  if (!resp.ok) throw new Error(`API Error ${resp.status}: ${resp.statusText}`);
  return resp.json();
}

export function getTemperature(
  stationId: string,
  startDate?: string,
  endDate?: string,
): Promise<TemperatureResponse> {
  const params = new URLSearchParams();
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);
  return fetchJson(`${BASE}/temperature/${stationId}?${params}`);
}

export function getDegreeDays(
  stationId: string,
  startDate?: string,
  endDate?: string,
  baseTemp?: number,
): Promise<DegreeDaysResponse> {
  const params = new URLSearchParams();
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);
  if (baseTemp !== undefined) params.set("base_temp", String(baseTemp));
  return fetchJson(`${BASE}/degree-days/${stationId}?${params}`);
}

export function getMonthlyDegreeDays(
  stationId: string,
  startDate?: string,
  endDate?: string,
  baseTemp?: number,
): Promise<MonthlyDegreeDays[]> {
  const params = new URLSearchParams();
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);
  if (baseTemp !== undefined) params.set("base_temp", String(baseTemp));
  return fetchJson(`${BASE}/degree-days/${stationId}/monthly?${params}`);
}

export function getModelFit(
  stationId: string,
  startDate?: string,
  endDate?: string,
): Promise<ModelFitResponse> {
  const params = new URLSearchParams();
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);
  return fetchJson(`${BASE}/model/fit/${stationId}?${params}`);
}

export function postSimulation(
  stationId: string,
  body: { n_days?: number; n_paths?: number; seed?: number },
  startDate?: string,
  endDate?: string,
): Promise<SimulationResponse> {
  const params = new URLSearchParams();
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);
  return fetchJson(`${BASE}/model/simulate/${stationId}?${params}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function postBurnAnalysis(
  stationId: string,
  body: {
    start_month: number;
    end_month: number;
    dd_type: string;
    base_temp: number;
    strike: number;
    n_years?: number;
    decay_factor?: number;
  },
): Promise<BurnAnalysisResponse> {
  return fetchJson(`${BASE}/pricing/burn-analysis/${stationId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function postMonteCarlo(
  stationId: string,
  body: {
    target_month: number;
    dd_type: string;
    base_temp: number;
    strike: number;
    lambda_risk: number;
    n_paths: number;
    seed?: number;
  },
): Promise<MonteCarloPricingResponse> {
  return fetchJson(`${BASE}/pricing/monte-carlo/${stationId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
