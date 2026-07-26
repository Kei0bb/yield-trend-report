import { useState } from "react";
import { NavLink } from "react-router-dom";

const tabs = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/wafermap", label: "Wafer Map" },
  { to: "/report", label: "Report" },
];

export default function TopNav() {
  const [logoOk, setLogoOk] = useState(true);

  return (
    <nav style={styles.nav}>
      <span style={styles.brand}>PE Portal</span>
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
      {logoOk && (
        <img
          src="/logo.png"
          alt=""
          style={styles.logo}
          onError={() => setLogoOk(false)}
        />
      )}
    </nav>
  );
}

const styles: Record<string, React.CSSProperties> = {
  nav: {
    display: "flex",
    alignItems: "center",
    gap: 4,
    padding: "0 24px",
    height: 52,
    background: "var(--canvas)",
    borderBottom: "var(--hairline)",
    flexShrink: 0,
  },
  brand: {
    fontWeight: 700,
    marginRight: 20,
    color: "var(--ink)",
    letterSpacing: "-0.01em",
  },
  link: {
    padding: "8px 14px",
    borderRadius: "var(--radius-control)",
    textDecoration: "none",
    color: "var(--muted)",
    fontSize: 14,
    fontWeight: 500,
  },
  linkActive: { background: "var(--surface-soft)", color: "var(--ink)" },
  logo: {
    marginLeft: "auto",
    height: 28,
    width: "auto",
    objectFit: "contain",
  },
};
