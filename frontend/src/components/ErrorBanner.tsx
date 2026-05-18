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
    background: "#fff2f2",
    border: "1px solid rgba(224, 62, 62, 0.3)",
    borderRadius: 8,
    margin: "0 16px 16px",
    fontSize: 13,
    color: "#c0392b",
  },
  icon: {
    flexShrink: 0,
    fontSize: 14,
  },
  text: {
    flex: 1,
    lineHeight: 1.4,
  },
  close: {
    flexShrink: 0,
    background: "none",
    border: "none",
    cursor: "pointer",
    color: "#c0392b",
    fontSize: 12,
    padding: "2px 4px",
    opacity: 0.7,
  },
};
