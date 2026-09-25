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
  letterSpacing: 0,
  whiteSpace: "nowrap",
};

const variants: Record<Variant, CSSProperties> = {
  neutral: { background: "var(--surface-soft)", color: "var(--body)" },
  success: { background: "var(--success-soft)", color: "var(--success-deep)" },
  warning: { background: "var(--warning-soft)", color: "var(--warning-deep)" },
  error: { background: "var(--error-soft)", color: "var(--error-deep)" },
};
