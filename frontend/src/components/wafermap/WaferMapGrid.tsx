import type { WaferMapWafer } from "../../types";
import WaferMapCanvas from "./WaferMapCanvas";

interface WaferMapGridProps {
  wafers: WaferMapWafer[];
  colorFor: (bin: number) => string;
  passBinCodes: number[];
  selectedBin: number | null;
}

/** A lot always holds 25 wafer slots — columns are fixed W1..W25. */
const LOT_WAFER_SLOTS = 25;

/** Normalize a wafer id for slot matching: "01"/"1"/1 all map to "1";
 *  non-numeric ids pass through unchanged. */
const slotKey = (wid: string): string => {
  const n = Number(wid);
  return Number.isNaN(n) ? wid : String(n);
};

/** Matrix layout: lots as rows, fixed wafer slots W1..W25 as columns, one
 *  canvas per cell. Untested slots render an em-dash placeholder. */
export default function WaferMapGrid({ wafers, colorFor, passBinCodes, selectedBin }: WaferMapGridProps) {
  if (wafers.length === 0) return null;

  // Preserve first-seen lot order for rows; index wafers by (lot, slot).
  const lotOrder: string[] = [];
  const byKey = new Map<string, WaferMapWafer>();
  const extraIds = new Set<string>();
  for (const w of wafers) {
    if (!byKey.has(`${w.lot_id}|`)) {
      // marker key per lot so includes() isn't needed
      byKey.set(`${w.lot_id}|`, w);
      lotOrder.push(w.lot_id);
    }
    const key = slotKey(w.wafer_id);
    const n = Number(key);
    if (Number.isNaN(n) || n < 1 || n > LOT_WAFER_SLOTS) extraIds.add(key);
    byKey.set(`${w.lot_id}|${key}`, w);
  }
  // Fixed 1..25 columns, plus any out-of-range/non-numeric ids so no data hides.
  const cols = [
    ...Array.from({ length: LOT_WAFER_SLOTS }, (_, i) => String(i + 1)),
    ...[...extraIds].sort((a, b) => a.localeCompare(b, undefined, { numeric: true })),
  ];

  return (
    <div style={styles.scroll}>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.corner} />
            {cols.map((wid) => (
              <th key={wid} style={styles.colHead}>W{wid}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lotOrder.map((lot) => (
            <tr key={lot}>
              <th style={styles.rowHead}>
                <span title={lot} style={styles.rowHeadText}>{lot}</span>
              </th>
              {cols.map((wid) => {
                const w = byKey.get(`${lot}|${slotKey(wid)}`);
                return (
                  <td key={wid} style={styles.cell}>
                    {w ? (
                      <WaferMapCanvas
                        wafer={w}
                        colorFor={colorFor}
                        passBinCodes={passBinCodes}
                        selectedBin={selectedBin}
                        size={92}
                      />
                    ) : (
                      <span style={styles.noWafer}>—</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  scroll: { overflowX: "auto", maxWidth: "100%" },
  table: { borderCollapse: "collapse" },
  corner: { padding: "4px 8px" },
  colHead: {
    padding: "4px 8px",
    textAlign: "center",
    fontSize: 11,
    fontWeight: 600,
    color: "var(--gray-500)",
    fontVariantNumeric: "tabular-nums",
    whiteSpace: "nowrap",
  },
  rowHead: {
    padding: "4px 10px",
    textAlign: "right",
    fontSize: 11,
    fontWeight: 600,
    color: "var(--gray-500)",
    whiteSpace: "nowrap",
    maxWidth: 180,
  },
  rowHeadText: {
    display: "block",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  cell: { padding: 6, textAlign: "center", verticalAlign: "middle" },
  noWafer: { color: "var(--gray-300, #ccc)", fontSize: 12 },
};
