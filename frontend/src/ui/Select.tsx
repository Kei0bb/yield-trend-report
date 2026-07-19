import type { CSSProperties, SelectHTMLAttributes } from "react";

/** Kit select: 36px, hairline border, control radius. Focus ring comes from
 *  the global select:focus rule in index.css (coral). */
export default function Select({ style, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select style={{ ...base, ...style }} {...rest} />;
}

const base: CSSProperties = {
  height: 36,
  padding: "0 10px",
  borderRadius: "var(--radius-control)",
  border: "var(--hairline)",
  background: "var(--surface-card)",
  color: "var(--ink)",
  fontSize: 13,
  fontFamily: "var(--font-sans)",
};
