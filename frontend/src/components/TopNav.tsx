import { useState } from "react";
import { NavLink } from "react-router-dom";

const tabs = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/report", label: "Report" },
  { to: "/wafermap", label: "Wafer Map" },
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
    background: "var(--white)",
    borderBottom: "var(--border-whisper)",
    flexShrink: 0,
  },
  brand: {
    fontWeight: 700,
    marginRight: 20,
    color: "var(--gray-700)",
    letterSpacing: "-0.01em",
  },
  link: {
    padding: "8px 14px",
    borderRadius: 8,
    textDecoration: "none",
    color: "var(--gray-500)",
    fontSize: 14,
    fontWeight: 500,
  },
  linkActive: { background: "var(--badge-bg)", color: "var(--badge-text)" },
  logo: {
    marginLeft: "auto",
    height: 28,
    width: "auto",
    objectFit: "contain",
  },
};
