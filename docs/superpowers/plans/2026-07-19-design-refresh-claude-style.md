# Claude-Style Design Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the entire frontend to the Claude/Anthropic design language (cream canvas, coral primary, hairline borders, sparse serif titles) via new tokens and a shared UI kit — zero functional change.

**Architecture:** Rewrite `index.css` tokens with legacy aliases so nothing breaks mid-migration; add self-hosted fonts; build `frontend/src/ui/` kit (Card, Button, Select, CheckListCard, PageTitle, Badge, tableStyles); migrate TopNav + 4 pages + charts onto the kit; finally remove aliases.

**Tech Stack:** React 19 + Vite, inline-style objects (project convention — no CSS-in-JS lib), `@fontsource-variable/inter` + `@fontsource/lora`, Plotly.

**Spec:** `docs/superpowers/specs/2026-07-19-design-refresh-claude-style-design.md`

## Global Constraints

- Zero functional change: no behavior, layout-structure, API, or backend edits. Backend tests (75) must pass untouched.
- No new external libraries except the two `@fontsource` packages. No CDN references (corporate networks block them).
- Cards have **no resting shadow** — hairline border + white-on-cream contrast only; `--shadow-hover` allowed on interactive hover.
- Coral `#cc785c` only on primary actions/active states/links — never as a data color.
- `BIN_COLORS` and the wafer-map Okabe–Ito palette are unchanged.
- Serif (Lora) appears exactly once per page: the page title.
- Numeric cells/axes keep or gain `fontVariantNumeric: "tabular-nums"`.
- Verification per task: `cd frontend && npm run build && npm run lint` both clean. No frontend unit-test framework exists; visual verification happens in Task 10.
- Each task ends with a commit (trailer lines added by the committer as usual).

---

### Task 1: Design tokens in `index.css` (with legacy aliases)

**Files:**
- Modify: `frontend/src/index.css` (full rewrite)

**Interfaces:**
- Produces: CSS variables `--canvas, --surface-card, --surface-soft, --ink, --body, --muted, --muted-soft, --primary, --primary-active, --primary-disabled, --success, --warning, --error, --hairline, --hairline-soft, --hairline-color, --shadow-hover, --radius-control, --radius-card, --radius-pill, --font-sans, --font-serif` — every later task styles against these.
- Legacy aliases keep all existing var names valid until Task 11 removes them.

- [ ] **Step 1: Replace the entire content of `frontend/src/index.css` with:**

```css
/* Design tokens — Claude-style data tool.
   Spec: docs/superpowers/specs/2026-07-19-design-refresh-claude-style-design.md
   Fonts are self-hosted via @fontsource (imported in main.tsx); corporate
   networks block external CDNs, so nothing here references a CDN. */

:root {
  /* Surfaces */
  --canvas: #faf9f5;
  --surface-card: #ffffff;
  --surface-soft: #f5f0e8;

  /* Text */
  --ink: #141413;
  --body: #3d3d3a;
  --muted: #6c6a64;
  --muted-soft: #8e8b82;

  /* Primary (coral) */
  --primary: #cc785c;
  --primary-active: #a9583e;
  --primary-disabled: #e6dfd8;

  /* Semantic (yield status) */
  --success: #5db872;
  --warning: #d4a017;
  --error: #c64545;

  /* Structure */
  --hairline-color: #e6dfd8;
  --hairline: 1px solid #e6dfd8;
  --hairline-soft: 1px solid #ebe6df;
  --shadow-hover: 0 1px 3px rgba(20, 20, 19, 0.08);

  /* Radius hierarchy */
  --radius-control: 8px;
  --radius-card: 12px;
  --radius-pill: 9999px;

  /* Typography */
  --font-sans: "Inter Variable", "Inter", -apple-system, BlinkMacSystemFont,
    "Segoe UI", Helvetica, Arial, sans-serif;
  --font-serif: "Lora", Georgia, "Times New Roman", serif;

  /* ── Legacy aliases — every pre-refresh var name, re-pointed at the new
     palette. Removed in the final migration task once no file uses them. ── */
  --black: var(--ink);
  --white: var(--surface-card);
  --warm-white: var(--canvas);
  --warm-dark: var(--ink);
  --gray-700: var(--body);
  --gray-500: var(--muted);
  --gray-400: var(--muted-soft);
  --gray-300: #c8c3ba;
  --gray-200: #d9d2c7;
  --gray-100: #efe9de;
  --notion-blue: var(--primary);
  --active-blue: var(--primary-active);
  --focus-blue: var(--primary);
  --badge-bg: var(--surface-soft);
  --badge-text: var(--body);
  --teal: #2a9d99;
  --green: var(--success);
  --orange: #dd5b00;
  --pink: #ff64c8;
  --purple: #391c57;
  --red: var(--error);
  --yellow: var(--warning);
  --border-whisper: var(--hairline);
  --border-soft: var(--hairline-soft);
  --shadow-card: none;
  --shadow-button: none;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html,
body {
  font-family: var(--font-sans);
  background: var(--canvas);
  color: var(--body);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  letter-spacing: -0.01em;
}

#root {
  width: 100%;
  max-width: 100%;
  min-height: 100vh;
}

button {
  font-family: inherit;
}

input,
select {
  font-family: inherit;
}

input:focus,
select:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(204, 120, 92, 0.18);
}

input[type="checkbox"] {
  accent-color: var(--primary);
}

::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}
::-webkit-scrollbar-thumb {
  background: var(--gray-200);
  border-radius: 999px;
}
::-webkit-scrollbar-thumb:hover {
  background: #b8b2a7;
}
```

- [ ] **Step 2: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: both succeed with no errors. The whole app is now cream-canvas with coral accents via the aliases.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat(design): Claude-style design tokens with legacy aliases"
```

---

### Task 2: Self-hosted fonts (Inter + Lora)

**Files:**
- Modify: `frontend/package.json` (via npm install)
- Modify: `frontend/src/main.tsx`

**Interfaces:**
- Produces: font families `"Inter Variable"` (weights 100–900 variable) and `"Lora"` (weight 500) available offline; `--font-sans` / `--font-serif` from Task 1 resolve to them.

- [ ] **Step 1: Install fontsource packages**

Run: `cd frontend && npm install @fontsource-variable/inter @fontsource/lora`
Expected: both added to `dependencies` in `package.json`.

- [ ] **Step 2: Import the fonts in `frontend/src/main.tsx`**

Add at the very top of the existing imports (before `./index.css`):

```tsx
import "@fontsource-variable/inter";
import "@fontsource/lora/500.css";
```

- [ ] **Step 3: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: success; `dist/assets` now contains woff2 files (check with `ls frontend/dist/assets | grep -i -E "inter|lora"`).

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/main.tsx
git commit -m "feat(design): self-host Inter Variable + Lora via fontsource"
```

---

### Task 3: Shared UI kit — `frontend/src/ui/`

**Files:**
- Create: `frontend/src/ui/Card.tsx`
- Create: `frontend/src/ui/Button.tsx`
- Create: `frontend/src/ui/Select.tsx`
- Create: `frontend/src/ui/PageTitle.tsx`
- Create: `frontend/src/ui/Badge.tsx`
- Create: `frontend/src/ui/CheckListCard.tsx`
- Create: `frontend/src/ui/tableStyles.ts`

**Interfaces (produces — later tasks import exactly these):**
- `Card({ title?, headerRight?, style?, bodyStyle?, children })` — white hairline card, radius 12, padding 20, no shadow.
- `Button({ variant? = "secondary", ...native button props })` — variants `"primary" | "secondary" | "ghost"`.
- `Select(native select props)` — 36px hairline select.
- `PageTitle({ breadcrumb?, title, subtext? })` — Lora serif 28/500 page heading.
- `Badge({ variant? = "neutral", children })` — variants `"neutral" | "success" | "warning" | "error"`.
- `CheckListCard({ title, options, selected, onToggle, headerRight?, footer?, grow?, minWidth?, height?, emptyText? })` with `CheckListOption = { value: string; label: string; swatch?: string; disabled?: boolean }`.
- `tableStyles` — style-object record: `scroll, table, th, thLeft, td, tdLeft, rowWarn`.

- [ ] **Step 1: Create `frontend/src/ui/Card.tsx`**

```tsx
import type { CSSProperties, ReactNode } from "react";

interface CardProps {
  title?: ReactNode;
  headerRight?: ReactNode;
  style?: CSSProperties;
  bodyStyle?: CSSProperties;
  children: ReactNode;
}

/** White card on the cream canvas: hairline border, 12px radius, padding 20,
 *  no resting shadow (elevation = surface contrast, per design spec). */
export default function Card({ title, headerRight, style, bodyStyle, children }: CardProps) {
  return (
    <section style={{ ...styles.card, ...style }}>
      {(title || headerRight) && (
        <div style={styles.header}>
          {title && <span style={styles.title}>{title}</span>}
          {headerRight && <div style={styles.headerRight}>{headerRight}</div>}
        </div>
      )}
      <div style={{ ...styles.body, ...bodyStyle }}>{children}</div>
    </section>
  );
}

const styles: Record<string, CSSProperties> = {
  card: {
    background: "var(--surface-card)",
    border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    padding: 20,
    display: "flex",
    flexDirection: "column",
    minWidth: 0,
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
    marginBottom: 12,
  },
  title: { fontSize: 14, fontWeight: 600, color: "var(--ink)" },
  headerRight: { display: "flex", alignItems: "center", gap: 10 },
  body: { flex: 1, minHeight: 0, display: "flex", flexDirection: "column", minWidth: 0 },
};
```

- [ ] **Step 2: Create `frontend/src/ui/Button.tsx`**

```tsx
import type { ButtonHTMLAttributes, CSSProperties } from "react";

type Variant = "primary" | "secondary" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

/** Kit button. primary = coral (one main action per view); secondary = white
 *  with hairline; ghost = borderless coral text link-button. */
export default function Button({ variant = "secondary", disabled, style, ...rest }: ButtonProps) {
  const merged: CSSProperties = {
    ...base,
    ...variants[variant],
    ...(disabled ? disabledStyles[variant] : {}),
    ...style,
  };
  return <button disabled={disabled} style={merged} {...rest} />;
}

const base: CSSProperties = {
  height: 36,
  padding: "0 16px",
  borderRadius: "var(--radius-control)",
  fontSize: 13,
  fontWeight: 500,
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 6,
  whiteSpace: "nowrap",
};

const variants: Record<Variant, CSSProperties> = {
  primary: { background: "var(--primary)", color: "#ffffff", border: "none" },
  secondary: { background: "var(--surface-card)", color: "var(--ink)", border: "var(--hairline)" },
  ghost: { background: "none", color: "var(--primary)", border: "none", padding: 0, height: "auto", fontSize: 12 },
};

const disabledStyles: Record<Variant, CSSProperties> = {
  primary: { background: "var(--primary-disabled)", color: "var(--muted)", cursor: "not-allowed" },
  secondary: { opacity: 0.5, cursor: "not-allowed" },
  ghost: { opacity: 0.5, cursor: "not-allowed" },
};
```

- [ ] **Step 3: Create `frontend/src/ui/Select.tsx`**

```tsx
import type { CSSProperties, SelectHTMLAttributes } from "react";

/** Kit select: 36px, hairline border, control radius. Focus ring comes from
 *  the global select:focus rule in index.css (coral). */
export default function Select({ style, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select style={{ ...base, ...style }} {...rest} />;
}

const base: CSSProperties = {
  height: 36,
  padding: "0 10px",
  borderRadius: "var(--radius-control)",
  border: "var(--hairline)",
  background: "var(--surface-card)",
  color: "var(--ink)",
  fontSize: 13,
  fontFamily: "var(--font-sans)",
};
```

- [ ] **Step 4: Create `frontend/src/ui/PageTitle.tsx`**

```tsx
import type { CSSProperties, ReactNode } from "react";

interface PageTitleProps {
  breadcrumb?: string;
  title: ReactNode;
  subtext?: ReactNode;
}

/** The one serif element per page (design spec): Lora 28/500 ink title with
 *  an optional muted breadcrumb above and subtext line below. */
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
    fontFamily: "var(--font-serif)",
    fontSize: 28,
    fontWeight: 500,
    color: "var(--ink)",
    letterSpacing: "-0.01em",
    lineHeight: 1.2,
  },
  subtext: { marginTop: 10, fontSize: 13, color: "var(--muted)" },
};
```

- [ ] **Step 5: Create `frontend/src/ui/Badge.tsx`**

```tsx
import type { CSSProperties, ReactNode } from "react";

type Variant = "neutral" | "success" | "warning" | "error";

interface BadgeProps {
  variant?: Variant;
  children: ReactNode;
}

/** Pill badge; tinted background + readable darker text per semantic state. */
export default function Badge({ variant = "neutral", children }: BadgeProps) {
  return <span style={{ ...base, ...variants[variant] }}>{children}</span>;
}

const base: CSSProperties = {
  display: "inline-block",
  padding: "2px 10px",
  borderRadius: "var(--radius-pill)",
  fontSize: 11,
  fontWeight: 500,
  letterSpacing: "0.02em",
  whiteSpace: "nowrap",
};

const variants: Record<Variant, CSSProperties> = {
  neutral: { background: "var(--surface-soft)", color: "var(--body)" },
  success: { background: "rgba(93, 184, 114, 0.14)", color: "#3e7d4f" },
  warning: { background: "rgba(212, 160, 23, 0.14)", color: "#8a6a0f" },
  error: { background: "rgba(198, 69, 69, 0.12)", color: "var(--error)" },
};
```

- [ ] **Step 6: Create `frontend/src/ui/CheckListCard.tsx`**

This generalizes the wafer-map `FilterCard` (single-select) and the Lots / Bin
cards (multi-select with swatches, disabled rows, header actions, footer).

```tsx
import type { CSSProperties, ReactNode } from "react";

export interface CheckListOption {
  value: string;
  label: string;
  swatch?: string;    // optional color dot (bin filter)
  disabled?: boolean; // e.g. lots beyond MAX_LOTS
}

interface CheckListCardProps {
  title: string;
  options: CheckListOption[];
  /** Checked values. Single-select callers pass `[value]` and replace it in onToggle. */
  selected: string[];
  onToggle: (value: string) => void;
  headerRight?: ReactNode;
  footer?: ReactNode;
  grow?: number;
  minWidth?: number;
  height?: number;
  /** Shown inside the scroll box when there are no options (loading / empty). */
  emptyText?: string;
}

/** Titled fixed-height card with a bordered scroll box of checkbox rows —
 *  the unified filter-card design from the wafer-map tab, now shared. */
export default function CheckListCard({
  title, options, selected, onToggle, headerRight, footer,
  grow = 1, minWidth = 0, height = 340, emptyText,
}: CheckListCardProps) {
  return (
    <div style={{ ...styles.card, flex: `${grow} 1 0`, minWidth, height }}>
      <div style={styles.header}>
        <span style={styles.title}>{title}</span>
        {headerRight && <div style={styles.headerRight}>{headerRight}</div>}
      </div>
      <div style={styles.list}>
        {options.length === 0 && emptyText && <p style={styles.empty}>{emptyText}</p>}
        {options.map((o) => (
          <label
            key={o.value}
            style={{ ...styles.item, ...(o.disabled ? styles.itemDisabled : {}) }}
          >
            <input
              type="checkbox"
              checked={selected.includes(o.value)}
              disabled={o.disabled}
              onChange={() => onToggle(o.value)}
            />
            {o.swatch && <span style={{ ...styles.swatch, background: o.swatch }} />}
            <span style={styles.itemText} title={o.label}>{o.label}</span>
          </label>
        ))}
      </div>
      {footer}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  card: {
    background: "var(--surface-card)",
    border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    padding: 20,
    marginBottom: 0,
    display: "flex",
    flexDirection: "column",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  headerRight: { display: "flex", alignItems: "center", gap: 10 },
  title: { fontSize: 14, fontWeight: 600, color: "var(--ink)" },
  list: {
    flex: 1,
    minHeight: 0,
    display: "flex",
    flexDirection: "column",
    gap: 4,
    overflowY: "auto",
    border: "var(--hairline)",
    borderRadius: "var(--radius-control)",
    padding: 6,
  },
  item: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    fontSize: 12,
    fontWeight: 500,
    color: "var(--body)",
    padding: "4px 8px",
    borderRadius: 6,
    cursor: "pointer",
  },
  itemDisabled: { color: "var(--muted-soft)", cursor: "not-allowed" },
  itemText: { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  swatch: { width: 10, height: 10, borderRadius: "50%", flexShrink: 0 },
  empty: { color: "var(--muted-soft)", fontSize: 13, padding: 4 },
};
```

- [ ] **Step 7: Create `frontend/src/ui/tableStyles.ts`**

```ts
import type { CSSProperties } from "react";

/** Shared data-table styles (Stripe tnum discipline): uppercase-tracked muted
 *  headers on the cream band, hairline-soft row rules, right-aligned
 *  tabular-nums numeric cells. Spread into <table>/<th>/<td> style props. */
export const tableStyles: Record<string, CSSProperties> = {
  scroll: { overflowX: "auto", maxWidth: "100%" },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 13,
    color: "var(--body)",
  },
  th: {
    textAlign: "right",
    padding: "10px 14px",
    background: "var(--canvas)",
    color: "var(--muted)",
    fontWeight: 600,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    borderBottom: "var(--hairline)",
    whiteSpace: "nowrap",
  },
  thLeft: {
    textAlign: "left",
    padding: "10px 14px",
    background: "var(--canvas)",
    color: "var(--muted)",
    fontWeight: 600,
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    borderBottom: "var(--hairline)",
  },
  td: {
    textAlign: "right",
    padding: "10px 14px",
    borderBottom: "var(--hairline-soft)",
    fontVariantNumeric: "tabular-nums",
  },
  tdLeft: { textAlign: "left", padding: "10px 14px", borderBottom: "var(--hairline-soft)" },
  rowWarn: { background: "rgba(198, 69, 69, 0.05)" },
};
```

- [ ] **Step 8: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: clean. (New files are not imported yet; lint must still pass on them.)

- [ ] **Step 9: Commit**

```bash
git add frontend/src/ui/
git commit -m "feat(design): shared UI kit — Card, Button, Select, PageTitle, Badge, CheckListCard, tableStyles"
```

---

### Task 4: TopNav + ErrorBanner

**Files:**
- Modify: `frontend/src/components/TopNav.tsx`
- Modify: `frontend/src/components/ErrorBanner.tsx`

**Interfaces:**
- Consumes: tokens from Task 1 only (no kit imports needed here).

- [ ] **Step 1: In `TopNav.tsx`, replace the `styles` const with:**

```tsx
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
```

(JSX unchanged. Active tab is now the Claude `category-tab` pattern: soft cream fill + ink text.)

- [ ] **Step 2: In `ErrorBanner.tsx`, replace the `styles` const with:**

```tsx
const styles: Record<string, React.CSSProperties> = {
  banner: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "10px 16px",
    background: "rgba(198, 69, 69, 0.08)",
    border: "1px solid rgba(198, 69, 69, 0.3)",
    borderRadius: "var(--radius-control)",
    margin: "0 16px 16px",
    fontSize: 13,
    color: "var(--error)",
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
```

- [ ] **Step 3: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/TopNav.tsx frontend/src/components/ErrorBanner.tsx
git commit -m "feat(design): TopNav category-tab active state, ErrorBanner semantic error tones"
```

---

### Task 5: Chart theme — `theme.ts`, `YieldChart`, `Sparkline`

**Files:**
- Modify: `frontend/src/theme.ts`
- Modify: `frontend/src/components/YieldChart.tsx`
- Modify: `frontend/src/components/dashboard/Sparkline.tsx`

**Interfaces:**
- Produces from `theme.ts`: `INK = "#141413"`, `MUTED = "#6c6a64"`, `MUTED_SOFT = "#8e8b82"`, `GRID = "#efe9de"`, `AXIS_LINE = "#e6dfd8"`, `plotlyBaseLayout(): Partial<Plotly.Layout>`; `YIELD_LINE_COLOR` becomes `#141413`; `BIN_COLORS` unchanged; `FONT_FAMILY` updated to lead with `"Inter Variable"`.
- Task 6 (SummaryTable) relies on `Sparkline` accepting the same props; its default `color` becomes ink.

- [ ] **Step 1: Replace the entire content of `frontend/src/theme.ts` with:**

```ts
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
```

- [ ] **Step 2: In `YieldChart.tsx`, update imports and layout**

Change the theme import to:

```tsx
import { BIN_COLORS, YIELD_LINE_COLOR, INK, MUTED, MUTED_SOFT, GRID, AXIS_LINE, plotlyBaseLayout } from "../theme";
```

Replace the `layout` const with:

```tsx
  const layout: Partial<Plotly.Layout> = {
    ...plotlyBaseLayout(),
    barmode: "stack",
    xaxis: { tickangle: -30, tickfont: { size: 10, color: MUTED }, gridcolor: GRID, linecolor: AXIS_LINE },
    yaxis: { title: { text: "Fail Bin (%)", font: { size: 10, color: MUTED_SOFT } }, side: "left", range: [0, 102], tickfont: { size: 10, color: MUTED }, gridcolor: GRID, zerolinecolor: AXIS_LINE },
    yaxis2: { title: { text: "Yield (%)", font: { size: 10, color: MUTED_SOFT } }, side: "right", overlaying: "y", range: yieldRange, tickfont: { size: 10, color: MUTED }, showgrid: false },
    legend: { orientation: "h", yanchor: "bottom", y: -0.4, xanchor: "center", x: 0.5, font: { size: 11, color: MUTED }, bgcolor: "rgba(0,0,0,0)" },
    margin: { l: 56, r: 56, t: 16, b: 110 },
    height: 420,
    shapes: targetShapes,
  };
```

In `targetShapes`, change the target line color to the semantic error tone:
`line: { color: "rgba(198,69,69,0.6)", width: 1.5, dash: "dash" }`.

Replace the `styles` const at the bottom with:

```tsx
const styles: Record<string, React.CSSProperties> = {
  card: {
    background: "var(--surface-card)",
    border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    padding: "22px 24px 12px",
  },
  cardHeader: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 16,
    marginBottom: 8,
    flexWrap: "wrap",
  },
  processBadge: {
    display: "inline-block",
    padding: "2px 10px",
    borderRadius: "var(--radius-pill)",
    background: "var(--surface-soft)",
    color: "var(--body)",
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: "0.04em",
    marginBottom: 6,
  },
  title: {
    fontSize: 17,
    fontWeight: 600,
    color: "var(--ink)",
    letterSpacing: "-0.015em",
  },
  stats: { display: "flex", gap: 28, flexWrap: "wrap", justifyContent: "flex-end" },
  statItem: { textAlign: "right" },
  statLabel: {
    fontSize: 10,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "var(--muted-soft)",
    marginBottom: 2,
  },
  statValue: {
    fontSize: 18,
    fontWeight: 600,
    color: "var(--ink)",
    letterSpacing: "-0.01em",
    fontVariantNumeric: "tabular-nums",
  },
};
```

- [ ] **Step 3: In `Sparkline.tsx`, change the default color and target-line stroke**

```tsx
export default function Sparkline({
  values, width = 90, height = 22, color = "#141413", target,
}: SparklineProps) {
```

and the target line: `stroke="rgba(20,20,19,0.3)"`.

- [ ] **Step 4: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/theme.ts frontend/src/components/YieldChart.tsx frontend/src/components/dashboard/Sparkline.tsx
git commit -m "feat(design): ink/hairline chart theme, shared plotly base layout"
```

---

### Task 6: Dashboard page + SummaryTable

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/components/dashboard/SummaryTable.tsx`

**Interfaces:**
- Consumes: `PageTitle`, `Select`, `Button`, `Card` from `../ui/*`; `tableStyles` from `../../ui/tableStyles`; `Badge` from `../../ui/Badge`.

- [ ] **Step 1: Restyle `DashboardPage.tsx`**

Add imports:

```tsx
import PageTitle from "../ui/PageTitle";
import Select from "../ui/Select";
import Button from "../ui/Button";
```

Replace the `<header>` block with:

```tsx
      <PageTitle breadcrumb="Monitoring · Yield Overview" title="Dashboard" />
```

In the toolbar, replace the two `<select>` elements with the kit `Select`
(same props/children, drop `style={styles.select}`), and the refresh button with:

```tsx
        <Button onClick={() => load(true)} disabled={loading}>
          {loading ? "Refreshing…" : "🔄 Refresh"}
        </Button>
```

Replace the `styles` const with:

```tsx
const styles: Record<string, React.CSSProperties> = {
  container: {
    flex: 1,
    padding: "40px 56px 56px",
    overflowY: "auto",
    background: "var(--canvas)",
    minWidth: 0,
  },
  toolbar: { display: "flex", alignItems: "center", gap: 18, marginBottom: 20, flexWrap: "wrap" },
  field: { display: "inline-flex", alignItems: "center", gap: 8 },
  fieldLabel: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "var(--muted-soft)",
  },
  updated: { fontSize: 12, color: "var(--muted-soft)", marginLeft: "auto", fontVariantNumeric: "tabular-nums" },
  error: {
    background: "rgba(198, 69, 69, 0.08)",
    color: "var(--error)",
    padding: "10px 14px",
    borderRadius: "var(--radius-control)",
    marginBottom: 16,
    fontSize: 13,
  },
  card: {
    background: "var(--surface-card)",
    border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    overflow: "hidden",
  },
  empty: { color: "var(--muted-soft)", fontSize: 14 },
};
```

(The table wrapper keeps a plain styled div — `Card` adds padding the full-bleed table doesn't want.)

- [ ] **Step 2: Restyle `SummaryTable.tsx`**

Add imports:

```tsx
import { tableStyles } from "../../ui/tableStyles";
import Badge from "../../ui/Badge";
```

Changes inside the component:
- `deltaColor`: `r.delta == null ? "var(--muted-soft)" : r.delta < 0 ? "var(--error)" : "var(--success)"`.
- Below-target latest cell: `{ color: "var(--error)" }` (was `var(--red)`).
- Sparkline call: `color={warn ? "#c64545" : "#141413"}`.
- Warnings cell: replace `<span key={i} style={styles.badge}>⚠ {w.message}</span>` with `<Badge key={i} variant="error">⚠ {w.message}</Badge>` (wrap adjacent badges with a 4px gap: put them in `<span style={{ display: "inline-flex", gap: 4, flexWrap: "wrap" }}>` if more than one — simplest is to keep them inline and add `marginRight: 4` via a wrapper span; use `<span key={i} style={{ marginRight: 4 }}><Badge variant="error">⚠ {w.message}</Badge></span>`).

Replace the `styles` const with (base cells now come from `tableStyles`):

```tsx
const styles: Record<string, React.CSSProperties> = {
  table: { ...tableStyles.table },
  th: { ...tableStyles.th, cursor: "pointer" },
  thLeft: { ...tableStyles.thLeft, cursor: "pointer" },
  tr: { cursor: "pointer" },
  trWarn: { ...tableStyles.rowWarn },
  trSub: { opacity: 0.85 },
  trDisabled: { cursor: "default", background: "var(--canvas)", color: "var(--muted)" },
  td: { ...tableStyles.td },
  tdLeft: { ...tableStyles.tdLeft },
  tdLeftSub: { ...tableStyles.tdLeft, paddingLeft: 28 },
  proc: { color: "var(--muted-soft)" },
  subGlyph: { color: "var(--muted-soft)", marginRight: 6, userSelect: "none" },
  subName: { color: "var(--muted-soft)", fontSize: 11, marginTop: 2 },
  trProductEnd: { borderBottom: "none" },
  spacer: { height: 6, background: "var(--canvas)" },
};
```

Note: the old `styles.tr` carried `borderBottom: var(--border-soft)`; the row
rule now lives on the `td`s via `tableStyles`, so `trProductEnd`'s
`borderBottom: "none"` must move too — apply it on the row's cells instead:
where the JSX spreads `...(isProductEnd ? styles.trProductEnd : {})` on the
`<tr>`, ALSO spread `...(isProductEnd ? { borderBottom: "none" } : {})` onto
each `td`/`tdLeft` style in that row. Concretely, compute once per row:

```tsx
const cellEnd: React.CSSProperties = isProductEnd ? { borderBottom: "none" } : {};
```

and add `...cellEnd` to every `style={{ ...styles.td… }}` in that row.

- [ ] **Step 3: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/DashboardPage.tsx frontend/src/components/dashboard/SummaryTable.tsx
git commit -m "feat(design): dashboard on kit — serif title, tableStyles, semantic badges"
```

---

### Task 7: Report page + ReportView

**Files:**
- Modify: `frontend/src/pages/ReportPage.tsx`
- Modify: `frontend/src/components/ReportView.tsx`

**Interfaces:**
- Consumes: `PageTitle`, `Select`, `Button` from `../ui/*`.

- [ ] **Step 1: Restyle `ReportPage.tsx`**

Add imports:

```tsx
import PageTitle from "../ui/PageTitle";
import Select from "../ui/Select";
import Button from "../ui/Button";
```

JSX changes:
- Replace the `<header>` block with `<PageTitle breadcrumb="Reports · Yield Trend" title="Report" />`.
- Product `<select>` → kit `Select` (drop `style={styles.select}`).
- Generate button → `<Button variant="primary" onClick={handleGenerate} disabled={disabled}>{loading ? "Loading…" : "Generate Report"}</Button>`.
- Export button → `<Button onClick={() => exportPdf(buildRequest())} disabled={data === null || disabled}>Export PDF</Button>`.
- Mock dot color: `background: isMock === false ? "var(--primary)" : "var(--success)"`.

Replace the `styles` const with:

```tsx
const styles: Record<string, React.CSSProperties> = {
  page: { flex: 1, display: "flex", flexDirection: "column", minWidth: 0 },
  container: {
    flex: 1,
    padding: "40px 56px 56px",
    overflowY: "auto",
    background: "var(--canvas)",
    minWidth: 0,
  },
  toolbar: { display: "flex", alignItems: "center", gap: 18, marginBottom: 24, flexWrap: "wrap" },
  field: { display: "inline-flex", alignItems: "center", gap: 8 },
  fieldLabel: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "var(--muted-soft)",
  },
  chipGroup: { display: "flex", gap: 6, flexWrap: "wrap" },
  chip: {
    padding: "6px 14px",
    borderRadius: "var(--radius-pill)",
    border: "var(--hairline)",
    background: "var(--surface-card)",
    color: "var(--muted)",
    fontSize: 13,
    fontWeight: 500,
    cursor: "pointer",
  },
  chipActive: {
    background: "var(--surface-soft)",
    color: "var(--ink)",
    border: "1px solid rgba(204, 120, 92, 0.45)",
  },
  mock: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    fontSize: 12,
    color: "var(--muted-soft)",
    marginLeft: "auto",
  },
  mockDot: { width: 6, height: 6, borderRadius: "50%", display: "inline-block" },
};
```

(`select`, `primaryBtn`, `secondaryBtn`, `btnDisabled`, `header`, `breadcrumb`, `title` are deleted — kit components own them now.)

- [ ] **Step 2: Restyle `ReportView.tsx`**

The in-view report header keeps its own layout (it is a report masthead, not
the page title — `ReportPage` already renders the page's single serif
`PageTitle`, so this masthead title stays sans). Replace the `styles` const
with:

```tsx
const styles: Record<string, React.CSSProperties> = {
  container: {
    flex: 1,
    padding: "40px 56px 56px",
    overflowY: "auto",
    background: "var(--canvas)",
    minWidth: 0,
  },
  header: { marginBottom: 32 },
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
    marginBottom: 12,
  },
  metaRow: {
    display: "flex",
    alignItems: "center",
    gap: 14,
    flexWrap: "wrap",
    fontSize: 13,
    color: "var(--muted)",
    fontVariantNumeric: "tabular-nums",
  },
  metaItem: { display: "inline-flex", alignItems: "center", gap: 6 },
  metaLabel: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "var(--muted-soft)",
  },
  metaDivider: { width: 1, height: 12, background: "var(--hairline-color)" },
  grid: { display: "flex", flexDirection: "column", gap: 24 },
  empty: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "var(--canvas)",
    padding: 40,
  },
  emptyCard: {
    maxWidth: 460,
    background: "var(--surface-card)",
    border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    padding: "36px 32px",
    textAlign: "center",
  },
  emptyBadge: {
    display: "inline-block",
    padding: "3px 10px",
    borderRadius: "var(--radius-pill)",
    background: "var(--surface-soft)",
    color: "var(--body)",
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: "0.04em",
    marginBottom: 14,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: 600,
    color: "var(--ink)",
    letterSpacing: "-0.015em",
    marginBottom: 10,
  },
  emptyText: { fontSize: 14, lineHeight: 1.55, color: "var(--muted)" },
};
```

- [ ] **Step 3: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ReportPage.tsx frontend/src/components/ReportView.tsx
git commit -m "feat(design): report page on kit — coral primary action, soft-cream chips"
```

---

### Task 8: Explore page + LotTable

**Files:**
- Modify: `frontend/src/pages/ExplorePage.tsx`
- Modify: `frontend/src/components/explore/LotTable.tsx`

**Interfaces:**
- Consumes: `PageTitle`, `Button` from `../ui/*`; `tableStyles`, `Badge` from `../../ui/*`.

- [ ] **Step 1: Restyle `ExplorePage.tsx`**

Add imports:

```tsx
import Button from "../ui/Button";
```

JSX: the back button becomes `<Button onClick={() => navigate("/dashboard")}>← Back</Button>`.
The header keeps its custom two-element layout (back button + title block), so
`PageTitle` is not used here; instead the local title adopts the serif face
(this page's single serif element).

Replace the `styles` const with:

```tsx
const styles: Record<string, React.CSSProperties> = {
  container: {
    flex: 1,
    padding: "40px 56px 56px",
    overflowY: "auto",
    background: "var(--canvas)",
    minWidth: 0,
  },
  header: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 16,
    marginBottom: 24,
    flexWrap: "wrap",
  },
  headerLeft: { display: "flex", alignItems: "center", gap: 16 },
  breadcrumb: {
    fontSize: 12,
    color: "var(--muted-soft)",
    fontWeight: 500,
    letterSpacing: "0.02em",
    marginBottom: 6,
  },
  title: {
    fontFamily: "var(--font-serif)",
    fontSize: 26,
    fontWeight: 500,
    color: "var(--ink)",
    letterSpacing: "-0.01em",
    lineHeight: 1.2,
  },
  proc: { color: "var(--muted-soft)", fontWeight: 500 },
  stack: { display: "flex", flexDirection: "column", gap: 24 },
  card: {
    background: "var(--surface-card)",
    border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    overflow: "hidden",
  },
  error: {
    background: "rgba(198, 69, 69, 0.08)",
    color: "var(--error)",
    padding: "10px 14px",
    borderRadius: "var(--radius-control)",
    marginBottom: 16,
    fontSize: 13,
  },
  empty: { color: "var(--muted-soft)", fontSize: 14 },
};
```

(`back` style is deleted — the kit Button owns it.)

- [ ] **Step 2: Restyle `LotTable.tsx`**

Add imports:

```tsx
import { tableStyles } from "../../ui/tableStyles";
import Badge from "../../ui/Badge";
```

Replace warning spans with `<span key={i} style={{ marginRight: 4 }}><Badge variant="error">⚠ {w.message}</Badge></span>`.

Replace the `styles` const with (denser padding than the shared base, so
override padding/fontSize inline):

```tsx
const styles: Record<string, React.CSSProperties> = {
  scroll: { ...tableStyles.scroll },
  table: { ...tableStyles.table, tableLayout: "fixed", fontSize: 12 },
  th: { ...tableStyles.th, padding: "8px 10px", letterSpacing: "0.03em" },
  thLeft: { ...tableStyles.thLeft, padding: "8px 10px", letterSpacing: "0.03em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  td: { ...tableStyles.td, padding: "6px 10px" },
  tdLeft: { ...tableStyles.tdLeft, padding: "6px 10px" },
  warn: { ...tableStyles.rowWarn },
  binHead: { display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  cellTrunc: { display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  lotLink: { display: "block", color: "var(--primary)", textDecoration: "none", fontWeight: 500 },
};
```

(`badge` is deleted — kit Badge owns it. The lot link is now a coral text-link,
the Claude signature inline-link treatment.)

- [ ] **Step 3: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ExplorePage.tsx frontend/src/components/explore/LotTable.tsx
git commit -m "feat(design): explore page on kit — serif title, coral lot links, tableStyles"
```

---

### Task 9: Wafer Map page onto CheckListCard

**Files:**
- Modify: `frontend/src/pages/WaferMapPage.tsx`
- Delete: `frontend/src/components/wafermap/FilterCard.tsx`
- Delete: `frontend/src/components/wafermap/BinLegend.tsx`
- Modify: `frontend/src/components/wafermap/WaferMapGrid.tsx` (token color touch-up only)

**Interfaces:**
- Consumes: `CheckListCard` (+ `CheckListOption`), `Button`, `PageTitle` from `../ui/*`.
- Behavior contract (unchanged): single-select cards Product/Process/Sub/Period; multi-select Lots (MAX_LOTS 12, overflow disabled) and Bin filter (swatches); Load lots in Period footer; Show maps under Lots; Copy image in the map card header; grow weights 2/1/1/1.5/2/1.5 and minWidths 170/90/100/130/200/160; card height 340.

- [ ] **Step 1: Rewrite the filter row in `WaferMapPage.tsx`**

Replace imports of `FilterCard` and `BinLegend` with:

```tsx
import CheckListCard from "../ui/CheckListCard";
import Button from "../ui/Button";
import PageTitle from "../ui/PageTitle";
```

Replace the `<header>` block with `<PageTitle breadcrumb="Analysis · Wafer Map" title="Wafer Map" />`.

Replace the entire `<div style={styles.row}>…</div>` block with:

```tsx
      <div style={styles.row}>
        <CheckListCard
          title="Product" grow={2} minWidth={170}
          selected={[productId]}
          onToggle={(v) => { setProductId(v); setSub(""); }}
          options={products.map((p) => ({ value: p.product_id, label: p.product_id + (p.display_name && p.display_name !== p.product_id ? ` — ${p.display_name}` : "") }))}
        />
        <CheckListCard
          title="Process" grow={1} minWidth={90}
          selected={[process]}
          onToggle={(v) => { setProcess(v); setSub(""); }}
          options={[{ value: "CP", label: "CP" }, { value: "FT", label: "FT" }, { value: "SLT", label: "SLT" }]}
        />
        <CheckListCard
          title="Sub" grow={1} minWidth={100}
          selected={[sub]}
          onToggle={setSub}
          options={[{ value: "", label: "All" }, ...(subsByProcess[process] || []).map((s) => ({ value: s, label: s }))]}
        />
        <CheckListCard
          title="Period" grow={1.5} minWidth={130}
          selected={[String(months)]}
          onToggle={(v) => setMonths(Number(v))}
          options={[{ value: "1", label: "Last 1 month" }, { value: "3", label: "Last 3 months" }, { value: "6", label: "Last 6 months" }]}
          footer={
            <Button onClick={() => loadLots()} disabled={lotsLoading} style={{ width: "100%", marginTop: 12 }}>
              {lotsLoading ? "Loading…" : "🔄 Load lots"}
            </Button>
          }
        />
        <CheckListCard
          title="Lots" grow={2} minWidth={200}
          selected={selectedLots}
          onToggle={toggleLot}
          options={displayLots.map((l) => ({
            value: l.lot_id,
            label: l.lot_id,
            disabled: !selectedLots.includes(l.lot_id) && selectedLots.length >= MAX_LOTS,
          }))}
          emptyText={lotsLoading ? "Loading lots…" : lotsData ? "No lots found." : undefined}
          headerRight={
            <>
              <Button variant="ghost" onClick={() => setSelectedLots(displayLots.slice(0, MAX_LOTS).map((l) => l.lot_id))}>Select all</Button>
              <Button variant="ghost" onClick={() => setSelectedLots([])}>Clear</Button>
              <span style={styles.lotsCounter}>{selectedLots.length}/{MAX_LOTS}</span>
            </>
          }
          footer={
            <Button
              variant="primary"
              onClick={() => handleShowMaps()}
              disabled={selectedLots.length === 0 || mapLoading}
              style={{ alignSelf: "flex-start", marginTop: 12 }}
            >
              {mapLoading ? "Loading…" : "Show maps"}
            </Button>
          }
        />
        <CheckListCard
          title="Bin filter" grow={1.5} minWidth={160}
          selected={selectedBins.map(String)}
          onToggle={(v) => toggleBin(Number(v))}
          options={(mapData?.legend ?? []).map((item) => ({
            value: String(item.bin_code),
            label: `${item.label} (${item.count})`,
            swatch: colorFor(item.bin_code),
          }))}
          headerRight={mapData ? <span style={styles.lotsCounter}>{mapData.legend.length}</span> : undefined}
        />
      </div>
```

- [ ] **Step 2: Restyle the map card + remaining styles in `WaferMapPage.tsx`**

The Copy image button becomes `<Button onClick={handleCopy}>📋 Copy image</Button>`.

Replace the `styles` const with:

```tsx
const styles: Record<string, React.CSSProperties> = {
  container: {
    flex: 1,
    padding: "40px 56px 56px",
    overflowY: "auto",
    background: "var(--canvas)",
    minWidth: 0,
  },
  mapHeaderRow: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 },
  copyRow: { display: "flex", alignItems: "center", gap: 10 },
  copyMsg: { fontSize: 12, color: "var(--muted-soft)" },
  error: {
    background: "rgba(198, 69, 69, 0.08)",
    color: "var(--error)",
    padding: "10px 14px",
    borderRadius: "var(--radius-control)",
    marginBottom: 16,
    fontSize: 13,
  },
  card: {
    background: "var(--surface-card)",
    border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    padding: 20,
    marginBottom: 20,
  },
  row: { display: "flex", gap: 16, alignItems: "flex-start", marginBottom: 20, flexWrap: "wrap" },
  lotsCounter: { fontSize: 12, color: "var(--muted-soft)", fontVariantNumeric: "tabular-nums" },
  mapMeta: { color: "var(--muted-soft)", fontSize: 13 },
  gridSpacer: { marginTop: 16 },
};
```

(`header`, `breadcrumb`, `title`, `refresh`, `filterCard`, `scrollBox`,
`lotsHeader`, `lotsHeaderActions`, `lotsTitle`, `linkBtn`, `lotItem`,
`lotItemDisabled`, `primaryBtn`, `btnDisabled`, `empty` are all deleted —
`PageTitle`, `Button`, and `CheckListCard` own them now.)

- [ ] **Step 3: Delete the superseded components**

```bash
rm frontend/src/components/wafermap/FilterCard.tsx frontend/src/components/wafermap/BinLegend.tsx
```

Confirm nothing else imports them: `grep -rn "FilterCard\|BinLegend" frontend/src` → no hits.

- [ ] **Step 4: Token touch-up in `WaferMapGrid.tsx`**

In its `styles` const change only the colors:
- `colHead.color` and `rowHead.color`: `"var(--muted)"`.
- `noWafer.color`: `"var(--gray-300, #ccc)"` → `"#c8c3ba"`.

- [ ] **Step 5: Verify build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add -A frontend/src
git commit -m "feat(design): wafer map on kit — CheckListCard everywhere, coral actions"
```

---

### Task 10: Visual verification (before/after screenshots)

Run by the supervisor (Opus), not a subagent — screenshots go to the user.

**Files:** none (verification only).

- [ ] **Step 1: Build + start mock server**

```bash
cd frontend && npm run build
cd ../backend && USE_MOCK_DATA=true uv run python -m uvicorn app.main:app --port 8018
```

(background; wait until `curl -s http://localhost:8018/api/products` responds)

- [ ] **Step 2: Screenshot all four pages** (Playwright: `/dashboard`, `/report` after Generate, `/explore/<id>/CP` via dashboard row click, `/wafermap` after Load lots + Show maps). Save to scratchpad, send to the user.

- [ ] **Step 3: Checklist per page (from spec §7)**

- No blue remnants: `grep -rn "#0075de\|notion-blue\|badge-text\|badge-bg\|focus-blue\|active-blue" frontend/src` → only `theme.ts` BIN_COLORS hex allowed.
- No resting card shadows: `grep -rn "shadow-card\|shadow-button" frontend/src` → no hits.
- Exactly one serif title per page (visual check).
- Coral only on primary actions/links (visual check).
- Tabular-nums on numeric columns (visual check).

- [ ] **Step 4: Backend tests still green**

Run: `cd backend && uv run python -m pytest tests/ -q`
Expected: `75 passed`.

- [ ] **Step 5: Stop the mock server; user reviews screenshots before Task 11.**

---

### Task 11: Remove legacy aliases

Only after the user approves the visuals.

**Files:**
- Modify: `frontend/src/index.css`
- Modify: any file the grep below still flags

- [ ] **Step 1: Find remaining legacy-var users**

```bash
grep -rn "warm-white\|warm-dark\|gray-700\|gray-500\|gray-400\|gray-300\|gray-200\|gray-100\|notion-blue\|active-blue\|focus-blue\|badge-bg\|badge-text\|border-whisper\|border-soft\|shadow-card\|shadow-button\|--white\b\|--black\b\|--red\b\|--green\b\|--yellow\b\|--teal\b\|--orange\b\|--pink\b\|--purple\b" frontend/src --include="*.tsx" --include="*.ts" --include="*.css"
```

Expected leftovers: `frontend/src/components/wafermap/WaferMapGrid.tsx`
(`--gray-500`/`--gray-300` if Task 9 missed any) and `index.css` scrollbar
(`--gray-200`). Replace each: `--gray-500` → `--muted`, `--gray-200` (scrollbar
thumb) → literal `#d9d2c7`, other grays per the alias table in Task 1.

- [ ] **Step 2: Delete the entire "Legacy aliases" block from `:root` in `index.css`.**

- [ ] **Step 3: Verify build + lint + grep**

Run: `cd frontend && npm run build && npm run lint`, then re-run the Step 1 grep.
Expected: build/lint clean; grep returns zero hits.

- [ ] **Step 4: Commit**

```bash
git add -A frontend/src
git commit -m "refactor(design): drop legacy token aliases"
```
