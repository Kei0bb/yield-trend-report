interface SpinnerProps {
  size?: number;
}

/** CSS ring spinner. Keyframes + prefers-reduced-motion handling live in
 *  index.css (`.spinner`) so they're defined once globally. */
export default function Spinner({ size = 20 }: SpinnerProps) {
  return <span className="spinner" style={{ width: size, height: size }} aria-hidden="true" />;
}
