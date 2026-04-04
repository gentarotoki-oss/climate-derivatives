import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { DailyTemperature } from "../services/api";
import { useChartDimensions } from "../hooks/useChartDimensions";
import InfoPopover from "./InfoPopover";

interface Props {
  data: DailyTemperature[];
  seasonalValues?: number[];
  baseTemp: number;
}

export default function TemperatureChart({ data, seasonalValues, baseTemp }: Props) {
  const [containerRef, dims, containerNode] = useChartDimensions({
    marginTop: 20,
    marginRight: 20,
    marginBottom: 40,
    marginLeft: 50,
  });
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!data.length || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const parseDate = d3.timeParse("%Y-%m-%d");
    const parsed = data.map((d) => ({
      date: parseDate(d.date)!,
      tmax: d.tmax,
      tmin: d.tmin,
      tavg: d.tavg,
    }));

    const x = d3
      .scaleTime()
      .domain(d3.extent(parsed, (d) => d.date) as [Date, Date])
      .range([dims.marginLeft, dims.marginLeft + dims.innerWidth]);

    const allTemps = parsed.flatMap((d) => [d.tmin, d.tmax]);
    const y = d3
      .scaleLinear()
      .domain([d3.min(allTemps)! - 2, d3.max(allTemps)! + 2])
      .range([dims.marginTop + dims.innerHeight, dims.marginTop]);

    const g = svg.append("g");

    // TMIN-TMAX range band
    const area = d3
      .area<(typeof parsed)[0]>()
      .x((d) => x(d.date))
      .y0((d) => y(d.tmin))
      .y1((d) => y(d.tmax));

    g.append("path")
      .datum(parsed)
      .attr("d", area)
      .attr("fill", "#4682B4")
      .attr("opacity", 0.2);

    // T_avg line
    const line = d3
      .line<(typeof parsed)[0]>()
      .x((d) => x(d.date))
      .y((d) => y(d.tavg));

    g.append("path")
      .datum(parsed)
      .attr("d", line)
      .attr("fill", "none")
      .attr("stroke", "#1e3a5f")
      .attr("stroke-width", 1);

    // Seasonal component overlay
    if (seasonalValues && seasonalValues.length === parsed.length) {
      const seasonalLine = d3
        .line<number>()
        .x((_, i) => x(parsed[i].date))
        .y((d) => y(d));

      g.append("path")
        .datum(seasonalValues)
        .attr("d", seasonalLine)
        .attr("fill", "none")
        .attr("stroke", "#dc2626")
        .attr("stroke-width", 2)
        .attr("stroke-dasharray", "6,3");
    }

    // Base temp reference line
    g.append("line")
      .attr("x1", dims.marginLeft)
      .attr("x2", dims.marginLeft + dims.innerWidth)
      .attr("y1", y(baseTemp))
      .attr("y2", y(baseTemp))
      .attr("stroke", "#dc2626")
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "4,4")
      .attr("opacity", 0.5);

    g.append("text")
      .attr("x", dims.marginLeft + dims.innerWidth - 4)
      .attr("y", y(baseTemp) - 4)
      .attr("text-anchor", "end")
      .attr("font-size", 10)
      .attr("fill", "#dc2626")
      .text(`Base ${baseTemp}°C`);

    // Axes
    svg
      .append("g")
      .attr("transform", `translate(0,${dims.marginTop + dims.innerHeight})`)
      .call(d3.axisBottom(x).ticks(6).tickFormat(d3.timeFormat("%Y-%m") as never))
      .attr("font-size", 10);

    svg
      .append("g")
      .attr("transform", `translate(${dims.marginLeft},0)`)
      .call(d3.axisLeft(y).ticks(6))
      .attr("font-size", 10);

    // Tooltip
    const tooltip = d3
      .select(containerNode!)
      .append("div")
      .style("position", "absolute")
      .style("visibility", "hidden")
      .style("background", "white")
      .style("border", "1px solid #ddd")
      .style("border-radius", "4px")
      .style("padding", "6px 10px")
      .style("font-size", "12px")
      .style("pointer-events", "none")
      .style("box-shadow", "0 2px 4px rgba(0,0,0,0.1)");

    const bisect = d3.bisector<(typeof parsed)[0], Date>((d) => d.date).left;

    svg.append("rect")
      .attr("x", dims.marginLeft)
      .attr("y", dims.marginTop)
      .attr("width", dims.innerWidth)
      .attr("height", dims.innerHeight)
      .attr("fill", "none")
      .attr("pointer-events", "all")
      .on("mousemove", (event) => {
        const [mx] = d3.pointer(event);
        const date = x.invert(mx);
        const idx = bisect(parsed, date, 1);
        const d = parsed[Math.min(idx, parsed.length - 1)];
        tooltip
          .style("visibility", "visible")
          .style("left", `${mx + 12}px`)
          .style("top", `${y(d.tavg) - 10}px`)
          .html(
            `<strong>${d3.timeFormat("%Y-%m-%d")(d.date)}</strong><br/>` +
            `Avg: ${d.tavg.toFixed(1)}°C<br/>` +
            `Max: ${d.tmax.toFixed(1)}°C / Min: ${d.tmin.toFixed(1)}°C`
          );
      })
      .on("mouseleave", () => tooltip.style("visibility", "hidden"));

    return () => {
      tooltip.remove();
    };
  }, [data, seasonalValues, baseTemp, dims, containerNode]);

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">
        Temperature Time Series
        <InfoPopover title="Temperature Time Series">
          <p>日次気温データ。青帯はTMIN〜TMAXの範囲、暗い線は日平均気温。</p>
          <p className="mt-1">赤破線は季節成分 θ(t)（フーリエ級数フィット）。</p>
          <p className="mt-1">水平の赤点線はHDD/CDDの基準温度（18.3°C = 65°F）。</p>
        </InfoPopover>
      </h3>
      <div ref={containerRef} className="w-full h-64 relative">
        <svg ref={svgRef} width={dims.width} height={dims.height} />
      </div>
    </div>
  );
}
