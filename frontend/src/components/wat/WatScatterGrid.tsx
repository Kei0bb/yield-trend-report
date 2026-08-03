import { useState } from "react";
import Plot from "react-plotly.js";
import type { WatScatterPair, WatScatterPlot } from "../../types";
import { MUTED_SOFT, WAFER_COLORSCALE, plotlyBaseLayout } from "../../theme";

const PLOT_TITLES: Record<WatScatterPlot["kind"], string> = {
  vth_np: "Vth  n/p",
  idsat_np: "Idsat  n/p",
  ion_vt_n: "Ion-Vt  (N)",
  ion_vt_p: "Ion-Vt  (P)",
};

function axisLabel(item: string, unit: string): string {
  return unit ? `${item} [${unit}]` : item;
}

function ScatterPlot({ plot }: { plot: WatScatterPlot }) {
  if (plot.points.length === 0) {
    return (
      <div style={styles.empty}>
        <div style={styles.emptyTitle}>{PLOT_TITLES[plot.kind]}</div>
        <div>No data</div>
      </div>
    );
  }

  const [xLo, xHi] = plot.x_spec;
  const [yLo, yHi] = plot.y_spec;
  const shapes =
    xLo !== null && xHi !== null && yLo !== null && yHi !== null
      ? [{
          type: "rect" as const,
          x0: xLo, x1: xHi, y0: yLo, y1: yHi,
          line: { color: "rgba(198,69,69,0.45)", width: 1, dash: "dash" as const },
          fillcolor: "rgba(198,69,69,0.05)",
          layer: "below" as const,
        }]
      : [];

  return (
    <Plot
      data={[{
        x: plot.points.map((p) => p.x),
        y: plot.points.map((p) => p.y),
        type: "scatter",
        mode: "markers",
        marker: {
          size: 8,
          color: plot.points.map((p) => p.wafer_id),
          colorscale: WAFER_COLORSCALE,
          colorbar: { title: { text: "Wafer", font: { size: 10 } }, thickness: 10, len: 0.8 },
          line: { width: 1, color: "#ffffff" },
        },
        customdata: plot.points.map((p) => [p.wafer_id, p.site_no]),
        hovertemplate:
          "W%{customdata[0]} · site %{customdata[1]}<br>%{x:.4g}, %{y:.4g}<extra></extra>",
      }]}
      layout={{
        ...plotlyBaseLayout(),
        title: { text: PLOT_TITLES[plot.kind], font: { size: 13 } },
        height: 340,
        margin: { l: 62, r: 24, t: 40, b: 48 },
        showlegend: false,
        xaxis: {
          title: { text: axisLabel(plot.x_item, plot.x_unit), font: { size: 11, color: MUTED_SOFT } },
          gridcolor: "rgba(0,0,0,0.05)", zeroline: false,
        },
        yaxis: {
          title: { text: axisLabel(plot.y_item, plot.y_unit), font: { size: 11, color: MUTED_SOFT } },
          gridcolor: "rgba(0,0,0,0.05)", zeroline: false,
        },
        shapes,
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: "100%" }}
    />
  );
}

interface Props {
  pairs: WatScatterPair[];
}

/** One flavor at a time. Showing all 6 x 4 plots at once shrinks each below
 *  the size where 225 points and the wafer ramp can be read. */
export default function WatScatterGrid({ pairs }: Props) {
  const [active, setActive] = useState(0);
  if (pairs.length === 0) return null;

  const pair = pairs[Math.min(active, pairs.length - 1)];

  return (
    <div style={styles.card}>
      <div style={styles.chips}>
        {pairs.map((p, i) => (
          <button
            key={p.label}
            type="button"
            onClick={() => setActive(i)}
            style={{ ...styles.chip, ...(i === active ? styles.chipActive : {}) }}
          >
            {p.label}
          </button>
        ))}
        <span style={styles.legendHint}>colour = wafer number</span>
      </div>
      <div style={styles.grid}>
        {pair.plots.map((plot) => (
          <div key={plot.kind} style={styles.cell}>
            <ScatterPlot plot={plot} />
          </div>
        ))}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: "var(--surface-card)",
    border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    padding: 16,
    marginBottom: 20,
  },
  chips: { display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", marginBottom: 12 },
  chip: {
    padding: "6px 14px",
    borderRadius: "var(--radius-pill)",
    border: "var(--hairline)",
    background: "var(--surface-card)",
    color: "var(--muted)",
    fontSize: 13,
    fontWeight: 500,
    cursor: "pointer",
  },
  chipActive: {
    background: "var(--surface-soft)",
    color: "var(--ink)",
    border: "1px solid rgba(204, 120, 92, 0.45)",
  },
  legendHint: { marginLeft: "auto", fontSize: 12, color: "var(--muted-soft)" },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
    gap: 12,
  },
  cell: { minWidth: 0 },
  empty: {
    height: 340,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    color: "var(--muted-soft)",
    fontSize: 13,
    border: "1px dashed var(--hairline-color)",
    borderRadius: "var(--radius-control)",
  },
  emptyTitle: { color: "var(--muted)", fontWeight: 600 },
};
