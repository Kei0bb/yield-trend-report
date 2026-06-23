interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  color?: string;
  target?: number | null;
}

export default function Sparkline({
  values, width = 90, height = 22, color = "#0075de", target,
}: SparklineProps) {
  if (values.length < 2) {
    return <svg width={width} height={height} />;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const stepX = width / (values.length - 1);
  const points = values
    .map((v, i) => {
      const x = i * stepX;
      const y = height - ((v - min) / span) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  // Same y-scale as the plotted values above — only drawn when it falls
  // within the values' range so it doesn't distort the sparkline's scale.
  const showTarget = target != null && target >= min && target <= max;
  const targetY = showTarget ? height - ((target! - min) / span) * height : 0;
  return (
    <svg width={width} height={height} aria-hidden>
      {showTarget && (
        <line
          x1={0}
          y1={targetY}
          x2={width}
          y2={targetY}
          stroke="rgba(0,0,0,0.25)"
          strokeWidth={1}
          strokeDasharray="3 3"
        />
      )}
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}
