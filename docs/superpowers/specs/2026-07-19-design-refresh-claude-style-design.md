# Design refresh — "Claude-style data tool"

**Date:** 2026-07-19
**Scope:** Frontend visuals only — tokens, fonts, shared UI kit, all four pages, chart theme. Zero functional change; all existing backend tests (75) and frontend build/lint must pass unchanged. PDF styling is a later phase.

## Direction

Adopt the Anthropic/Claude design language (warm cream canvas, coral primary,
hairline borders, sparse serif display type, "color-block first, shadow rare"
elevation), adapted for a dense data tool by borrowing two practices:

- **PostHog** — cream canvas × white bordered cards as the chart/data surface.
- **Stripe** — tabular figures (`tnum`) wherever numbers carry meaning; dense,
  disciplined data tables.

Reference token sources (downloaded from `VoltAgent/awesome-design-md`):
`design-md/claude/DESIGN.md`, `design-md/posthog/DESIGN.md`,
`design-md/stripe/DESIGN.md`.

## 1. Design tokens (`frontend/src/index.css`)

New CSS variables (Claude values):

```css
/* Surfaces */
--canvas: #faf9f5;         /* page background (cream) */
--surface-card: #ffffff;   /* card face on cream (PostHog practice) */
--surface-soft: #f5f0e8;   /* hover fills, subtle bands, active tab */

/* Text */
--ink: #141413;            /* headlines, primary numbers */
--body: #3d3d3a;           /* running text */
--muted: #6c6a64;          /* labels, secondary */
--muted-soft: #8e8b82;     /* captions, fine print */

/* Primary (coral) */
--primary: #cc785c;
--primary-active: #a9583e;
--primary-disabled: #e6dfd8;

/* Semantic (yield status) */
--success: #5db872;
--warning: #d4a017;
--error: #c64545;

/* Structure */
--hairline: 1px solid #e6dfd8;
--hairline-soft: 1px solid #ebe6df;
--shadow-hover: 0 1px 3px rgba(20, 20, 19, 0.08);

/* Radius hierarchy */
--radius-control: 8px;     /* buttons, inputs, selects */
--radius-card: 12px;       /* cards */
--radius-pill: 9999px;     /* badges */
```

**Migration safety:** keep every existing variable name (`--gray-700`,
`--notion-blue`, `--warm-white`, `--border-whisper`, `--shadow-card`, …) as an
alias re-pointed at the new values (e.g. `--notion-blue: var(--primary)`,
`--warm-white: var(--canvas)`, `--shadow-card: none` → replaced by hairline).
Inline styles across pages keep working during migration; aliases are removed
at the end once pages are converted.

Cards carry **no resting shadow** — elevation comes from the white-on-cream
contrast plus a hairline border. `--shadow-hover` only on interactive hover.

## 2. Fonts (self-hosted, no CDN)

Corporate networks block external CDNs, so fonts ship in the bundle:

- `@fontsource-variable/inter` — all UI, tables, labels, numbers.
- `@fontsource/lora` (400/500) — serif display, **page titles and PDF cover
  only** (Copernicus substitute).
- Numbers everywhere they matter (tables, axes, lot ids, percentages):
  `font-variant-numeric: tabular-nums` (Stripe `tnum` discipline).

Type scale:

| Token | Font | Size/Weight | Use |
|---|---|---|---|
| page-title | Lora | 28px / 500 | one per page |
| section-title | Inter | 18px / 600 | card group headers |
| card-title | Inter | 14px / 600 | card headers |
| body | Inter | 14px / 400 | default |
| label | Inter | 13px / 500 | form labels, list items |
| caption | Inter | 12px / 500 | table headers, hints |

## 3. Shared UI kit (`frontend/src/ui/`)

New directory; components use inline-style objects (project convention), all
values from tokens. No CSS-in-JS library.

| Component | Contract |
|---|---|
| `Card` | white face, hairline border, 12px radius, padding 20; optional title row; optional fixed `height` + flex-column (for the wafer-map filter row) |
| `Button` | variants `primary` (coral/white), `secondary` (white/ink + hairline), `ghost`; height 36, radius 8, 13px/500 label; disabled = `--primary-disabled` bg + muted text |
| `Select` / `Input` | height 36, hairline border, radius 8; focus ring = coral at 15% alpha (replaces blue ring in `index.css`) |
| `CheckListCard` | generalizes wafer-map `FilterCard`: titled fixed-height card with a bordered scroll list of checkbox rows; modes `single` and `multi`; optional per-row color swatch (bin filter) and footer slot. Lots / Bin cards migrate onto it |
| `PageTitle` | Lora 28/500 + optional muted subtext line |
| `Badge` | pill; variants `neutral`, `success`, `warning`, `error` (tinted bg + readable text) |
| `tableStyles` | exported style objects: 12px uppercase-tracked headers in `--muted`, hairline-soft row rules, right-aligned `tabular-nums` numeric cells |

## 4. Page application (no functional change)

- **TopNav** — cream background, hairline bottom border. Active tab: Claude
  `category-tab` pattern — `--surface-soft` fill + ink text, radius 8 (replaces
  blue underline/blue text).
- **DashboardPage** — summary table via `tableStyles`; yield status coloring
  moves to semantic tokens/`Badge`; cards via `Card`.
- **ReportPage** — toolbar controls via `Select`/`Button`; Export PDF becomes
  the page's coral primary; chart cards via `Card`; `PageTitle`.
- **ExplorePage** — same treatment; `LotTable` via `tableStyles`.
- **WaferMapPage** — `FilterCard` folds into `ui/CheckListCard`; Lots and Bin
  cards use it too (multi mode); buttons/cards from the kit. Layout, sizes,
  and behavior stay exactly as shipped in 53f55a8.
- Coral is scarce: primary action buttons, active states, links. Never used
  as a data color.

## 5. Chart theme (`frontend/src/theme.ts` + chart components)

- Shared Plotly layout base: white paper/plot background, grid `#e6dfd8`,
  zero-line `#d9d2c7`, font Inter / ink, tabular-nums tick labels, muted axis
  titles.
- `YIELD_LINE_COLOR` → `#141413` (ink).
- `BIN_COLORS` and the wafer-map Okabe-Ito fail palette are **unchanged** —
  data-color distinguishability beats brand purity.
- Sparkline (dashboard) recolored to ink/hairline tones.

## 6. Out of scope

- PDF restyle (serif cover, coral accents) — separate later phase; only the
  screen UI changes now.
- Dark surfaces (`#181715`) and dark mode — not used.
- Any behavior, layout-structure, API, or backend change.

## 7. Verification

- `npm run build` + `npm run lint`; backend `pytest` (75) unchanged.
- Mock-server screenshots of all four pages, before/after, delivered for
  review (headless browser; user cannot reach sandbox localhost).
- Checklist per page: no blue remnants (`#0075de`, focus ring), no resting
  card shadows, tabular-nums on numeric columns, exactly one serif title per
  page, coral only on primary actions.
