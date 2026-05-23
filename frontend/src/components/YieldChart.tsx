import Plot from "./PlotlyChart";
import type { ProcessData } from "../types";
import { BIN_COLORS, PRODUCT_COLORS, FONT_FAMILY, YIELD_LINE_COLOR } from "../theme";

interface YieldChartProps {
  processName: string;
  /** display_name -> ProcessData */
  productData: Record<string, ProcessData>;
}

function buildBarTraces(
  products: string[],
  productData: Record<string, ProcessData>,
  allBinNames: string[],
  isMulti: boolean
): Plotly.Data[] {
  return products.flatMap((product, pIdx) =>
    allBinNames.map((binName, bIdx) => {
      const d = productData[product];
      const y = d.fail_bins[binName] ?? d.lots.map(() => 0);
      return {
        x: d.lots,
        y,
        name: binName,
        type: "bar" as const,
        marker: { color: BIN_COLORS[bIdx % BIN_COLORS.length], opacity: 0.9 },
        yaxis: "y",
        ...(isMulti
          ? {
              offsetgroup: product,
              legendgroup: binName,
              showlegend: pIdx === 0,
              hovertemplate: `<b>${product}</b> @ %{x}<br>${binName}: %{y:.3f}%<extra></extra>`,
            }
          : {
              hovertemplate: `%{x}<br>${binName}: %{y:.3f}%<extra></extra>`,
            }),
      } as unknown as Plotly.Data;
    })
  );
}

export default function YieldChart({ processName, productData }: YieldChartProps) {
  const productNames = Object.keys(productData);
  const isMulti = productNames.length > 1;

  // Yield axis fixed at 0-100 with a small top margin so points at 100 don't clip.
  const yieldRange: [number, number] = [0, 102];

  const allBinNames = Array.from(
    new Set(productNames.flatMap((p) => Object.keys(productData[p].fail_bins)))
  );

  const barTraces = buildBarTraces(productNames, productData, allBinNames, isMulti);

  // ── Single product ──────────────────────────────────────────────
  if (!isMulti) {
    const data = productData[productNames[0]];
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

    const layout: Partial<Plotly.Layout> = {
      barmode: "stack",
      font: { family: FONT_FAMILY, size: 11, color: "#37352f" },
      xaxis: { tickangle: -30, tickfont: { size: 10, color: "#615d59" }, gridcolor: "rgba(0,0,0,0.04)", linecolor: "rgba(0,0,0,0.1)" },
      yaxis: { title: { text: "Fail Bin (%)", font: { size: 10, color: "#787672" } }, side: "left", rangemode: "tozero", tickfont: { size: 10, color: "#615d59" }, gridcolor: "rgba(0,0,0,0.04)", zerolinecolor: "rgba(0,0,0,0.08)" },
      yaxis2: { title: { text: "Yield (%)", font: { size: 10, color: "#787672" } }, side: "right", overlaying: "y", range: yieldRange, tickfont: { size: 10, color: "#615d59" }, showgrid: false },
      legend: { orientation: "h", yanchor: "bottom", y: -0.4, xanchor: "center", x: 0.5, font: { size: 11, color: "#615d59" }, bgcolor: "rgba(0,0,0,0)" },
      margin: { l: 56, r: 56, t: 16, b: 110 },
      plot_bgcolor: "#ffffff",
      paper_bgcolor: "#ffffff",
      height: 420,
      hoverlabel: { bgcolor: "#ffffff", bordercolor: "rgba(0,0,0,0.1)", font: { family: FONT_FAMILY, size: 11, color: "#37352f" } },
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

  // ── Multi-product ───────────────────────────────────────────────
  const lineTraces: Plotly.Data[] = productNames.map((product, i) => {
    const d = productData[product];
    const color = PRODUCT_COLORS[i % PRODUCT_COLORS.length];
    return {
      x: d.lots,
      y: d.yield_avg,
      name: `Yield · ${product}`,
      type: "scatter" as const,
      mode: "lines+markers" as const,
      line: { color, width: 2 },
      marker: { size: 7, color },
      yaxis: "y2",
      legendgroup: `yield_${product}`,
      hovertemplate: `<b>${product}</b> @ %{x}<br>Yield: %{y:.2f}%<extra></extra>`,
    };
  });

  const multiLayout: Partial<Plotly.Layout> = {
    barmode: "stack",
    bargap: 0.25,
    bargroupgap: 0.08,
    font: { family: FONT_FAMILY, size: 12, color: "#37352f" },
    xaxis: { title: { text: "Work Week", font: { size: 11, color: "#787672" } }, tickangle: -30, tickfont: { size: 11, color: "#615d59" }, gridcolor: "rgba(0,0,0,0.04)", linecolor: "rgba(0,0,0,0.1)" },
    yaxis: { title: { text: "Fail Bin (%)", font: { size: 11, color: "#787672" } }, side: "left", rangemode: "tozero", tickfont: { size: 11, color: "#615d59" }, gridcolor: "rgba(0,0,0,0.04)", zerolinecolor: "rgba(0,0,0,0.08)" },
    yaxis2: { title: { text: "Yield (%)", font: { size: 11, color: "#787672" } }, side: "right", overlaying: "y", range: yieldRange, tickfont: { size: 11, color: "#615d59" }, showgrid: false },
    legend: { orientation: "h", yanchor: "bottom", y: -0.4, xanchor: "center", x: 0.5, font: { size: 11, color: "#615d59" }, bgcolor: "rgba(0,0,0,0)" },
    margin: { l: 56, r: 56, t: 16, b: 110 },
    plot_bgcolor: "#ffffff",
    paper_bgcolor: "#ffffff",
    height: 460,
    hoverlabel: { bgcolor: "#ffffff", bordercolor: "rgba(0,0,0,0.1)", font: { family: FONT_FAMILY, size: 12, color: "#37352f" } },
  };

  return (
    <section style={styles.card}>
      <div style={styles.cardHeader}>
        <div>
          <div style={styles.processBadge}>{processName}</div>
          <h3 style={styles.title}>Yield Trend — Revision Comparison</h3>
          <div style={styles.compareNote}>
            Work Week ごとに品種別 Bin stack を横に並べ、Yield ラインを重ねて表示
          </div>
        </div>
        <div style={styles.stats}>
          {productNames.map((product, i) => {
            const d = productData[product];
            const lastNonNull = [...d.yield_avg].reverse().find((v): v is number => v != null);
            const latestYield = lastNonNull ?? 0;
            return (
              <div key={product} style={styles.statItem}>
                <div style={{ ...styles.statLabel, display: "flex", alignItems: "center", gap: 4, justifyContent: "flex-end" }}>
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: PRODUCT_COLORS[i % PRODUCT_COLORS.length], flexShrink: 0, display: "inline-block" }} />
                  {product}
                </div>
                <div style={styles.statValue}>{latestYield.toFixed(2)}%</div>
              </div>
            );
          })}
        </div>
      </div>
      <Plot
        data={[...barTraces, ...lineTraces]}
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
  compareNote: {
    fontSize: 12,
    color: "var(--gray-400)",
    marginTop: 2,
    lineHeight: 1.4,
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
