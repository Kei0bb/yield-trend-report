import type { ButtonHTMLAttributes, CSSProperties } from "react";

type Variant = "primary" | "secondary" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

/** Kit button. primary = coral (one main action per view); secondary = white
 *  with hairline; ghost = borderless coral text link-button. */
export default function Button({ variant = "secondary", disabled, style, ...rest }: ButtonProps) {
  const merged: CSSProperties = {
    ...base,
    ...variants[variant],
    ...(disabled ? disabledStyles[variant] : {}),
    ...style,
  };
  return <button disabled={disabled} style={merged} {...rest} />;
}

const base: CSSProperties = {
  height: 36,
  padding: "0 16px",
  borderRadius: "var(--radius-control)",
  fontSize: 13,
  fontWeight: 500,
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 6,
  whiteSpace: "nowrap",
};

const variants: Record<Variant, CSSProperties> = {
  primary: { background: "var(--primary)", color: "#ffffff", border: "none" },
  secondary: { background: "var(--surface-card)", color: "var(--ink)", border: "var(--hairline)" },
  ghost: { background: "none", color: "var(--primary)", border: "none", padding: 0, height: "auto", fontSize: 12 },
};

const disabledStyles: Record<Variant, CSSProperties> = {
  primary: { background: "var(--primary-disabled)", color: "var(--muted)", cursor: "not-allowed" },
  secondary: { opacity: 0.5, cursor: "not-allowed" },
  ghost: { opacity: 0.5, cursor: "not-allowed" },
};
