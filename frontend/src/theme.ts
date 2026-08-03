// Shared design tokens used by chart components and print view.
// Edit here to change colors site-wide — do not duplicate in individual files.
// Palette source: docs/superpowers/specs/2026-07-19-design-refresh-claude-style-design.md

export const BIN_COLORS = [
  "#2a9d99", // teal
  "#1aae39", // green
  "#dd5b00", // orange
  "#ff64c8", // pink
  "#391c57", // purple
  "#e9b949", // yellow
  "#e03e3e", // red
  "#0075de", // blue
  "#a39e98", // gray
  "#37352f", // warm dark
  "#097fe8", // light blue
  "#005bab", // dark blue
];

export const FONT_FAMILY =
  "'Inter Variable', Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif";

// Claude-style ink/hairline chart chrome
export const INK = "#141413";
export const MUTED = "#6c6a64";
export const MUTED_SOFT = "#8e8b82";
export const GRID = "#efe9de";
export const AXIS_LINE = "#e6dfd8";

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
  [0.0, "#f0d9cf"],
  [0.5, "#cc785c"],
  [1.0, "#5c2f1e"],
];

/** PCM/WAT judgement. Reserved status colors — never reused as series colors. */
export const STATUS_COLOR: Record<string, string> = {
  red: "var(--error)",
  yellow: "var(--warning)",
  gray: "var(--muted-soft)",
  ok: "var(--ink)",
};

/** Printed alongside the color so a black-and-white PDF still carries the
 *  judgement. */
export const STATUS_MARK: Record<string, string> = {
  red: "●",
  yellow: "▲",
  gray: "–",
  ok: "",
};

export const SPEC_LINE_COLOR = "#c64545";
