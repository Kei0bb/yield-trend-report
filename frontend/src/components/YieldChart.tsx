import Plot from "./PlotlyChart";
import type { ProcessData } from "../types";
import { BIN_COLORS, YIELD_LINE_COLOR, MUTED, MUTED_SOFT, GRID, AXIS_LINE, plotlyBaseLayout } from "../theme";

interface YieldChartProps {
  processName: string;
  data: ProcessData;
  target?: number | null;
  colorMap?: Record<string, string>;
}

export default function YieldChart({ processName, data, target, colorMap }: YieldChartProps) {
  // Yield axis fixed at 0-100 with a small top margin so points at 100 don't clip.
  const yieldRange: [number, number] = [0, 102];

  const binNames = Object.keys(data.fail_bins);

  const barTraces: Plotly.Data[] = binNames.map(
    (binName, bIdx) =>
      ({
        x: data.lots,
        y: data.fail_bins[binName] ?? data.lots.map(() => 0),
        name: binName,
        type: "bar" as const,
        marker: { color: (colorMap && colorMap[binName]) ?? BIN_COLORS[bIdx % BIN_COLORS.length] },
        yaxis: "y",
        hovertemplate: `%{x}<br>${binName}: %{y:.3f}%<extra></extra>`,
      } as unknown as Plotly.Data)
  );

  const lastNonNull = [...data.yield_avg].reverse().find((v): v is number => v != null);
  const latestYield = lastNonNull ?? 0;

  const lineTrace: Plotly.Data = {
    x: data.lots,
    y: data.yield_avg,
    name: "Yield (%)",
    type: "scatter" as const,
    mode: "lines+markers" as const,
    line: { color: YIELD_LINE_COLOR, width: 2 },
    marker: { size: 6, color: YIELD_LINE_COLOR },
    yaxis: "y2",
    hovertemplate: "%{x}<br>Yield: %{y:.2f}%<extra></extra>",
  };

  // Optional product-level target reference line on the yield (y2) axis.
  // Report/PDF never pass `target`, so this stays a no-op there.
  const hasTarget = target != null;
  const targetShapes: Partial<Plotly.Shape>[] = hasTarget
    ? [
        {
          type: "line",
          xref: "paper",
          x0: 0,
          x1: 1,
          yref: "y2",
          y0: target,
          y1: target,
          line: { color: "rgba(198,69,69,0.6)", width: 1.5, dash: "dash" },
        },
      ]
    : [];

  const layout: Partial<Plotly.Layout> = {
    ...plotlyBaseLayout(),
    barmode: "stack",
    xaxis: { tickangle: -30, tickfont: { size: 10, color: MUTED }, gridcolor: GRID, linecolor: AXIS_LINE },
    yaxis: { title: { text: "Fail Bin (%)", font: { size: 10, color: MUTED_SOFT } }, side: "left", range: [0, 102], tickfont: { size: 10, color: MUTED }, gridcolor: GRID, zerolinecolor: AXIS_LINE },
    yaxis2: { title: { text: "Yield (%)", font: { size: 10, color: MUTED_SOFT } }, side: "right", overlaying: "y", range: yieldRange, tickfont: { size: 10, color: MUTED }, showgrid: false },
    legend: { orientation: "h", yanchor: "bottom", y: -0.4, xanchor: "center", x: 0.5, font: { size: 11, color: MUTED }, bgcolor: "rgba(0,0,0,0)" },
    margin: { l: 56, r: 56, t: 16, b: 110 },
    height: 420,
    shapes: targetShapes,
  };

  return (
    <section style={styles.card}>
      <div style={styles.cardHeader}>
        <div>
          <div style={styles.processBadge}>{processName}</div>
          <h3 style={styles.title}>Yield Trend</h3>
        </div>
        <div style={styles.stats}>
          {hasTarget && (
            <div style={styles.statItem}>
              <div style={styles.statLabel}>Target</div>
              <div style={styles.statValue}>{target}%</div>
            </div>
          )}
          <div style={styles.statItem}>
            <div style={styles.statLabel}>Latest yield</div>
            <div style={styles.statValue}>{latestYield.toFixed(2)}%</div>
          </div>
        </div>
      </div>
      <Plot
        data={[...barTraces, lineTrace]}
        layout={layout}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: "100%" }}
        useResizeHandler
      />
    </section>
  );
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: "var(--surface-card)",
    border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    padding: "22px 24px 12px",
  },
  cardHeader: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 16,
    marginBottom: 8,
    flexWrap: "wrap",
  },
  processBadge: {
    display: "inline-block",
    padding: "2px 10px",
    borderRadius: "var(--radius-pill)",
    background: "var(--surface-soft)",
    color: "var(--body)",
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: "0.04em",
    marginBottom: 6,
  },
  title: {
    fontSize: 17,
    fontWeight: 600,
    color: "var(--ink)",
    letterSpacing: "-0.015em",
  },
  stats: { display: "flex", gap: 28, flexWrap: "wrap", justifyContent: "flex-end" },
  statItem: { textAlign: "right" },
  statLabel: {
    fontSize: 10,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "var(--muted-soft)",
    marginBottom: 2,
  },
  statValue: {
    fontSize: 18,
    fontWeight: 600,
    color: "var(--ink)",
    letterSpacing: "-0.01em",
    fontVariantNumeric: "tabular-nums",
  },
};
