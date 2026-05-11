import Plot from "./PlotlyChart";
import type { ProcessData } from "../types";

// Notion-inspired accent palette for fail bins (single product)
const BIN_COLORS = [
  "#2a9d99", // teal
  "#1aae39", // green
  "#dd5b00", // orange
  "#ff64c8", // pink
  "#391c57", // purple
  "#e9b949", // yellow
  "#e03e3e", // red
  "#0075de", // notion blue
  "#a39e98", // gray
  "#37352f", // dark
  "#097fe8", // focus blue
  "#005bab", // active blue
];

// 複数品種比較用カラー（品種ごとに割り当て）
const PRODUCT_COLORS = [
  "#0075de", // notion blue
  "#e03e3e", // red
  "#1aae39", // green
  "#dd5b00", // orange
  "#391c57", // purple
  "#e9b949", // yellow
  "#097fe8", // focus blue
  "#ff64c8", // pink
];

const YIELD_LINE_COLOR = "#0075de";

const FONT_FAMILY =
  "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif";

interface YieldChartProps {
  processName: string;
  /** product -> ProcessData */
  productData: Record<string, ProcessData>;
}

export default function YieldChart({ processName, productData }: YieldChartProps) {
  const productNames = Object.keys(productData);
  const isMulti = productNames.length > 1;

  // ── 単一品種レンダリング ─────────────────────────────────────────
  if (!isMulti) {
    const data = productData[productNames[0]];
    const binNames = Object.keys(data.fail_bins);
    const avg =
      data.yield_avg.length > 0
        ? data.yield_avg.reduce((a, b) => a + b, 0) / data.yield_avg.length
        : 0;

    const barTraces: Plotly.Data[] = binNames.map((binName, i) => ({
      x: data.lots,
      y: data.fail_bins[binName],
      name: binName,
      type: "bar" as const,
      marker: { color: BIN_COLORS[i % BIN_COLORS.length], opacity: 0.9 },
      yaxis: "y",
      hovertemplate: `%{x}<br>${binName}: %{y:.3f}%<extra></extra>`,
    }));

    const lineTrace: Plotly.Data = {
      x: data.lots,
      y: data.yield_avg,
      name: "Yield (%)",
      type: "scatter" as const,
      mode: "lines+markers" as const,
      line: { color: YIELD_LINE_COLOR, width: 2.5, shape: "spline" },
      marker: { size: 7, color: YIELD_LINE_COLOR },
      yaxis: "y2",
      hovertemplate: "%{x}<br>Yield: %{y:.2f}%<extra></extra>",
    };

    const layout: Partial<Plotly.Layout> = {
      barmode: "stack",
      font: { family: FONT_FAMILY, size: 12, color: "#37352f" },
      xaxis: {
        title: { text: "Work Week", font: { size: 11, color: "#787672" } },
        tickangle: -30,
        tickfont: { size: 11, color: "#615d59" },
        gridcolor: "rgba(0,0,0,0.04)",
        linecolor: "rgba(0,0,0,0.1)",
      },
      yaxis: {
        title: { text: "Fail Bin (%)", font: { size: 11, color: "#787672" } },
        side: "left",
        rangemode: "tozero",
        tickfont: { size: 11, color: "#615d59" },
        gridcolor: "rgba(0,0,0,0.04)",
        zerolinecolor: "rgba(0,0,0,0.08)",
      },
      yaxis2: {
        title: { text: "Yield (%)", font: { size: 11, color: "#787672" } },
        side: "right",
        overlaying: "y",
        range: [80, 100],
        tickfont: { size: 11, color: "#615d59" },
        showgrid: false,
      },
      legend: {
        orientation: "h",
        yanchor: "bottom",
        y: -0.4,
        xanchor: "center",
        x: 0.5,
        font: { size: 11, color: "#615d59" },
        bgcolor: "rgba(0,0,0,0)",
      },
      margin: { l: 56, r: 56, t: 16, b: 110 },
      plot_bgcolor: "#ffffff",
      paper_bgcolor: "#ffffff",
      height: 420,
      hoverlabel: {
        bgcolor: "#ffffff",
        bordercolor: "rgba(0,0,0,0.1)",
        font: { family: FONT_FAMILY, size: 12, color: "#37352f" },
      },
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
              <div style={styles.statLabel}>Avg yield</div>
              <div style={styles.statValue}>{avg.toFixed(2)}%</div>
            </div>
            <div style={styles.statItem}>
              <div style={styles.statLabel}>Lots</div>
              <div style={styles.statValue}>{data.lots.length}</div>
            </div>
            <div style={styles.statItem}>
              <div style={styles.statLabel}>Bins</div>
              <div style={styles.statValue}>{binNames.length}</div>
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

  // ── 複数品種比較レンダリング ─────────────────────────────────────

  // Y 軸範囲を全品種のデータから動的計算（余白 ±2%）
  const allYields = productNames.flatMap((p) => productData[p].yield_avg);
  const yMin = allYields.length > 0 ? Math.min(...allYields) : 80;
  const yMax = allYields.length > 0 ? Math.max(...allYields) : 100;
  const yPad = Math.max((yMax - yMin) * 0.5, 2);
  const yRange = [Math.max(0, Math.floor(yMin - yPad)), Math.min(100, Math.ceil(yMax + yPad))];

  const lineTraces: Plotly.Data[] = productNames.map((product, i) => {
    const d = productData[product];
    const color = PRODUCT_COLORS[i % PRODUCT_COLORS.length];
    return {
      x: d.lots,
      y: d.yield_avg,
      name: product,
      type: "scatter" as const,
      mode: "lines+markers" as const,
      line: { color, width: 2.5, shape: "spline" },
      marker: { size: 7, color },
      hovertemplate: `%{x}<br>${product}: %{y:.2f}%<extra></extra>`,
    };
  });

  const multiLayout: Partial<Plotly.Layout> = {
    font: { family: FONT_FAMILY, size: 12, color: "#37352f" },
    xaxis: {
      title: { text: "Work Week", font: { size: 11, color: "#787672" } },
      tickangle: -30,
      tickfont: { size: 11, color: "#615d59" },
      gridcolor: "rgba(0,0,0,0.05)",
      linecolor: "rgba(0,0,0,0.1)",
    },
    yaxis: {
      title: { text: "Yield (%)", font: { size: 11, color: "#787672" } },
      range: yRange,
      tickfont: { size: 11, color: "#615d59" },
      gridcolor: "rgba(0,0,0,0.05)",
      zerolinecolor: "rgba(0,0,0,0.08)",
    },
    legend: {
      orientation: "h",
      yanchor: "bottom",
      y: -0.35,
      xanchor: "center",
      x: 0.5,
      font: { size: 11, color: "#615d59" },
      bgcolor: "rgba(0,0,0,0)",
    },
    margin: { l: 56, r: 32, t: 16, b: 100 },
    plot_bgcolor: "#ffffff",
    paper_bgcolor: "#ffffff",
    height: 400,
    hoverlabel: {
      bgcolor: "#ffffff",
      bordercolor: "rgba(0,0,0,0.1)",
      font: { family: FONT_FAMILY, size: 12, color: "#37352f" },
    },
  };

  return (
    <section style={styles.card}>
      <div style={styles.cardHeader}>
        <div>
          <div style={styles.processBadge}>{processName}</div>
          <h3 style={styles.title}>Yield Comparison</h3>
        </div>
        {/* 品種ごとの平均 yield を横並びで表示 */}
        <div style={styles.stats}>
          {productNames.map((product, i) => {
            const d = productData[product];
            const avg =
              d.yield_avg.length > 0
                ? d.yield_avg.reduce((a, b) => a + b, 0) / d.yield_avg.length
                : 0;
            const color = PRODUCT_COLORS[i % PRODUCT_COLORS.length];
            return (
              <div key={product} style={styles.statItem}>
                <div
                  style={{
                    ...styles.statLabel,
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    justifyContent: "flex-end",
                  }}
                >
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      background: color,
                      flexShrink: 0,
                      display: "inline-block",
                    }}
                  />
                  {product}
                </div>
                <div style={styles.statValue}>{avg.toFixed(2)}%</div>
              </div>
            );
          })}
        </div>
      </div>
      <Plot
        data={lineTraces}
        layout={multiLayout}
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
