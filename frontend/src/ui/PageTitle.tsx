import type { CSSProperties, ReactNode } from "react";

interface PageTitleProps {
  title: ReactNode;
  subtext?: ReactNode;
}

/** Page heading: 26/700 ink title with an optional subtext line below. */
export default function PageTitle({ title, subtext }: PageTitleProps) {
  return (
    <header style={styles.header}>
      <h1 style={styles.title}>{title}</h1>
      {subtext && <div style={styles.subtext}>{subtext}</div>}
    </header>
  );
}

const styles: Record<string, CSSProperties> = {
  header: { marginBottom: 24 },
  title: {
    fontSize: 26,
    fontWeight: 700,
    color: "var(--ink)",
    letterSpacing: "-0.02em",
    lineHeight: 1.2,
  },
  subtext: { marginTop: 10, fontSize: 13, color: "var(--muted)" },
};
