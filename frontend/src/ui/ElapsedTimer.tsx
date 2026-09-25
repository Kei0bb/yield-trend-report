import { useEffect, useState } from "react";

interface ElapsedTimerProps {
  /** ms epoch when the tracked operation started. */
  startedAt: number;
  /** Prefix, e.g. "Loading data" or "Refreshing" — rendered as "{label}… Ns". */
  label: string;
}

/** Ticks its own interval so callers don't need an effect that calls
 *  setState synchronously on mount (which would trip
 *  react-hooks/set-state-in-effect) — the setState happens inside the
 *  interval callback, which the rule allows. */
export default function ElapsedTimer({ startedAt, label }: ElapsedTimerProps) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const elapsed = Math.max(0, Math.floor((now - startedAt) / 1000));
  return <span>{label}… {elapsed}s</span>;
}
