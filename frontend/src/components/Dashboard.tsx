import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getTemperature,
  getMonthlyDegreeDays,
  getModelFit,
  postSimulation,
  postBurnAnalysis,
  postMonteCarlo,
} from "../services/api";
import TemperatureChart from "./TemperatureChart";
import DegreeDaysChart from "./DegreeDaysChart";
import SimulationFanChart from "./SimulationFanChart";
import PricingDistribution from "./PricingDistribution";
import InfoPopover from "./InfoPopover";

const CITIES: Record<string, string> = {
  "CITY:US170006": "Chicago, IL",
  "CITY:US360019": "New York, NY",
  "CITY:US260006": "Detroit, MI",
  "CITY:US130001": "Atlanta, GA",
};

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export default function Dashboard() {
  const [stationId, setStationId] = useState("CITY:US170006");
  const [ddType, setDdType] = useState<"hdd" | "cdd">("hdd");
  const [baseTemp, setBaseTemp] = useState(18.3);
  const [lambda, setLambda] = useState(0.0);
  const [nPaths, setNPaths] = useState(10000);
  const [targetMonth, setTargetMonth] = useState(1);
  const [strike, setStrike] = useState(500);

  // Compute seasonal values from model fit to overlay on temperature chart
  const computeSeasonalValues = (
    fit: { seasonal: { a: number; b: number; c1: number; d1: number; c2: number; d2: number } } | undefined,
    nPoints: number,
  ): number[] | undefined => {
    if (!fit) return undefined;
    const { a, b, c1, d1, c2, d2 } = fit.seasonal;
    return Array.from({ length: nPoints }, (_, i) =>
      a + b * i +
      c1 * Math.sin((2 * Math.PI * i) / 365) +
      d1 * Math.cos((2 * Math.PI * i) / 365) +
      c2 * Math.sin((4 * Math.PI * i) / 365) +
      d2 * Math.cos((4 * Math.PI * i) / 365),
    );
  };

  // --- Queries ---
  const tempQuery = useQuery({
    queryKey: ["temperature", stationId],
    queryFn: () => getTemperature(stationId),
    staleTime: 5 * 60_000,
  });

  const monthlyQuery = useQuery({
    queryKey: ["monthly-dd", stationId, baseTemp],
    queryFn: () => getMonthlyDegreeDays(stationId, undefined, undefined, baseTemp),
    staleTime: 5 * 60_000,
  });

  const modelQuery = useQuery({
    queryKey: ["model-fit", stationId],
    queryFn: () => getModelFit(stationId),
    staleTime: 5 * 60_000,
  });

  const simQuery = useQuery({
    queryKey: ["simulation", stationId, nPaths],
    queryFn: () => postSimulation(stationId, { n_days: 365, n_paths: nPaths, seed: 42 }),
    staleTime: 5 * 60_000,
  });

  const burnQuery = useQuery({
    queryKey: ["burn", stationId, targetMonth, ddType, baseTemp, strike],
    queryFn: () =>
      postBurnAnalysis(stationId, {
        start_month: targetMonth,
        end_month: targetMonth,
        dd_type: ddType,
        base_temp: baseTemp,
        strike,
      }),
    staleTime: 5 * 60_000,
  });

  const mcQuery = useQuery({
    queryKey: ["mc", stationId, targetMonth, ddType, baseTemp, strike, lambda, nPaths],
    queryFn: () =>
      postMonteCarlo(stationId, {
        target_month: targetMonth,
        dd_type: ddType,
        base_temp: baseTemp,
        strike,
        lambda_risk: lambda,
        n_paths: nPaths,
      }),
    staleTime: 5 * 60_000,
  });

  const isLoading =
    tempQuery.isLoading || monthlyQuery.isLoading || modelQuery.isLoading || simQuery.isLoading;

  const seasonalValues = computeSeasonalValues(modelQuery.data, tempQuery.data?.data.length ?? 0);

  // Guide text based on parameter changes
  const guideText = (() => {
    if (lambda > 0.3) return `λ=${lambda.toFixed(1)}: 高い正のリスクプレミアム → ${ddType === "hdd" ? "HDD先物が割高" : "CDD先物が割安"}に`;
    if (lambda < -0.3) return `λ=${lambda.toFixed(1)}: 負のリスクプレミアム → ${ddType === "hdd" ? "HDD先物が割安" : "CDD先物が割高"}に`;
    if (lambda === 0) return "λ=0: 実測度でのプライシング（リスクプレミアムなし）";
    return `λ=${lambda.toFixed(1)}: わずかなリスクプレミアム`;
  })();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <h1 className="text-lg font-bold text-gray-900">
            Climate Derivatives Pricing Dashboard
          </h1>
          <p className="text-xs text-gray-500 mt-0.5">
            HDD/CDD Futures & Options — Data → Modeling → Pricing
          </p>
        </div>
      </header>

      {/* Controls */}
      <div className="max-w-7xl mx-auto px-4 py-3">
        <div className="bg-white rounded-lg shadow p-4 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 text-sm">
          {/* City */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">City</label>
            <select
              value={stationId}
              onChange={(e) => setStationId(e.target.value)}
              className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
            >
              {Object.entries(CITIES).map(([id, name]) => (
                <option key={id} value={id}>{name}</option>
              ))}
            </select>
          </div>

          {/* DD Type */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Type</label>
            <select
              value={ddType}
              onChange={(e) => setDdType(e.target.value as "hdd" | "cdd")}
              className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
            >
              <option value="hdd">HDD (Heating)</option>
              <option value="cdd">CDD (Cooling)</option>
            </select>
          </div>

          {/* Target Month */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Target Month</label>
            <select
              value={targetMonth}
              onChange={(e) => setTargetMonth(Number(e.target.value))}
              className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
            >
              {MONTHS.map((m, i) => (
                <option key={i} value={i + 1}>{m}</option>
              ))}
            </select>
          </div>

          {/* Base Temp */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Base Temp: {baseTemp}°C
            </label>
            <input
              type="range" min="15" max="22" step="0.1" value={baseTemp}
              onChange={(e) => setBaseTemp(Number(e.target.value))}
              className="w-full"
            />
          </div>

          {/* Lambda */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              λ (Risk): {lambda.toFixed(2)}
              <InfoPopover title="Market Price of Risk (λ)">
                <p>不完全市場では唯一の「正しい価格」がない。</p>
                <p className="mt-1">λはリスク中立測度Qを決定するパラメータ。</p>
                <p className="mt-1">λ=0: 実測度 / λ&gt;0: HDD↑ / λ&lt;0: HDD↓</p>
              </InfoPopover>
            </label>
            <input
              type="range" min="-1" max="1" step="0.05" value={lambda}
              onChange={(e) => setLambda(Number(e.target.value))}
              className="w-full"
            />
          </div>

          {/* Strike */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Strike (K)</label>
            <input
              type="number" value={strike} min={0} step={50}
              onChange={(e) => setStrike(Number(e.target.value))}
              className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
            />
          </div>

          {/* Paths */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">MC Paths</label>
            <select
              value={nPaths}
              onChange={(e) => setNPaths(Number(e.target.value))}
              className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
            >
              {[1000, 5000, 10000, 20000, 50000].map((n) => (
                <option key={n} value={n}>{n.toLocaleString()}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Guide text */}
        <div className="mt-2 text-xs text-blue-700 bg-blue-50 rounded px-3 py-1.5">
          {guideText}
        </div>
      </div>

      {/* Loading indicator */}
      {isLoading && (
        <div className="max-w-7xl mx-auto px-4 py-2">
          <div className="text-sm text-gray-500 animate-pulse">Loading data...</div>
        </div>
      )}

      {/* Error display */}
      {(tempQuery.error || modelQuery.error) && (
        <div className="max-w-7xl mx-auto px-4 py-2">
          <div className="text-sm text-red-600 bg-red-50 rounded px-3 py-2">
            API Error: {String(tempQuery.error || modelQuery.error)}
            <br />
            <span className="text-xs">Make sure the backend is running: <code>uvicorn app.main:app --reload</code></span>
          </div>
        </div>
      )}

      {/* 4 Panel Grid */}
      <div className="max-w-7xl mx-auto px-4 pb-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-3">
          {/* Panel 1: Temperature */}
          {tempQuery.data && (
            <TemperatureChart
              data={tempQuery.data.data}
              seasonalValues={seasonalValues}
              baseTemp={baseTemp}
            />
          )}

          {/* Panel 2: Degree Days */}
          {monthlyQuery.data && (
            <DegreeDaysChart data={monthlyQuery.data} ddType={ddType} />
          )}

          {/* Panel 3: Simulation Fan Chart */}
          {simQuery.data && (
            <SimulationFanChart data={simQuery.data} />
          )}

          {/* Panel 4: Pricing */}
          <PricingDistribution
            burn={burnQuery.data ?? null}
            mc={mcQuery.data ?? null}
            ddType={ddType}
          />
        </div>

        {/* Model fit summary */}
        {modelQuery.data && (
          <div className="mt-4 bg-white rounded-lg shadow p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">
              Model Parameters
              <InfoPopover title="OU Process Parameters">
                <p>気温モデル: dT = κ(θ(t) - T)dt + σdW</p>
                <p className="mt-1"><strong>κ</strong>: 平均回帰速度。半減期 = ln2/κ 日</p>
                <p className="mt-1"><strong>σ</strong>: ボラティリティ。日々のランダムショック</p>
                <p className="mt-1"><strong>R²</strong>: 季節成分の説明力</p>
              </InfoPopover>
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
              <div className="bg-gray-50 rounded p-2">
                <div className="text-gray-500">κ (mean-reversion)</div>
                <div className="font-mono font-semibold">{modelQuery.data.ou.kappa.toFixed(4)}</div>
              </div>
              <div className="bg-gray-50 rounded p-2">
                <div className="text-gray-500">σ (volatility)</div>
                <div className="font-mono font-semibold">{modelQuery.data.ou.sigma.toFixed(4)}</div>
              </div>
              <div className="bg-gray-50 rounded p-2">
                <div className="text-gray-500">Half-life</div>
                <div className="font-mono font-semibold">{modelQuery.data.ou.half_life_days.toFixed(1)} days</div>
              </div>
              <div className="bg-gray-50 rounded p-2">
                <div className="text-gray-500">Stationary σ</div>
                <div className="font-mono font-semibold">{modelQuery.data.ou.stationary_std.toFixed(2)} °C</div>
              </div>
              <div className="bg-gray-50 rounded p-2">
                <div className="text-gray-500">R² (seasonal fit)</div>
                <div className="font-mono font-semibold">{(modelQuery.data.r_squared * 100).toFixed(1)}%</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
