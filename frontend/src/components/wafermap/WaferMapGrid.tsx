import type { WaferMapWafer } from "../../types";
import WaferMapCanvas from "./WaferMapCanvas";

interface WaferMapGridProps {
  wafers: WaferMapWafer[];
  colorFor: (bin: number) => string;
  passBinCodes: number[];
  selectedBin: number | null;
}

export default function WaferMapGrid({ wafers, colorFor, passBinCodes, selectedBin }: WaferMapGridProps) {
  if (wafers.length === 0) return null;

  // Group wafers by lot_id, preserving first-seen lot order.
  const lotOrder: string[] = [];
  const byLot = new Map<string, WaferMapWafer[]>();
  for (const w of wafers) {
    if (!byLot.has(w.lot_id)) {
      byLot.set(w.lot_id, []);
      lotOrder.push(w.lot_id);
    }
    byLot.get(w.lot_id)!.push(w);
  }

  return (
    <div style={styles.wrap}>
      {lotOrder.map((lotId) => {
        const lotWafers = byLot.get(lotId)!;
        return (
          <div key={lotId} style={styles.lotSection}>
            <div style={styles.lotHeading}>
              {lotId} <span style={styles.lotCount}>· {lotWafers.length}w</span>
            </div>
            <div style={styles.waferRow}>
              {lotWafers.map((wafer) => (
                <div key={`${wafer.lot_id}-${wafer.wafer_id}`} style={styles.waferItem}>
                  <WaferMapCanvas
                    wafer={wafer}
                    colorFor={colorFor}
                    passBinCodes={passBinCodes}
                    selectedBin={selectedBin}
                  />
                  <div style={styles.caption}>W{wafer.wafer_id}</div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrap: { display: "flex", flexDirection: "column", gap: 24 },
  lotSection: {},
  lotHeading: {
    fontSize: 13,
    fontWeight: 600,
    color: "var(--gray-700)",
    marginBottom: 10,
  },
  lotCount: { fontWeight: 400, color: "var(--gray-400)" },
  waferRow: { display: "flex", flexWrap: "wrap", gap: 16 },
  waferItem: { display: "flex", flexDirection: "column", alignItems: "center", gap: 4 },
  caption: {
    fontSize: 11,
    color: "var(--gray-400)",
    fontVariantNumeric: "tabular-nums",
  },
};
