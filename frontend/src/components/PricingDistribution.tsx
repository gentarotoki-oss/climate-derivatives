import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { BurnAnalysisResponse, MonteCarloPricingResponse } from "../services/api";
import { useChartDimensions } from "../hooks/useChartDimensions";
import InfoPopover from "./InfoPopover";

interface Props {
  burn: BurnAnalysisResponse | null;
  mc: MonteCarloPricingResponse | null;
  ddType: "hdd" | "cdd";
}

export default function PricingDistribution({ burn, mc, ddType }: Props) {
  const [containerRef, dims] = useChartDimensions({
    marginTop: 20,
    marginRight: 20,
    marginBottom: 40,
    marginLeft: 55,
  });
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || (!burn && !mc)) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    // Build histogram from burn historical values
    const burnVals = burn?.historical_values ?? [];


    // Use burn historical data as bars
    if (burnVals.length > 0) {
      const x = d3
        .scaleLinear()
        .domain([
          d3.min(burnVals)! * 0.85,
          d3.max(burnVals)! * 1.15,
        ])
        .range([dims.marginLeft, dims.marginLeft + dims.innerWidth]);

      const bins = d3.bin().domain(x.domain() as [number, number]).thresholds(12)(burnVals);

      const y = d3
        .scaleLinear()
        .domain([0, d3.max(bins, (b) => b.length)! * 1.2])
        .range([dims.marginTop + dims.innerHeight, dims.marginTop]);

      const g = svg.append("g");

      // Histogram bars
      g.selectAll("rect")
        .data(bins)
        .enter()
        .append("rect")
        .attr("x", (d) => x(d.x0!))
        .attr("y", (d) => y(d.length))
        .attr("width", (d) => Math.max(0, x(d.x1!) - x(d.x0!) - 1))
        .attr("height", (d) => dims.marginTop + dims.innerHeight - y(d.length))
        .attr("fill", "#4682B4")
        .attr("opacity", 0.6);

      // Burn average line
      if (burn) {
        g.append("line")
          .attr("x1", x(burn.futures_price))
          .attr("x2", x(burn.futures_price))
          .attr("y1", dims.marginTop)
          .attr("y2", dims.marginTop + dims.innerHeight)
          .attr("stroke", "#dc2626")
          .attr("stroke-width", 2)
          .attr("stroke-dasharray", "6,3");

        g.append("text")
          .attr("x", x(burn.futures_price) + 4)
          .attr("y", dims.marginTop + 14)
          .text(`Burn: ${burn.futures_price.toFixed(0)}`)
          .attr("fill", "#dc2626")
          .attr("font-size", 11)
          .attr("font-weight", "bold");
      }

      // MC average line
      if (mc) {
        g.append("line")
          .attr("x1", x(mc.futures_price))
          .attr("x2", x(mc.futures_price))
          .attr("y1", dims.marginTop)
          .attr("y2", dims.marginTop + dims.innerHeight)
          .attr("stroke", "#1e3a5f")
          .attr("stroke-width", 2)
          .attr("stroke-dasharray", "4,4");

        g.append("text")
          .attr("x", x(mc.futures_price) + 4)
          .attr("y", dims.marginTop + 28)
          .text(`MC: ${mc.futures_price.toFixed(0)} (λ=${mc.lambda_risk})`)
          .attr("fill", "#1e3a5f")
          .attr("font-size", 11)
          .attr("font-weight", "bold");
      }

      // Strike line
      if (burn && burn.strike > 0 && x(burn.strike) >= dims.marginLeft) {
        g.append("line")
          .attr("x1", x(burn.strike))
          .attr("x2", x(burn.strike))
          .attr("y1", dims.marginTop)
          .attr("y2", dims.marginTop + dims.innerHeight)
          .attr("stroke", "#16a34a")
          .attr("stroke-width", 1.5)
          .attr("stroke-dasharray", "3,3");

        g.append("text")
          .attr("x", x(burn.strike) + 4)
          .attr("y", dims.marginTop + dims.innerHeight - 4)
          .text(`K=${burn.strike}`)
          .attr("fill", "#16a34a")
          .attr("font-size", 10);
      }

      // Axes
      svg
        .append("g")
        .attr("transform", `translate(0,${dims.marginTop + dims.innerHeight})`)
        .call(d3.axisBottom(x).ticks(6))
        .attr("font-size", 10);

      svg
        .append("g")
        .attr("transform", `translate(${dims.marginLeft},0)`)
        .call(d3.axisLeft(y).ticks(4))
        .attr("font-size", 10);
    }
  }, [burn, mc, ddType, dims]);

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">
        Pricing Distribution
        <InfoPopover title="Pricing Distribution">
          <p>ヒストリカル累積{ddType.toUpperCase()}値の分布。</p>
          <p className="mt-1"><strong>赤破線</strong>: Burn Analysis先物価格（過去平均）</p>
          <p className="mt-1"><strong>青破線</strong>: Monte Carlo先物価格（モデルベース）</p>
          <p className="mt-1"><strong>緑線</strong>: オプション行使価格 K</p>
        </InfoPopover>
      </h3>
      <div ref={containerRef} className="w-full h-64 relative">
        <svg ref={svgRef} width={dims.width} height={dims.height} />
      </div>
      {/* Pricing results table */}
      {(burn || mc) && (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-xs text-center border-collapse">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="py-1 px-2 text-left">Metric</th>
                {burn && <th className="py-1 px-2">Burn Analysis</th>}
                {mc && <th className="py-1 px-2">Monte Carlo</th>}
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-gray-100">
                <td className="py-1 px-2 text-left font-medium">Futures</td>
                {burn && <td className="py-1 px-2">{burn.futures_price.toFixed(1)}</td>}
                {mc && (
                  <td className="py-1 px-2">
                    {mc.futures_price.toFixed(1)}
                    <span className="text-gray-400 ml-1">±{mc.futures_se.toFixed(1)}</span>
                  </td>
                )}
              </tr>
              <tr className="border-b border-gray-100">
                <td className="py-1 px-2 text-left font-medium">Call (K={burn?.strike ?? mc?.strike ?? 0})</td>
                {burn && <td className="py-1 px-2">{burn.call_price.toFixed(2)}</td>}
                {mc && (
                  <td className="py-1 px-2">
                    {mc.call_price.toFixed(2)}
                    <span className="text-gray-400 ml-1">±{mc.call_se.toFixed(2)}</span>
                  </td>
                )}
              </tr>
              <tr>
                <td className="py-1 px-2 text-left font-medium">Put (K={burn?.strike ?? mc?.strike ?? 0})</td>
                {burn && <td className="py-1 px-2">{burn.put_price.toFixed(2)}</td>}
                {mc && (
                  <td className="py-1 px-2">
                    {mc.put_price.toFixed(2)}
                    <span className="text-gray-400 ml-1">±{mc.put_se.toFixed(2)}</span>
                  </td>
                )}
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
