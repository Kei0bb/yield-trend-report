import { useEffect, useRef } from "react";
import type { WaferMapWafer } from "../../types";

interface WaferMapCanvasProps {
  wafer: WaferMapWafer;
  colorFor: (bin: number) => string;
  passBinCodes: number[];
  selectedBins: number[];
  size?: number;
}

export default function WaferMapCanvas({
  wafer,
  colorFor,
  passBinCodes,
  selectedBins,
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
    const spanX = maxX - minX + 1;
    const spanY = maxY - minY + 1;
    const cellX = size / (spanX + 2);
    const cellY = size / (spanY + 2);

    ctx.clearRect(0, 0, size, size);
    ctx.fillStyle = "#f3f2f0"; // wafer disc
    ctx.beginPath();
    ctx.arc(size / 2, size / 2, size / 2 - 1, 0, Math.PI * 2);
    ctx.fill();

    for (let i = 0; i < wafer.x.length; i++) {
      const b = wafer.bin[i];
      const isPass = passBinCodes.includes(b);
      let color: string;
      if (selectedBins.length) color = selectedBins.includes(b) ? colorFor(b) : "#eceae7";
      else color = isPass ? "#e3e1de" : colorFor(b);
      ctx.fillStyle = color;
      ctx.fillRect(
        (wafer.x[i] - minX + 1) * cellX,
        (wafer.y[i] - minY + 1) * cellY, // +Y down (correct wafer orientation)
        Math.max(cellX - 0.5, 0.5),
        Math.max(cellY - 0.5, 0.5),
      );
    }
  }, [wafer, colorFor, passBinCodes, selectedBins, size]);

  return (
    <canvas
      ref={ref}
      style={{ width: size, height: size }}
      title={`${wafer.lot_id} / W${wafer.wafer_id}`}
    />
  );
}
