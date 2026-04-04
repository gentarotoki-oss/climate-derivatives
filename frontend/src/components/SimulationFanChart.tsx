import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { SimulationResponse } from "../services/api";
import { useChartDimensions } from "../hooks/useChartDimensions";
import InfoPopover from "./InfoPopover";

interface Props {
  data: SimulationResponse;
}

export default function SimulationFanChart({ data }: Props) {
  const [containerRef, dims] = useChartDimensions({
    marginTop: 20,
    marginRight: 20,
    marginBottom: 40,
    marginLeft: 50,
  });
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!data || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const n = data.dates_offset.length;
    const x = d3
      .scaleLinear()
      .domain([0, n - 1])
      .range([dims.marginLeft, dims.marginLeft + dims.innerWidth]);

    const allVals = [
      ...data.percentiles.p5,
      ...data.percentiles.p95,
    ];
    const y = d3
      .scaleLinear()
      .domain([d3.min(allVals)! - 2, d3.max(allVals)! + 2])
      .range([dims.marginTop + dims.innerHeight, dims.marginTop]);

    const g = svg.append("g");

    // 90% CI band (p5-p95)
    const area90 = d3
      .area<number>()
      .x((_, i) => x(i))
      .y0((_, i) => y(data.percentiles.p5[i]))
      .y1((_, i) => y(data.percentiles.p95[i]));

    g.append("path")
      .datum(d3.range(n))
      .attr("d", area90)
      .attr("fill", "#4682B4")
      .attr("opacity", 0.15);

    // 50% CI band (p25-p75)
    const area50 = d3
      .area<number>()
      .x((_, i) => x(i))
      .y0((_, i) => y(data.percentiles.p25[i]))
      .y1((_, i) => y(data.percentiles.p75[i]));

    g.append("path")
      .datum(d3.range(n))
      .attr("d", area50)
      .attr("fill", "#4682B4")
      .attr("opacity", 0.3);

    // Median line
    const medianLine = d3
      .line<number>()
      .x((_, i) => x(i))
      .y((_, i) => y(data.percentiles.p50[i]));

    g.append("path")
      .datum(d3.range(n))
      .attr("d", medianLine)
      .attr("fill", "none")
      .attr("stroke", "#4682B4")
      .attr("stroke-width", 2);

    // Seasonal component
    const seasonalLine = d3
      .line<number>()
      .x((_, i) => x(i))
      .y((d) => y(d));

    g.append("path")
      .datum(data.seasonal)
      .attr("d", seasonalLine)
      .attr("fill", "none")
      .attr("stroke", "#dc2626")
      .attr("stroke-width", 1.5)
      .attr("stroke-dasharray", "6,3");

    // Axes
    svg
      .append("g")
      .attr("transform", `translate(0,${dims.marginTop + dims.innerHeight})`)
      .call(d3.axisBottom(x).ticks(6).tickFormat((d) => `Day ${d}`))
      .attr("font-size", 10);

    svg
      .append("g")
      .attr("transform", `translate(${dims.marginLeft},0)`)
      .call(d3.axisLeft(y).ticks(6))
      .attr("font-size", 10);

    // Legend
    const legend = svg.append("g").attr("transform", `translate(${dims.marginLeft + 10}, ${dims.marginTop + 5})`);
    const items = [
      { label: "Median (p50)", color: "#4682B4", dash: "" },
      { label: "50% CI", color: "#4682B4", dash: "", rect: true, opacity: 0.3 },
      { label: "90% CI", color: "#4682B4", dash: "", rect: true, opacity: 0.15 },
      { label: "Seasonal θ(t)", color: "#dc2626", dash: "6,3" },
    ];
    items.forEach((item, i) => {
      if (item.rect) {
        legend.append("rect").attr("x", 0).attr("y", i * 16).attr("width", 20).attr("height", 10)
          .attr("fill", item.color).attr("opacity", item.opacity ?? 1);
      } else {
        legend.append("line").attr("x1", 0).attr("x2", 20).attr("y1", i * 16 + 5).attr("y2", i * 16 + 5)
          .attr("stroke", item.color).attr("stroke-width", 2).attr("stroke-dasharray", item.dash);
      }
      legend.append("text").attr("x", 24).attr("y", i * 16 + 10).text(item.label).attr("font-size", 10);
    });
  }, [data, dims]);

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">
        Simulation Fan Chart ({data.n_paths.toLocaleString()} paths)
        <InfoPopover title="Monte Carlo Fan Chart">
          <p>Euler-Maruyama法で生成した気温パスのパーセンタイルバンド。</p>
          <p className="mt-1"><strong>濃い帯</strong>: 50%信頼区間 (p25-p75)</p>
          <p className="mt-1"><strong>薄い帯</strong>: 90%信頼区間 (p5-p95)</p>
          <p className="mt-1">バンドが広いほど将来の不確実性が大きい。</p>
        </InfoPopover>
      </h3>
      <div ref={containerRef} className="w-full h-64 relative">
        <svg ref={svgRef} width={dims.width} height={dims.height} />
      </div>
    </div>
  );
}
