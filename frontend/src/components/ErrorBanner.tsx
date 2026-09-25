interface ErrorBannerProps {
  message: string;
  onDismiss: () => void;
}

export default function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div style={styles.banner} role="alert">
      <span style={styles.icon}>⚠</span>
      <span style={styles.text}>{message}</span>
      <button style={styles.close} onClick={onDismiss} aria-label="Dismiss">✕</button>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  banner: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "10px 16px",
    background: "var(--error-soft)",
    border: "1px solid rgba(238, 0, 0, 0.25)",
    borderRadius: "var(--radius-control)",
    margin: "0 16px 16px",
    fontSize: 13,
    color: "var(--error-deep)",
  },
  icon: { flexShrink: 0, fontSize: 14 },
  text: { flex: 1, lineHeight: 1.4 },
  close: {
    flexShrink: 0,
    background: "none",
    border: "none",
    cursor: "pointer",
    color: "var(--error)",
    fontSize: 12,
    padding: "2px 4px",
    opacity: 0.7,
  },
};
