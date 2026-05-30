interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  color?: string;
}

export default function Sparkline({
  values, width = 90, height = 22, color = "#0075de",
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
  return (
    <svg width={width} height={height} aria-hidden>
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}
