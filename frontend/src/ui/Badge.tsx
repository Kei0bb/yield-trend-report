import type { CSSProperties, ReactNode } from "react";

type Variant = "neutral" | "success" | "warning" | "error";

interface BadgeProps {
  variant?: Variant;
  children: ReactNode;
}

/** Pill badge; tinted background + readable darker text per semantic state. */
export default function Badge({ variant = "neutral", children }: BadgeProps) {
  return <span style={{ ...base, ...variants[variant] }}>{children}</span>;
}

const base: CSSProperties = {
  display: "inline-block",
  padding: "2px 10px",
  borderRadius: "var(--radius-pill)",
  fontSize: 11,
  fontWeight: 500,
  letterSpacing: "0.02em",
  whiteSpace: "nowrap",
};

const variants: Record<Variant, CSSProperties> = {
  neutral: { background: "var(--surface-soft)", color: "var(--body)" },
  success: { background: "rgba(93, 184, 114, 0.14)", color: "#3e7d4f" },
  warning: { background: "rgba(212, 160, 23, 0.14)", color: "#8a6a0f" },
  error: { background: "rgba(198, 69, 69, 0.12)", color: "var(--error)" },
};
