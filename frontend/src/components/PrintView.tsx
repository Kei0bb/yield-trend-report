import Plot from "./PlotlyChart";
import type { YieldRequest, YieldResponse, ProcessData } from "../types";
import { BIN_COLORS, PRODUCT_COLORS, FONT_FAMILY, YIELD_LINE_COLOR } from "../theme";

interface PrintViewProps {
  data: YieldResponse;
  request: YieldRequest;
}

const PROCESS_ORDER = ["CP", "FT", "SLT"];
const COMPANY_NAME = "Yield Trend Report";

// Build Plotly traces for a single-product page
function buildSingleTraces(data: ProcessData): { traces: Plotly.Data[]; layout: Partial<Plotly.Layout> } {
  const binNames = Object.keys(data.fail_bins);

  const barTraces: Plotly.Data[] = binNames.map((binName, i) => ({
    x: data.lots,
    y: data.fail_bins[binName],
    name: binName,
    type: "bar" as const,
    marker: { color: BIN_COLORS[i % BIN_COLORS.length], opacity: 0.9 },
    yaxis: "y",
  }));

  const lineTrace: Plotly.Data = {
    x: data.lots,
    y: data.yield_avg,
    name: "Yield (%)",
    type: "scatter" as const,
    mode: "lines+markers" as const,
    line: { color: YIELD_LINE_COLOR, width: 2, shape: "spline" },
    marker: { size: 6, color: YIELD_LINE_COLOR },
    yaxis: "y2",
  };

  const layout: Partial<Plotly.Layout> = {
    barmode: "stack",
    font: { family: FONT_FAMILY, size: 11, color: "#37352f" },
    xaxis: { tickangle: -30, tickfont: { size: 10 }, gridcolor: "rgba(0,0,0,0.04)" },
    yaxis: { title: { text: "Fail Bin (%)" }, side: "left", rangemode: "tozero", tickfont: { size: 10 }, gridcolor: "rgba(0,0,0,0.04)" },
    yaxis2: { title: { text: "Yield (%)" }, side: "right", overlaying: "y", range: [80, 100], tickfont: { size: 10 }, showgrid: false },
    legend: { orientation: "h", y: -0.38, x: 0.5, xanchor: "center", yanchor: "bottom", font: { size: 10 } },
    margin: { l: 56, r: 56, t: 12, b: 110 },
    plot_bgcolor: "#ffffff",
    paper_bgcolor: "#ffffff",
    height: 380,
  };

  return { traces: [...barTraces, lineTrace], layout };
}

// Build Plotly traces for a multi-product page
function buildMultiTraces(
  products: string[],
  productData: Record<string, ProcessData>
): { traces: Plotly.Data[]; layout: Partial<Plotly.Layout> } {
  const allBinNames = Array.from(
    new Set(products.flatMap((p) => Object.keys(productData[p]?.fail_bins ?? {})))
  );

  const barTraces: Plotly.Data[] = products.flatMap((product, pIdx) =>
    allBinNames.map((binName, bIdx) => {
      const d = productData[product];
      const y = d?.fail_bins[binName] ?? d?.lots.map(() => 0) ?? [];
      return {
        x: d?.lots ?? [],
        y,
        name: binName,
        type: "bar" as const,
        marker: { color: BIN_COLORS[bIdx % BIN_COLORS.length], opacity: 0.9 },
        yaxis: "y",
        offsetgroup: product,
        legendgroup: binName,
        showlegend: pIdx === 0,
      } as unknown as Plotly.Data;
    })
  );

  const allYields = products.flatMap((p) => productData[p]?.yield_avg ?? []);
  const yMin = allYields.length > 0 ? Math.min(...allYields) : 80;
  const yMax = allYields.length > 0 ? Math.max(...allYields) : 100;
  const yPad = Math.max((yMax - yMin) * 0.5, 2);

  const lineTraces: Plotly.Data[] = products.map((product, i) => ({
    x: productData[product]?.lots ?? [],
    y: productData[product]?.yield_avg ?? [],
    name: `Yield · ${product}`,
    type: "scatter" as const,
    mode: "lines+markers" as const,
    line: { color: PRODUCT_COLORS[i % PRODUCT_COLORS.length], width: 2, shape: "spline" },
    marker: { size: 6, color: PRODUCT_COLORS[i % PRODUCT_COLORS.length] },
    yaxis: "y2",
  }));

  const layout: Partial<Plotly.Layout> = {
    barmode: "stack",
    bargap: 0.25,
    bargroupgap: 0.08,
    font: { family: FONT_FAMILY, size: 11, color: "#37352f" },
    xaxis: { title: { text: "Work Week" }, tickangle: -30, tickfont: { size: 10 }, gridcolor: "rgba(0,0,0,0.04)" },
    yaxis: { title: { text: "Fail Bin (%)" }, side: "left", rangemode: "tozero", tickfont: { size: 10 }, gridcolor: "rgba(0,0,0,0.04)" },
    yaxis2: { title: { text: "Yield (%)" }, side: "right", overlaying: "y", range: [Math.max(0, yMin - yPad), Math.min(100, yMax + yPad)], tickfont: { size: 10 }, showgrid: false },
    legend: { orientation: "h", y: -0.38, x: 0.5, xanchor: "center", yanchor: "bottom", font: { size: 10 } },
    margin: { l: 56, r: 56, t: 12, b: 110 },
    plot_bgcolor: "#ffffff",
    paper_bgcolor: "#ffffff",
    height: 380,
  };

  return { traces: [...barTraces, ...lineTraces], layout };
}

export default function PrintView({ data, request }: PrintViewProps) {
  const sortedProcesses = Object.keys(data.data).sort(
    (a, b) => PROCESS_ORDER.indexOf(a) - PROCESS_ORDER.indexOf(b)
  );

  const firstProcess = sortedProcesses[0];
  const displayNames = firstProcess ? Object.keys(data.data[firstProcess]) : [];
  const isMulti = displayNames.length > 1;
  const titleText = displayNames.join(" vs ") || request.products.join(" vs ");
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className="print-view">
      {sortedProcesses.map((process, pageIdx) => {
        const prodDict = data.data[process];
        const hasData = displayNames.some((d) => prodDict[d]?.lots.length > 0);

        let traces: Plotly.Data[] = [];
        let layout: Partial<Plotly.Layout> = {};
        if (hasData) {
          if (isMulti) {
            ({ traces, layout } = buildMultiTraces(displayNames, prodDict));
          } else {
            ({ traces, layout } = buildSingleTraces(prodDict[displayNames[0]]));
          }
        }

        return (
          <div key={process} className="print-page" style={printPageStyle}>
            {/* Header */}
            <div style={headerStyle}>
              <div>
                <div style={titleStyle}>{titleText}</div>
                <div style={metaStyle}>
                  {process} · Period: {request.start_month} → {request.end_month} · Generated: {today}
                </div>
              </div>
              <div style={confidentialStyle}>CONFIDENTIAL</div>
            </div>

            <div style={dividerStyle} />

            {/* Chart */}
            <div className="print-chart" style={{ flex: 1 }}>
              {hasData ? (
                <Plot
                  data={traces}
                  layout={layout}
                  config={{ staticPlot: true, displayModeBar: false }}
                  style={{ width: "100%", height: "100%" }}
                />
              ) : (
                <div style={noDataStyle}>No data available for {process}</div>
              )}
            </div>

            {/* Footer */}
            <div style={footerStyle}>
              <span>{COMPANY_NAME}</span>
              <span>Page {pageIdx + 1} of {sortedProcesses.length}</span>
              <span>Yield Trend Report · Internal Use Only</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

const printPageStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  height: "100vh",
  padding: "0",
  boxSizing: "border-box",
  fontFamily: FONT_FAMILY,
  color: "#37352f",
  background: "#fff",
};

const headerStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  padding: "10px 0 6px",
};

const titleStyle: React.CSSProperties = {
  fontSize: 20,
  fontWeight: 700,
  letterSpacing: "-0.02em",
  color: "#37352f",
};

const metaStyle: React.CSSProperties = {
  fontSize: 10,
  color: "#615d59",
  marginTop: 3,
};

const confidentialStyle: React.CSSProperties = {
  fontSize: 9,
  fontWeight: 700,
  letterSpacing: "0.08em",
  color: "#fff",
  background: "#c0392b",
  padding: "2px 8px",
  borderRadius: 3,
  alignSelf: "flex-start",
};

const dividerStyle: React.CSSProperties = {
  height: 1,
  background: "rgba(0,0,0,0.15)",
  marginBottom: 8,
};

const footerStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  fontSize: 8,
  color: "#a39e98",
  paddingTop: 6,
  borderTop: "1px solid rgba(0,0,0,0.07)",
};

const noDataStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  height: "100%",
  color: "#a39e98",
  fontSize: 14,
};
