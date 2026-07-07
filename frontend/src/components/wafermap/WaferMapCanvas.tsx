import { useEffect, useRef } from "react";
import type { WaferMapWafer } from "../../types";

interface WaferMapCanvasProps {
  wafer: WaferMapWafer;
  colorFor: (bin: number) => string;
  passBinCodes: number[];
  selectedBin: number | null;
  size?: number;
}

export default function WaferMapCanvas({
  wafer,
  colorFor,
  passBinCodes,
  selectedBin,
  size = 120,
}: WaferMapCanvasProps) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const dpr = window.devicePixelRatio || 1;
    cv.width = size * dpr;
    cv.height = size * dpr;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    const minX = Math.min(...wafer.x);
    const maxX = Math.max(...wafer.x);
    const minY = Math.min(...wafer.y);
    const maxY = Math.max(...wafer.y);
    const n = Math.max(maxX - minX + 1, maxY - minY + 1);
    const cell = size / (n + 2); // 1-cell margin

    ctx.clearRect(0, 0, size, size);
    ctx.fillStyle = "#f3f2f0"; // wafer disc
    ctx.beginPath();
    ctx.arc(size / 2, size / 2, size / 2 - 1, 0, Math.PI * 2);
    ctx.fill();

    for (let i = 0; i < wafer.x.length; i++) {
      const b = wafer.bin[i];
      const isPass = passBinCodes.includes(b);
      let color: string;
      if (selectedBin != null) color = b === selectedBin ? colorFor(b) : "#eceae7";
      else color = isPass ? "#e3e1de" : colorFor(b);
      ctx.fillStyle = color;
      ctx.fillRect(
        (wafer.x[i] - minX + 1) * cell + size / 2 - ((n + 2) * cell) / 2,
        (maxY - wafer.y[i] + 1) * cell + size / 2 - ((n + 2) * cell) / 2, // +Y up
        Math.max(cell - 0.5, 0.5),
        Math.max(cell - 0.5, 0.5),
      );
    }
  }, [wafer, colorFor, passBinCodes, selectedBin, size]);

  return (
    <canvas
      ref={ref}
      style={{ width: size, height: size }}
      title={`${wafer.lot_id} / W${wafer.wafer_id}`}
    />
  );
}
