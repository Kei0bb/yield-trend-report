# Vercel-Style Design Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the warm Claude-style frontend look with Vercel's ink-on-near-white language without changing layout, density, fonts, or the PDF.

**Architecture:** Almost all color/shape comes from CSS custom properties in `frontend/src/index.css` and Plotly constants in `frontend/src/theme.ts`, so Task 1 swaps token values. Task 2 reshapes the shared `ui/` kit + TopNav. Task 3 replaces the remaining hard-coded warm colors and card borders in pages/components. Task 4 is the sweep + visual verification.

**Tech Stack:** React 19 + Vite 8 + TypeScript (inline `style` objects), Plotly, Inter (self-hosted via @fontsource).

**Spec:** `docs/superpowers/specs/2026-09-25-design-refresh-vercel-style-design.md`

## Global Constraints

- Font stays Inter (`--font-sans` / `FONT_FAMILY` unchanged). No new npm dependencies.
- Backend / PDF (`backend/app/services/pdf_service.py`) must not be modified.
- `BIN_COLORS` in `theme.ts` and `PALETTE` in `pages/WaferMapPage.tsx` must not be modified.
- Layout, paddings (other than those listed), font sizes (other than those listed) unchanged.
- Plotly never receives `var(--…)` — Plotly-facing colors are literals.
- No weight 700 anywhere in `frontend/src` after Task 3 (600 is the ceiling).
- No test framework exists in the frontend; each task's gate is `npm run build` (tsc + vite) + `npm run lint` + the grep checks written in the task.

## Review Focus

1. **Plotly + CSS var** — a `var(--error)` passed to a Plotly marker renders silently black. Task 3 Step 5 greps chart files for `var(--` inside Plotly configs.
2. **Focus visibility on black primary button** — focus ring must be visible on `#171717` buttons (blue ring from `button:focus-visible`, Task 1).
3. **Warning text contrast** — `#f5a623` text on white is unreadable at 12–13px; any *text* colored `var(--warning)` must be checked (Task 3 Step 6 lists and fixes them to `--warning-deep`).
4. **Wafer map legibility** — pass dies (`#e5e5e5`) must stay distinguishable from the disc (`#f2f2f2`) and from deselected bins (`#ededed`) (Task 4 screenshot check).
5. **Cards lose their edge** — replacing `border` with `--shadow-card` must keep a visible 1px ring on `#fafafa`; no card may end up with neither (Task 3 Step 4 grep).

---

### Task 1: Tokens (`index.css`, `theme.ts`)

**Files:**
- Modify: `frontend/src/index.css` (whole file)
- Modify: `frontend/src/theme.ts` (header comment, `INK`…`AXIS_LINE`, `WAFER_COLORSCALE`, `STATUS_PLOT_COLOR`, `SPEC_LINE_COLOR`)

**Interfaces:**
- Produces CSS variables used by Tasks 2–3: `--hairline-strong`, `--link`, `--error-soft`, `--error-deep`, `--warning-soft`, `--warning-deep`, `--success-soft`, `--success-deep`, `--shadow-card`, `--shadow-popover` (plus all existing names, new values).
- Produces TS constants (unchanged names): `INK`, `MUTED`, `MUTED_SOFT`, `GRID`, `AXIS_LINE`, `WAFER_COLORSCALE`, `STATUS_PLOT_COLOR`, `SPEC_LINE_COLOR`.

- [ ] **Step 1: Replace `frontend/src/index.css` with:**

```css
/* Design tokens — Vercel-style data tool.
   Spec: docs/superpowers/specs/2026-09-25-design-refresh-vercel-style-design.md
   Fonts are self-hosted via @fontsource (imported in main.tsx); corporate
   networks block external CDNs, so nothing here references a CDN. */

:root {
  /* Surfaces */
  --canvas: #fafafa;
  --surface-card: #ffffff;
  --surface-soft: #f5f5f5;

  /* Text */
  --ink: #171717;
  --body: #4d4d4d;
  --muted: #666666;
  --muted-soft: #888888;

  /* Primary (ink) */
  --primary: #171717;
  --primary-active: #383838;
  --primary-disabled: #ebebeb;
  --link: #0070f3;

  /* Semantic (yield status) — base / soft background / deep text */
  --success: #45a557;
  --success-soft: #e8f5eb;
  --success-deep: #2e7d3e;
  --warning: #f5a623;
  --warning-soft: #fff5e0;
  --warning-deep: #ab570a;
  --error: #ee0000;
  --error-soft: #fdecec;
  --error-deep: #c50000;

  /* Structure */
  --hairline-color: #ebebeb;
  --hairline: 1px solid #ebebeb;
  --hairline-soft: 1px solid #f2f2f2;
  --hairline-strong: #a1a1a1;
  --shadow-hover: 0 1px 1px rgba(0, 0, 0, 0.02), 0 2px 2px rgba(0, 0, 0, 0.04);
  /* Cards: ring + stacked drop. Use INSTEAD of border, never with it. */
  --shadow-card: 0 0 0 1px rgba(0, 0, 0, 0.08), 0 1px 1px rgba(0, 0, 0, 0.02),
    0 2px 2px rgba(0, 0, 0, 0.04);
  --shadow-popover: 0 0 0 1px rgba(0, 0, 0, 0.08), 0 8px 16px -4px rgba(0, 0, 0, 0.04),
    0 24px 32px -8px rgba(0, 0, 0, 0.06);

  /* Radius hierarchy */
  --radius-control: 6px;
  --radius-card: 8px;
  --radius-pill: 9999px;

  /* Typography */
  --font-sans: "Inter Variable", "Inter", -apple-system, BlinkMacSystemFont,
    "Segoe UI", Helvetica, Arial, sans-serif;
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

table {
  font-variant-numeric: tabular-nums;
}

input:focus,
select:focus {
  outline: none;
  border-color: var(--link);
  box-shadow: 0 0 0 3px rgba(0, 112, 243, 0.18);
}

button:focus-visible {
  outline: 2px solid var(--link);
  outline-offset: 2px;
}

input[type="checkbox"] {
  accent-color: var(--ink);
}

::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}
::-webkit-scrollbar-thumb {
  background: #d4d4d4;
  border-radius: 999px;
}
::-webkit-scrollbar-thumb:hover {
  background: #a1a1a1;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.spinner {
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 2px solid var(--hairline-color);
  border-top-color: var(--ink);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@media (prefers-reduced-motion: reduce) {
  .spinner {
    animation: none;
  }
}
```

- [ ] **Step 2: Edit `frontend/src/theme.ts`.**

Header line 3 → `// Palette source: docs/superpowers/specs/2026-09-25-design-refresh-vercel-style-design.md`

Replace the chart-chrome block:

```ts
// Vercel-style ink/hairline chart chrome
export const INK = "#171717";
export const MUTED = "#666666";
export const MUTED_SOFT = "#888888";
export const GRID = "#f2f2f2";
export const AXIS_LINE = "#ebebeb";
```

Replace `WAFER_COLORSCALE` value (keep its doc comment):

```ts
export const WAFER_COLORSCALE: [number, string][] = [
  [0.0, "#d3e5ff"],
  [0.5, "#0070f3"],
  [1.0, "#0a3a82"],
];
```

Replace `STATUS_PLOT_COLOR` and its comment:

```ts
/** Plotly parses colors with tinycolor and cannot resolve CSS custom
 *  properties — a `var(--error)` marker silently renders black, with no
 *  error. Literal mirror of STATUS_COLOR for anything handed to Plotly.
 *  Values match index.css. They intentionally differ from the backend's
 *  STATUS_HEX (PDF keeps the previous palette — out of scope for the
 *  Vercel refresh). */
export const STATUS_PLOT_COLOR: Record<string, string> = {
  red: "#ee0000", yellow: "#f5a623", gray: "#888888", ok: INK, excluded: INK,
};
```

`SPEC_LINE_COLOR` → `"#ee0000"`. Leave `BIN_COLORS`, `FONT_FAMILY`, `STATUS_COLOR`, `STATUS_MARK` untouched.

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run build && npm run lint`
Expected: both succeed.
Run: `grep -nE 'cc785c|141413|c64545|faf9f5' frontend/src/index.css frontend/src/theme.ts`
Expected: no output.
Run: `git diff --stat -- frontend/src/theme.ts && git diff frontend/src/theme.ts | grep -A12 'BIN_COLORS = \['`
Expected: no `-`/`+` lines inside the BIN_COLORS array.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/index.css frontend/src/theme.ts
git commit -m "style: switch design tokens to Vercel-style palette"
```

---

### Task 2: Shared UI kit + TopNav

**Files:**
- Modify: `frontend/src/ui/Button.tsx`, `frontend/src/ui/Select.tsx`, `frontend/src/ui/PageTitle.tsx`, `frontend/src/ui/Badge.tsx`, `frontend/src/ui/tableStyles.ts`, `frontend/src/ui/CheckListCard.tsx`, `frontend/src/components/TopNav.tsx`

**Interfaces:**
- Consumes: CSS variables from Task 1.
- Produces: no API changes — same props/exports; only style values change.

- [ ] **Step 1: `ui/Button.tsx`** — doc comment and styles:

```ts
/** Kit button. primary = ink black (one main action per view); secondary =
 *  white with hairline; ghost = borderless ink text link-button. */
```

```ts
const base: CSSProperties = {
  height: 32,
  padding: "0 14px",
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
  ghost: { background: "none", color: "var(--ink)", border: "none", padding: 0, height: "auto", fontSize: 12 },
};
```

(`disabledStyles` unchanged.)

- [ ] **Step 2: `ui/Select.tsx`** — height matches buttons:

```ts
/** Kit select: 32px, hairline border, control radius. Focus ring comes from
 *  the global select:focus rule in index.css (blue). */
```
and `height: 32,` in `base`.

- [ ] **Step 3: `ui/PageTitle.tsx`**

```ts
/** Page heading: 24/600 ink title (tight tracking) with an optional subtext line below. */
```
```ts
  title: {
    fontSize: 24,
    fontWeight: 600,
    color: "var(--ink)",
    letterSpacing: "-0.04em",
    lineHeight: 1.25,
  },
```

- [ ] **Step 4: `ui/Badge.tsx`** — variants:

```ts
const variants: Record<Variant, CSSProperties> = {
  neutral: { background: "var(--surface-soft)", color: "var(--body)" },
  success: { background: "var(--success-soft)", color: "var(--success-deep)" },
  warning: { background: "var(--warning-soft)", color: "var(--warning-deep)" },
  error: { background: "var(--error-soft)", color: "var(--error-deep)" },
};
```
and in `base` change `letterSpacing: "0.02em"` → `letterSpacing: 0`.

- [ ] **Step 5: `ui/tableStyles.ts`** — sentence-case headers, soft red row:

Doc comment:
```ts
/** Shared data-table styles: sentence-case muted 12px headers on the canvas
 *  band, hairline-soft row rules, right-aligned tabular-nums numeric cells.
 *  Spread into <table>/<th>/<td> style props. */
```
In both `th` and `thLeft`: `fontWeight: 500`, `fontSize: 12`, remove `textTransform` and `letterSpacing` lines. `rowWarn: { background: "var(--error-soft)" }`.

- [ ] **Step 6: `ui/CheckListCard.tsx`** — card uses ring shadow instead of border (the inner `list` keeps its hairline border):

```ts
  card: {
    background: "var(--surface-card)",
    boxShadow: "var(--shadow-card)",
    borderRadius: "var(--radius-card)",
    padding: 20,
    marginBottom: 0,
    display: "flex",
    flexDirection: "column",
  },
```

- [ ] **Step 7: `components/TopNav.tsx`** — styles object:

```ts
const styles: Record<string, React.CSSProperties> = {
  nav: {
    display: "flex",
    alignItems: "center",
    gap: 4,
    padding: "0 24px",
    height: 56,
    background: "var(--surface-card)",
    borderBottom: "var(--hairline)",
    flexShrink: 0,
  },
  brand: {
    fontWeight: 600,
    marginRight: 20,
    color: "var(--ink)",
    letterSpacing: "-0.02em",
  },
  link: {
    padding: "6px 12px",
    borderRadius: "var(--radius-pill)",
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

- [ ] **Step 8: Verify**

Run: `cd frontend && npm run build && npm run lint` → both succeed.
Run: `grep -nE 'rgba\(|#[0-9a-fA-F]{6}|fontWeight: 700|uppercase' frontend/src/ui/*.ts* frontend/src/components/TopNav.tsx`
Expected: only `color: "#ffffff"` in Button.tsx.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/ui frontend/src/components/TopNav.tsx
git commit -m "style: reshape UI kit and top nav to Vercel style"
```

---

### Task 3: Pages/components — card rings, hard-coded colors, weights

**Files (all under `frontend/src/`):**
- Modify: `pages/DashboardPage.tsx`, `pages/ExplorePage.tsx`, `pages/WaferMapPage.tsx`, `pages/ReportPage.tsx`, `components/ErrorBanner.tsx`, `components/ReportView.tsx`, `components/YieldChart.tsx`, `components/dashboard/WarningsPopover.tsx`, `components/dashboard/Sparkline.tsx`, `components/dashboard/SummaryTable.tsx`, `components/wat/WatSummaryTab.tsx`, `components/wat/WatTrendTab.tsx`, `components/wat/WatSummaryTable.tsx`, `components/wat/WatScatterGrid.tsx`, `components/wat/WatItemTrendChart.tsx`, `components/wafermap/WaferMapCanvas.tsx`, `components/wafermap/WaferMapGrid.tsx`

**Interfaces:**
- Consumes: CSS variables from Task 1; `INK`, `STATUS_PLOT_COLOR` from `theme.ts`.
- Produces: nothing new.

- [ ] **Step 1: Error boxes → soft red.** In each of these style objects replace the `background: "rgba(198, 69, 69, 0.08)"` with `background: "var(--error-soft)"` and `color: "var(--error)"` with `color: "var(--error-deep)"`:
  - `pages/DashboardPage.tsx` `error` (~line 129)
  - `pages/ExplorePage.tsx` `error` (~line 168)
  - `pages/WaferMapPage.tsx` `error` (~line 315)
  - `components/wat/WatTrendTab.tsx` `error` (~line 166)
  - `components/wat/WatSummaryTab.tsx` `error` (~line 200)

  `components/ErrorBanner.tsx` `banner`:
```ts
    background: "var(--error-soft)",
    border: "1px solid rgba(238, 0, 0, 0.25)",
    borderRadius: "var(--radius-control)",
    margin: "0 16px 16px",
    fontSize: 13,
    color: "var(--error-deep)",
```

- [ ] **Step 2: Row tints / overlay / active chips**
  - `components/wat/WatSummaryTable.tsx`: `rowRed: { background: "var(--error-soft)" }`, `rowYellow: { background: "var(--warning-soft)" }`.
  - `pages/DashboardPage.tsx` `overlay.background` → `"rgba(250, 250, 250, 0.6)"`.
  - `components/wat/WatScatterGrid.tsx` and `pages/ReportPage.tsx` `chipActive.border` → `"1px solid var(--hairline-strong)"`.

- [ ] **Step 3: Plotly / canvas literals** (must stay literals — no `var(--`)
  - `components/YieldChart.tsx:59`: `line: { color: "rgba(238,0,0,0.6)", width: 1.5, dash: "dash" }`
  - `components/wat/WatScatterGrid.tsx:34-35`: `line: { color: "rgba(238,0,0,0.45)", ... }`, `fillcolor: "rgba(238,0,0,0.05)"`
  - `components/wat/WatItemTrendChart.tsx:53`: `marker: { size: 4, color: "rgba(23,23,23,0.45)" }`
  - `components/dashboard/Sparkline.tsx`: default prop `color = INK` (add `import { INK } from "../../theme";` if not already imported), line 38 `stroke="rgba(23,23,23,0.3)"`
  - `components/dashboard/SummaryTable.tsx:229`: `color={warn ? STATUS_PLOT_COLOR.red : INK}` (import both from `../../theme`, merging into an existing theme import if present)
  - `components/wafermap/WaferMapCanvas.tsx`: line 41 `"#f2f2f2"`, line 50 `"#ededed"`, line 51 `"#e5e5e5"` (keep the existing comments)
  - `components/wafermap/WaferMapGrid.tsx:135`: `noWafer: { color: "#a1a1a1", fontSize: 12 }`

- [ ] **Step 4: Cards → ring shadow.** In each card-style object below, replace `border: "var(--hairline)",` with `boxShadow: "var(--shadow-card)",` (keep everything else):
  - `pages/DashboardPage.tsx` `card`
  - `pages/ExplorePage.tsx` `card`
  - `pages/WaferMapPage.tsx` `card`
  - `components/YieldChart.tsx` `card`
  - `components/ReportView.tsx` `emptyCard`
  - `components/wat/WatSummaryTab.tsx` `lotHeader`
  - `components/wat/WatTrendTab.tsx` `header`
  - `components/wat/WatSummaryTable.tsx` `card`
  - `components/wat/WatScatterGrid.tsx` `card` (NOT `chip`)

  `components/dashboard/WarningsPopover.tsx` popover style: delete `border: "var(--hairline)",` and set `boxShadow: "var(--shadow-popover)",`.

  Verify no card has both or neither:
  Run: `grep -rn -B3 -A3 'radius-card' frontend/src | grep -cE 'boxShadow: "var\(--shadow-(card|popover)\)"'`
  Expected: `11` (9 above + CheckListCard + WarningsPopover).
  Run: `grep -rn -B3 -A3 'radius-card' frontend/src | grep -E 'border: "var\(--hairline\)"'`
  Expected: no output.

- [ ] **Step 5: Weight 700 → 600**
  - `components/ReportView.tsx` `title` (~line 112): `fontSize: 24, fontWeight: 600, letterSpacing: "-0.04em"` (keep `lineHeight`, `marginBottom`, `color`)
  - `pages/ExplorePage.tsx` `title` (~line 147): same three values.
  Run: `grep -rn 'fontWeight: 700' frontend/src` → no output.

  Plotly CSS-var guard:
  Run: `grep -nE 'var\(--' frontend/src/components/YieldChart.tsx frontend/src/components/wat/WatScatterGrid.tsx frontend/src/components/wat/WatItemTrendChart.tsx`
  Expected: matches only inside the `styles` objects at the bottom of each file (React style props), never inside Plotly `data`/`layout` objects. Inspect each match.

- [ ] **Step 6: Warning-colored text**
  Run: `grep -rn 'color: "var(--warning)"' frontend/src`
  For every match that colors **text** (e.g. `WatSummaryTab.tsx` `yellow`, and any in `WatTrendTab.tsx`/`SummaryTable.tsx`), change to `color: "var(--warning-deep)"`. Matches that color a dot/swatch/background stay `--warning`.

- [ ] **Step 7: Verify**

Run: `cd frontend && npm run build && npm run lint` → both succeed.

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "style: apply Vercel palette to pages, charts and cards"
```

---

### Task 4: Sweep + visual verification

**Files:** only fixes found by the sweep.

- [ ] **Step 1: Warm-color sweep**

Run:
```bash
grep -rnE '141413|c64545|cc785c|d4a017|5db872|faf9f5|f5f0e8|e6dfd8|ebe6df|6c6a64|8e8b82|3d3d3a|f3f2f0|eceae7|e3e1de|c8c3ba|d9d2c7|b8b2a7|rgba\(20, ?20, ?19|rgba\(198, ?69, ?69|rgba\(204, ?120, ?92|rgba\(212, ?160, ?23|rgba\(93, ?184, ?114|coral|cream' frontend/src
```
Expected: no output. Fix any hit per the spec tables (§1/§4), then re-run.

- [ ] **Step 2: Protected palettes untouched**

Run: `git diff main -- frontend/src/theme.ts | grep -E '^[-+].*"#(2a78d6|eb6834|1baf7a|eda100|e87ba4|008300|4a3aa7|e34948)"'` → no output.
Run: `git diff main --stat -- backend/ frontend/src/pages/WaferMapPage.tsx | cat` → `backend/` absent; WaferMapPage changes limited to the `error`/`card` styles (inspect `git diff main -- frontend/src/pages/WaferMapPage.tsx | grep PALETTE` → no output).

- [ ] **Step 3: Build, lint, backend tests**

Run: `cd frontend && npm run build && npm run lint` → succeed.
Run: `cd backend && uv run pytest -q` → all pass.

- [ ] **Step 4: Screenshots (mock mode)**

Start: `cd backend && uv run uvicorn app.main:app --port 8000` (background). Using Playwright, open and screenshot at 1440×900:
- `http://localhost:8000/dashboard` (then open the warnings popover if the badge exists)
- `http://localhost:8000/report` (select a product; Yield view, then PCM/WAT tabs)
- `http://localhost:8000/explore` (via a Dashboard row link if direct URL needs params)
- `http://localhost:8000/wafermap` (select a lot so the map renders)

Check each: no coral/beige; black primary buttons; cards show a thin ring; red/yellow status readable; chart markers not unexpectedly black; wafer pass dies distinguishable from disc and deselected bins. Tab-key onto a primary button shows the blue focus ring.

- [ ] **Step 5: Commit fixes (if any)**

```bash
git add frontend/src
git commit -m "style: fix leftovers from Vercel refresh sweep"
```
