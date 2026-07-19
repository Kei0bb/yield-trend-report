import type { CSSProperties, ReactNode } from "react";

interface CardProps {
  title?: ReactNode;
  headerRight?: ReactNode;
  style?: CSSProperties;
  bodyStyle?: CSSProperties;
  children: ReactNode;
}

/** White card on the cream canvas: hairline border, 12px radius, padding 20,
 *  no resting shadow (elevation = surface contrast, per design spec). */
export default function Card({ title, headerRight, style, bodyStyle, children }: CardProps) {
  return (
    <section style={{ ...styles.card, ...style }}>
      {(title || headerRight) && (
        <div style={styles.header}>
          {title && <span style={styles.title}>{title}</span>}
          {headerRight && <div style={styles.headerRight}>{headerRight}</div>}
        </div>
      )}
      <div style={{ ...styles.body, ...bodyStyle }}>{children}</div>
    </section>
  );
}

const styles: Record<string, CSSProperties> = {
  card: {
    background: "var(--surface-card)",
    border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    padding: 20,
    display: "flex",
    flexDirection: "column",
    minWidth: 0,
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
    marginBottom: 12,
  },
  title: { fontSize: 14, fontWeight: 600, color: "var(--ink)" },
  headerRight: { display: "flex", alignItems: "center", gap: 10 },
  body: { flex: 1, minHeight: 0, display: "flex", flexDirection: "column", minWidth: 0 },
};
