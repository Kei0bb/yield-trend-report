import { NavLink } from "react-router-dom";

const tabs = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/report", label: "Report" },
];

export default function TopNav() {
  return (
    <nav style={styles.nav}>
      <span style={styles.brand}>Yield</span>
      {tabs.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          style={({ isActive }) => ({
            ...styles.link,
            ...(isActive ? styles.linkActive : {}),
          })}
        >
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}

const styles: Record<string, React.CSSProperties> = {
  nav: {
    display: "flex",
    alignItems: "center",
    gap: 4,
    padding: "0 20px",
    height: 48,
    background: "var(--white)",
    borderBottom: "var(--border-whisper)",
    flexShrink: 0,
  },
  brand: { fontWeight: 700, marginRight: 20, color: "var(--gray-700)" },
  link: {
    padding: "8px 14px",
    borderRadius: 8,
    textDecoration: "none",
    color: "var(--gray-500)",
    fontSize: 14,
    fontWeight: 500,
  },
  linkActive: { background: "var(--badge-bg)", color: "var(--badge-text)" },
};
