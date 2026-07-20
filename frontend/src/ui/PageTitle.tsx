import type { CSSProperties, ReactNode } from "react";

interface PageTitleProps {
  breadcrumb?: string;
  title: ReactNode;
  subtext?: ReactNode;
}

/** Page heading: 26/700 ink title with an optional muted breadcrumb above
 *  and subtext line below. */
export default function PageTitle({ breadcrumb, title, subtext }: PageTitleProps) {
  return (
    <header style={styles.header}>
      {breadcrumb && <div style={styles.breadcrumb}>{breadcrumb}</div>}
      <h1 style={styles.title}>{title}</h1>
      {subtext && <div style={styles.subtext}>{subtext}</div>}
    </header>
  );
}

const styles: Record<string, CSSProperties> = {
  header: { marginBottom: 24 },
  breadcrumb: {
    fontSize: 12,
    color: "var(--muted-soft)",
    fontWeight: 500,
    letterSpacing: "0.02em",
    marginBottom: 8,
  },
  title: {
    fontSize: 26,
    fontWeight: 700,
    color: "var(--ink)",
    letterSpacing: "-0.02em",
    lineHeight: 1.2,
  },
  subtext: { marginTop: 10, fontSize: 13, color: "var(--muted)" },
};
