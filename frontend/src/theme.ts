// Shared design tokens used by chart components and print view.
// Edit here to change colors site-wide — do not duplicate in individual files.
// Palette source: docs/superpowers/specs/2026-09-25-design-refresh-vercel-style-design.md

/** Categorical fail-bin palette. Mirrored in backend/app/services/pdf_service.py
 *  BIN_COLORS — keep the two lists identical so screen and PDF agree.
 *
 *  The ORDER is the colorblind-safety mechanism, not cosmetic: this sequence
 *  was validated for adjacent stacked segments on a white surface (worst
 *  adjacent CVD ΔE 9.1, normal-vision ΔE 19.6). Reordering or inserting a hue
 *  voids that — re-validate before touching it. */
export const BIN_COLORS = [
  "#2a78d6", // blue
  "#eb6834", // orange
  "#1baf7a", // aqua
  "#eda100", // yellow
  "#e87ba4", // magenta
  "#008300", // green
  "#4a3aa7", // violet
  "#e34948", // red
];

export const FONT_FAMILY =
  "'Inter Variable', Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif";

// Vercel-style ink/hairline chart chrome
export const INK = "#171717";
export const MUTED = "#666666";
export const MUTED_SOFT = "#888888";
export const GRID = "#f2f2f2";
export const AXIS_LINE = "#ebebeb";

export const YIELD_LINE_COLOR = INK;

/** Base Plotly layout shared by all charts: white paper (charts live inside
 *  white cards), hairline grid, ink text. Spread first, then override. */
export function plotlyBaseLayout(): Partial<Plotly.Layout> {
  return {
    font: { family: FONT_FAMILY, size: 11, color: INK },
    plot_bgcolor: "#ffffff",
    paper_bgcolor: "#ffffff",
    hoverlabel: {
      bgcolor: "#ffffff",
      bordercolor: AXIS_LINE,
      font: { family: FONT_FAMILY, size: 11, color: INK },
    },
  };
}

/** Wafer number is an ordered quantity, so it gets a single-hue light→dark
 *  ramp with a colorbar — not 25 categorical swatches, and never a rainbow. */
export const WAFER_COLORSCALE: [number, string][] = [
  [0.0, "#d3e5ff"],
  [0.5, "#0070f3"],
  [1.0, "#0a3a82"],
];

/** PCM/WAT judgement. Reserved status colors — never reused as series colors.
 *  These are CSS custom properties: do NOT hand them to Plotly (marker.color
 *  etc.) — tinycolor cannot resolve `var(...)` and silently falls back to
 *  black. Use STATUS_PLOT_COLOR for anything Plotly-facing. */
export const STATUS_COLOR: Record<string, string> = {
  red: "var(--error-deep)",
  yellow: "var(--warning-deep)",
  gray: "var(--muted-soft)",
  ok: "var(--ink)",
  excluded: "var(--ink)",
};

/** Plotly parses colors with tinycolor and cannot resolve CSS custom
 *  properties — a `var(--error)` marker silently renders black, with no
 *  error. Literal mirror of STATUS_COLOR for anything handed to Plotly.
 *  Values match index.css. They intentionally differ from the backend's
 *  STATUS_HEX (PDF keeps the previous palette — out of scope for the
 *  Vercel refresh). */
export const STATUS_PLOT_COLOR: Record<string, string> = {
  red: "#ee0000", yellow: "#f5a623", gray: "#888888", ok: INK, excluded: INK,
};

/** Printed alongside the color so a black-and-white PDF still carries the
 *  judgement. */
export const STATUS_MARK: Record<string, string> = {
  red: "●",
  yellow: "▲",
  gray: "–",
  ok: "",
  excluded: "",
};

export const SPEC_LINE_COLOR = "#ee0000";
