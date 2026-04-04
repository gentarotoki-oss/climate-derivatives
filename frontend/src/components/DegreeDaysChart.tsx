import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { MonthlyDegreeDays } from "../services/api";
import { useChartDimensions } from "../hooks/useChartDimensions";
import InfoPopover from "./InfoPopover";

interface Props {
  data: MonthlyDegreeDays[];
  ddType: "hdd" | "cdd";
}

const MONTH_LABELS = [
  "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

export default function DegreeDaysChart({ data, ddType }: Props) {
  const [containerRef, dims] = useChartDimensions({
    marginTop: 20,
    marginRight: 20,
    marginBottom: 40,
    marginLeft: 55,
  });
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!data.length || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const years = [...new Set(data.map((d) => d.year))].sort();
    const color = d3.scaleOrdinal(d3.schemeTableau10).domain(years.map(String));

    const x = d3
      .scaleBand()
      .domain(Array.from({ length: 12 }, (_, i) => MONTH_LABELS[i + 1]))
      .range([dims.marginLeft, dims.marginLeft + dims.innerWidth])
      .padding(0.15);

    const maxVal = d3.max(data, (d) => (ddType === "hdd" ? d.hdd : d.cdd)) ?? 0;
    const y = d3
      .scaleLinear()
      .domain([0, maxVal * 1.1])
      .range([dims.marginTop + dims.innerHeight, dims.marginTop]);

    const yearBand = d3
      .scaleBand()
      .domain(years.map(String))
      .range([0, x.bandwidth()])
      .padding(0.05);

    // Bars per year
    const g = svg.append("g");
    for (const yr of years) {
      const yrData = data.filter((d) => d.year === yr);
      g.selectAll(`.bar-${yr}`)
        .data(yrData)
        .enter()
        .append("rect")
        .attr("x", (d) => (x(MONTH_LABELS[d.month]) ?? 0) + (yearBand(String(yr)) ?? 0))
        .attr("y", (d) => y(ddType === "hdd" ? d.hdd : d.cdd))
        .attr("width", yearBand.bandwidth())
        .attr("height", (d) => dims.marginTop + dims.innerHeight - y(ddType === "hdd" ? d.hdd : d.cdd))
        .attr("fill", color(String(yr)))
        .attr("opacity", 0.8);
    }

    // Axes
    svg
      .append("g")
      .attr("transform", `translate(0,${dims.marginTop + dims.innerHeight})`)
      .call(d3.axisBottom(x))
      .attr("font-size", 10);

    svg
      .append("g")
      .attr("transform", `translate(${dims.marginLeft},0)`)
      .call(d3.axisLeft(y).ticks(5))
      .attr("font-size", 10);

    // Legend
    const legend = svg.append("g").attr("transform", `translate(${dims.marginLeft + dims.innerWidth - 80}, ${dims.marginTop})`);
    years.forEach((yr, i) => {
      legend
        .append("rect")
        .attr("x", 0)
        .attr("y", i * 16)
        .attr("width", 12)
        .attr("height", 12)
        .attr("fill", color(String(yr)));
      legend
        .append("text")
        .attr("x", 16)
        .attr("y", i * 16 + 10)
        .text(String(yr))
        .attr("font-size", 10);
    });
  }, [data, ddType, dims]);

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">
        Monthly {ddType.toUpperCase()} by Year
        <InfoPopover title={ddType === "hdd" ? "Heating Degree Days" : "Cooling Degree Days"}>
          {ddType === "hdd" ? (
            <>
              <p><strong>HDD</strong> = max(T_base − T_avg, 0)</p>
              <p className="mt-1">寒い日ほど大きい。冬の暖房需要の代理変数。</p>
              <p className="mt-1">CME先物は月次累積HDDに対して取引。1 HDD = $20。</p>
            </>
          ) : (
            <>
              <p><strong>CDD</strong> = max(T_avg − T_base, 0)</p>
              <p className="mt-1">暑い日ほど大きい。夏の冷房需要の代理変数。</p>
              <p className="mt-1">CME先物は月次累積CDDに対して取引。1 CDD = $20。</p>
            </>
          )}
          <p className="mt-1 text-gray-500">年ごとのばらつきが「気候リスク」。</p>
        </InfoPopover>
      </h3>
      <div ref={containerRef} className="w-full h-64 relative">
        <svg ref={svgRef} width={dims.width} height={dims.height} />
      </div>
    </div>
  );
}
