import Plot from "./PlotlyChart";
import type { ProcessData } from "../types";
import { BIN_COLORS, FONT_FAMILY, YIELD_LINE_COLOR } from "../theme";

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
        marker: { color: (colorMap && colorMap[binName]) ?? BIN_COLORS[bIdx % BIN_COLORS.length], opacity: 0.9 },
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
          line: { color: "rgba(224,62,62,0.6)", width: 1.5, dash: "dash" },
        },
      ]
    : [];

  const layout: Partial<Plotly.Layout> = {
    barmode: "stack",
    font: { family: FONT_FAMILY, size: 11, color: "#37352f" },
    xaxis: { tickangle: -30, tickfont: { size: 10, color: "#615d59" }, gridcolor: "rgba(0,0,0,0.04)", linecolor: "rgba(0,0,0,0.1)" },
    yaxis: { title: { text: "Fail Bin (%)", font: { size: 10, color: "#787672" } }, side: "left", range: [0, 102], tickfont: { size: 10, color: "#615d59" }, gridcolor: "rgba(0,0,0,0.04)", zerolinecolor: "rgba(0,0,0,0.08)" },
    yaxis2: { title: { text: "Yield (%)", font: { size: 10, color: "#787672" } }, side: "right", overlaying: "y", range: yieldRange, tickfont: { size: 10, color: "#615d59" }, showgrid: false },
    legend: { orientation: "h", yanchor: "bottom", y: -0.4, xanchor: "center", x: 0.5, font: { size: 11, color: "#615d59" }, bgcolor: "rgba(0,0,0,0)" },
    margin: { l: 56, r: 56, t: 16, b: 110 },
    plot_bgcolor: "#ffffff",
    paper_bgcolor: "#ffffff",
    height: 420,
    hoverlabel: { bgcolor: "#ffffff", bordercolor: "rgba(0,0,0,0.1)", font: { family: FONT_FAMILY, size: 11, color: "#37352f" } },
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
          <div style={styles.statItem}>
            <div style={styles.statLabel}>Latest yield</div>
            <div style={styles.statValue}>{latestYield.toFixed(2)}%</div>
          </div>
          {hasTarget && (
            <div style={styles.statItem}>
              <div style={styles.statLabel}>Target</div>
              <div style={styles.statValue}>{target}%</div>
            </div>
          )}
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
    background: "var(--white)",
    border: "var(--border-whisper)",
    borderRadius: 12,
    padding: "22px 24px 12px",
    boxShadow: "var(--shadow-card)",
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
    borderRadius: 999,
    background: "var(--badge-bg)",
    color: "var(--badge-text)",
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: "0.04em",
    marginBottom: 6,
  },
  title: {
    fontSize: 17,
    fontWeight: 600,
    color: "var(--gray-700)",
    letterSpacing: "-0.015em",
  },
  stats: {
    display: "flex",
    gap: 28,
    flexWrap: "wrap",
    justifyContent: "flex-end",
  },
  statItem: {
    textAlign: "right",
  },
  statLabel: {
    fontSize: 10,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "var(--gray-400)",
    marginBottom: 2,
  },
  statValue: {
    fontSize: 18,
    fontWeight: 600,
    color: "var(--gray-700)",
    letterSpacing: "-0.01em",
    fontVariantNumeric: "tabular-nums",
  },
};
