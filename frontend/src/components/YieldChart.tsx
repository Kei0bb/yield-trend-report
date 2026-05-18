import Plot from "./PlotlyChart";
import type { ProcessData } from "../types";

// Notion-inspired accent palette for fail bins
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

// 複数品種比較用カラー（品種ラベル・Yield line に割り当て）
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

const FONT_FAMILY =
  "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif";

interface YieldChartProps {
  processName: string;
  /** product -> ProcessData */
  productData: Record<string, ProcessData>;
}

// 1品種分のチャートトレースとレイアウトを生成する共通ヘルパー
function buildSingleProductChart(
  data: ProcessData,
  yieldLineColor: string,
  yieldRange: [number, number],
  height: number
) {
  const binNames = Object.keys(data.fail_bins);

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
    line: { color: yieldLineColor, width: 2.5, shape: "spline" },
    marker: { size: 6, color: yieldLineColor },
    yaxis: "y2",
    hovertemplate: "%{x}<br>Yield: %{y:.2f}%<extra></extra>",
  };

  const layout: Partial<Plotly.Layout> = {
    barmode: "stack",
    font: { family: FONT_FAMILY, size: 11, color: "#37352f" },
    xaxis: {
      tickangle: -30,
      tickfont: { size: 10, color: "#615d59" },
      gridcolor: "rgba(0,0,0,0.04)",
      linecolor: "rgba(0,0,0,0.1)",
    },
    yaxis: {
      title: { text: "Fail Bin (%)", font: { size: 10, color: "#787672" } },
      side: "left",
      rangemode: "tozero",
      tickfont: { size: 10, color: "#615d59" },
      gridcolor: "rgba(0,0,0,0.04)",
      zerolinecolor: "rgba(0,0,0,0.08)",
    },
    yaxis2: {
      title: { text: "Yield (%)", font: { size: 10, color: "#787672" } },
      side: "right",
      overlaying: "y",
      range: yieldRange,
      tickfont: { size: 10, color: "#615d59" },
      showgrid: false,
    },
    legend: {
      orientation: "h",
      yanchor: "bottom",
      y: -0.45,
      xanchor: "center",
      x: 0.5,
      font: { size: 10, color: "#615d59" },
      bgcolor: "rgba(0,0,0,0)",
    },
    margin: { l: 50, r: 50, t: 8, b: 100 },
    plot_bgcolor: "#ffffff",
    paper_bgcolor: "#ffffff",
    height,
    hoverlabel: {
      bgcolor: "#ffffff",
      bordercolor: "rgba(0,0,0,0.1)",
      font: { family: FONT_FAMILY, size: 11, color: "#37352f" },
    },
  };

  return { traces: [...barTraces, lineTrace], layout, binNames };
}

export default function YieldChart({ processName, productData }: YieldChartProps) {
  const productNames = Object.keys(productData);
  const isMulti = productNames.length > 1;

  // 全品種の Yield 最小・最大から共通スケールを計算（比較を公平にするため）
  const allYields = productNames.flatMap((p) => productData[p].yield_avg);
  const yMin = allYields.length > 0 ? Math.min(...allYields) : 80;
  const yMax = allYields.length > 0 ? Math.max(...allYields) : 100;
  const yPad = Math.max((yMax - yMin) * 0.5, 2);
  const yieldRange: [number, number] = [
    Math.max(0, Math.floor(yMin - yPad)),
    Math.min(100, Math.ceil(yMax + yPad)),
  ];

  // ── 単一品種 ────────────────────────────────────────────────────
  if (!isMulti) {
    const data = productData[productNames[0]];
    const avg =
      data.yield_avg.length > 0
        ? data.yield_avg.reduce((a, b) => a + b, 0) / data.yield_avg.length
        : 0;
    const { traces, layout } = buildSingleProductChart(
      data,
      "#0075de",
      yieldRange,
      420
    );
    // 単一品種は余裕のある margin を戻す
    layout.margin = { l: 56, r: 56, t: 16, b: 110 };
    layout.height = 420;
    (layout as any).legend = {
      orientation: "h",
      yanchor: "bottom",
      y: -0.4,
      xanchor: "center",
      x: 0.5,
      font: { size: 11, color: "#615d59" },
      bgcolor: "rgba(0,0,0,0)",
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
          </div>
        </div>
        <Plot
          data={traces}
          layout={layout}
          config={{ responsive: true, displayModeBar: false }}
          style={{ width: "100%" }}
          useResizeHandler
        />
      </section>
    );
  }

  // ── 複数品種: 同一チャートに grouped stacked bar + 品種別 Yield line ──
  // 全 bin 名のユニオン（凡例を一意に保つ）
  const allBinNames = Array.from(
    new Set(productNames.flatMap((p) => Object.keys(productData[p].fail_bins)))
  );

  // Bar traces: 品種 × bin の組み合わせ
  // offsetgroup=product で同じ品種のbinsが積み上がり、品種間は横に並ぶ
  const multiBarTraces: Plotly.Data[] = productNames.flatMap((product, pIdx) =>
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
        // offsetgroup: 同じ product のbarsは積み上げ、product間は side-by-side
        offsetgroup: product,
        legendgroup: binName,
        showlegend: pIdx === 0, // 凡例は最初の品種のみ表示
        hovertemplate: `<b>${product}</b> @ %{x}<br>${binName}: %{y:.3f}%<extra></extra>`,
      } as unknown as Plotly.Data;
    })
  );

  // 品種別 Yield line（右Y軸）
  const multiLineTraces: Plotly.Data[] = productNames.map((product, i) => {
    const d = productData[product];
    const color = PRODUCT_COLORS[i % PRODUCT_COLORS.length];
    return {
      x: d.lots,
      y: d.yield_avg,
      name: `Yield · ${product}`,
      type: "scatter" as const,
      mode: "lines+markers" as const,
      line: { color, width: 2.5, shape: "spline" },
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
      range: yieldRange,
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
    height: 460,
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
          <h3 style={styles.title}>Yield Trend — Revision Comparison</h3>
          <div style={styles.compareNote}>
            Work Week ごとに品種別 Bin stack を横に並べ、Yield ラインを重ねて表示
          </div>
        </div>
        {/* 品種ごとの平均 Yield を右端に表示 */}
        <div style={styles.stats}>
          {productNames.map((product, i) => {
            const d = productData[product];
            const avg =
              d.yield_avg.length > 0
                ? d.yield_avg.reduce((a, b) => a + b, 0) / d.yield_avg.length
                : 0;
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
                      background: PRODUCT_COLORS[i % PRODUCT_COLORS.length],
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
        data={[...multiBarTraces, ...multiLineTraces]}
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
  compareNote: {
    fontSize: 12,
    color: "var(--gray-400)",
    marginTop: 2,
    lineHeight: 1.4,
  },
  // 未使用（旧マルチグリッド・残置）
  _unused: {
    fontSize: 12,
    fontWeight: 600,
    marginBottom: 2,
    marginLeft: 4,
  },
};
