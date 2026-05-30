import Plot from "../PlotlyChart";
import type { LotData } from "../../types";
import { formatLotId, type LotIdFormat } from "../../utils/formatLotId";

interface Props {
  lots: LotData[];
  format: LotIdFormat;
}

export default function LotTrendChart({ lots, format }: Props) {
  const x = lots.map((l) => formatLotId(l.lot_id, l.lot_date, format));
  const y = lots.map((l) => l.yield_pct);
  const warnIdx = lots
    .map((l, i) => (l.warnings.length > 0 ? i : -1))
    .filter((i) => i >= 0);

  const traces: Plotly.Data[] = [
    {
      x,
      y,
      type: "scatter" as const,
      mode: "lines+markers" as const,
      name: "歩留り",
      line: { color: "#3a7bbf" },
      marker: { size: 6 },
    },
    {
      x: warnIdx.map((i) => x[i]),
      y: warnIdx.map((i) => y[i]),
      type: "scatter" as const,
      mode: "markers" as const,
      name: "要注意",
      marker: { size: 12, color: "#b13a2a", symbol: "circle-open", line: { width: 2 } },
    },
  ];

  return (
    <Plot
      data={traces}
      layout={{
        height: 320,
        margin: { t: 20, r: 20, b: 60, l: 50 },
        yaxis: { title: { text: "歩留り (%)" }, range: [0, 102] },
        xaxis: { tickangle: -45 },
        showlegend: true,
      }}
      style={{ width: "100%" }}
      useResizeHandler
      config={{ displayModeBar: false }}
    />
  );
}
