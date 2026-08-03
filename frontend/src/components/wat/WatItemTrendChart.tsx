import Plot from "react-plotly.js";
import type { WatItemStats } from "../../types";
import { INK, MUTED_SOFT, SPEC_LINE_COLOR, plotlyBaseLayout } from "../../theme";

interface Props {
  item: WatItemStats;
}

/** Wafer means with ±3σ whiskers and the spec limits. One series, so no
 *  legend — the title names it. */
export default function WatItemTrendChart({ item }: Props) {
  const series = item.wafer_series;
  const shapes = [];
  const annotations = [];
  for (const [limit, label] of [[item.spec_low, "LSL"], [item.spec_high, "USL"]] as const) {
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

  const unit = item.unit ? ` [${item.unit}]` : "";

  return (
    <Plot
      data={[{
        x: series.map((w) => w.wafer_id),
        y: series.map((w) => w.mean),
        type: "scatter",
        mode: "lines+markers",
        line: { color: INK, width: 2 },
        marker: { size: 8, color: INK },
        error_y: {
          type: "data",
          array: series.map((w) => (w.sigma === null ? 0 : w.sigma * 3)),
          visible: true,
          color: "rgba(20,20,19,0.35)",
          thickness: 1.2,
          width: 3,
        },
        hovertemplate: "Wafer %{x}<br>%{y:.4g}<extra></extra>",
      }]}
      layout={{
        ...plotlyBaseLayout(),
        title: { text: `${item.item_name}${unit}`, font: { size: 13 } },
        height: 300,
        margin: { l: 64, r: 56, t: 40, b: 44 },
        showlegend: false,
        xaxis: {
          title: { text: "Wafer #", font: { size: 11, color: MUTED_SOFT } },
          gridcolor: "rgba(0,0,0,0.05)",
          zeroline: false,
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
