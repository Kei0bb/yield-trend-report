import Plot from "../PlotlyChart";
import { INK, MUTED_SOFT, SPEC_LINE_COLOR, plotlyBaseLayout } from "../../theme";

export interface TrendPoint {
  /** X value: a wafer number, or a lot id. */
  label: string | number;
  mean: number | null;
  sigma: number | null;
  /** Marker color; defaults to INK. Used to carry a lot's own judgement. */
  color?: string;
}

interface Props {
  title: string;
  points: TrendPoint[];
  xTitle: string;
  specLow: number | null;
  specHigh: number | null;
  /** Lot ids are categories, not numbers — keeps them evenly spaced. */
  categoryAxis?: boolean;
}

/** Means with ±3σ whiskers and the spec limits. One series, so no legend —
 *  the title names it. Shared by the wafer axis (single-lot report) and the
 *  lot axis (trend report); the two must not drift apart. */
export default function WatItemTrendChart({
  title, points, xTitle, specLow, specHigh, categoryAxis = false,
}: Props) {
  const shapes = [];
  const annotations = [];
  for (const [limit, label] of [[specLow, "LSL"], [specHigh, "USL"]] as const) {
    if (limit === null || limit === undefined) continue;
    shapes.push({
      type: "line" as const, xref: "paper" as const, x0: 0, x1: 1,
      y0: limit, y1: limit,
      line: { color: SPEC_LINE_COLOR, width: 1, dash: "dash" as const },
    });
    annotations.push({
      xref: "paper" as const, x: 1, y: limit, xanchor: "left" as const,
      text: label, showarrow: false,
      font: { size: 10, color: SPEC_LINE_COLOR },
    });
  }

  return (
    <Plot
      data={[{
        x: points.map((p) => p.label),
        y: points.map((p) => p.mean),
        type: "scatter",
        mode: "lines+markers",
        line: { color: INK, width: 2 },
        marker: { size: 8, color: points.map((p) => p.color ?? INK) },
        error_y: {
          type: "data",
          array: points.map((p) => (p.sigma === null ? 0 : p.sigma * 3)),
          visible: true,
          color: "rgba(20,20,19,0.35)",
          thickness: 1.2,
          width: 3,
        },
        hovertemplate: "%{x}<br>%{y:.4g}<extra></extra>",
      }]}
      layout={{
        ...plotlyBaseLayout(),
        title: { text: title, font: { size: 13 } },
        height: 300,
        margin: { l: 64, r: 56, t: 40, b: categoryAxis ? 96 : 44 },
        showlegend: false,
        xaxis: {
          title: { text: xTitle, font: { size: 11, color: MUTED_SOFT } },
          gridcolor: "rgba(0,0,0,0.05)",
          zeroline: false,
          ...(categoryAxis ? { type: "category" as const, tickangle: -45 } : {}),
        },
        yaxis: { gridcolor: "rgba(0,0,0,0.05)", zeroline: false },
        shapes,
        annotations,
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: "100%" }}
    />
  );
}
