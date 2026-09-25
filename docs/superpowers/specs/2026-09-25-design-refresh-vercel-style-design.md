# Design Refresh — Vercel Style (screen only)

- Date: 2026-09-25
- Supersedes (screen side): `2026-07-19-design-refresh-claude-style-design.md`
- Source: https://getdesign.md/vercel/design-md (VoltAgent/awesome-design-md `design-md/vercel/DESIGN.md`)

## Goal

Replace the warm Claude-style look (coral primary, beige neutrals) with Vercel's
stark ink-on-near-white language, while keeping the tool's data density.
Only the in-app subset of the Vercel spec is adopted.

## Decisions

| Topic | Decision |
|---|---|
| Font | Keep Inter (self-hosted `@fontsource-variable/inter`). Vercel's spec names Inter as the Geist substitute. No Geist / Geist Mono. |
| PDF (ReportLab) | Out of scope. `backend/app/services/pdf_service.py` unchanged. |
| Density | Unchanged. Body 14px, tables 12–13px, current paddings/layout. |
| Marketing parts | Not adopted: 100px pill CTAs, mesh gradient, 64–192px section padding, polarity-flipped dark bands. |
| Data colors | `BIN_COLORS` (CVD-validated order) and WaferMapPage Okabe-Ito `PALETTE` unchanged. |
| Success color | Stays green (Vercel maps success to blue; green reads as "good yield" for engineers). |
| Dark mode | Not added. |

## 1. Tokens — `frontend/src/index.css`

Keep existing variable names; change values. Add the new ones listed.

| Variable | Old | New |
|---|---|---|
| `--canvas` | `#faf9f5` | `#fafafa` |
| `--surface-card` | `#ffffff` | `#ffffff` |
| `--surface-soft` | `#f5f0e8` | `#f5f5f5` |
| `--ink` | `#141413` | `#171717` |
| `--body` | `#3d3d3a` | `#4d4d4d` |
| `--muted` | `#6c6a64` | `#666666` |
| `--muted-soft` | `#8e8b82` | `#888888` |
| `--primary` | `#cc785c` | `#171717` |
| `--primary-active` | `#a9583e` | `#383838` |
| `--primary-disabled` | `#e6dfd8` | `#ebebeb` |
| `--success` | `#5db872` | `#45a557` |
| `--warning` | `#d4a017` | `#f5a623` |
| `--error` | `#c64545` | `#ee0000` |
| `--hairline-color` / `--hairline` | `#e6dfd8` | `#ebebeb` |
| `--hairline-soft` | `#ebe6df` | `#f2f2f2` |
| `--radius-control` | `8px` | `6px` |
| `--radius-card` | `12px` | `8px` |
| `--shadow-hover` | `0 1px 3px rgba(20,20,19,.08)` | `0 1px 1px rgba(0,0,0,.02), 0 2px 2px rgba(0,0,0,.04)` |

New variables:

| Variable | Value | Use |
|---|---|---|
| `--hairline-strong` | `#a1a1a1` | Stronger divider, hover border |
| `--link` | `#0070f3` | Focus ring, inline links |
| `--error-soft` | `#fdecec` | Error banner / red row background |
| `--error-deep` | `#c50000` | Error text on soft background |
| `--warning-soft` | `#fff5e0` | Yellow row / warning badge background |
| `--warning-deep` | `#ab570a` | Warning text on soft background |
| `--success-soft` | `#e8f5eb` | Success badge background |
| `--success-deep` | `#2e7d3e` | Success badge text |
| `--shadow-card` | `0 0 0 1px rgba(0,0,0,.08), 0 1px 1px rgba(0,0,0,.02), 0 2px 2px rgba(0,0,0,.04)` | Cards (replaces border where cards currently use hairline + no shadow; either the ring or the border, not both) |
| `--shadow-popover` | `0 0 0 1px rgba(0,0,0,.08), 0 8px 16px -4px rgba(0,0,0,.04), 0 24px 32px -8px rgba(0,0,0,.06)` | Popovers / dropdowns |

Global rules in `index.css`:
- Focus: `border-color: var(--link); box-shadow: 0 0 0 3px rgba(0,112,243,.18)`.
- Checkbox `accent-color: var(--ink)`.
- Scrollbar thumb `#d4d4d4`, hover `#a1a1a1`.
- Spinner top color `var(--ink)`.
- `table { font-variant-numeric: tabular-nums; }`.
- Header comment updated to reference this spec.

## 2. Chart tokens — `frontend/src/theme.ts`

| Constant | New |
|---|---|
| `INK` | `#171717` |
| `MUTED` | `#666666` |
| `MUTED_SOFT` | `#888888` |
| `GRID` | `#f2f2f2` |
| `AXIS_LINE` | `#ebebeb` |
| `WAFER_COLORSCALE` | `[[0,"#d3e5ff"],[0.5,"#0070f3"],[1,"#0a3a82"]]` (single-hue blue ramp) |
| `STATUS_PLOT_COLOR` | red `#ee0000`, yellow `#f5a623`, gray `#888888` |
| `SPEC_LINE_COLOR` | `#ee0000` |

- `BIN_COLORS` unchanged.
- Update the "Palette source" comment and the `STATUS_PLOT_COLOR` comment: screen values now intentionally differ from backend `STATUS_HEX` (PDF out of scope).

## 3. Components

- **`ui/Button.tsx`** — height 32, radius `--radius-control` (6px), fontSize 13, weight 500. primary: `--primary` bg / white text; hover not required. secondary: white bg + hairline, hover border `--hairline-strong` optional. ghost: `--ink` text (was coral), underline on hover not required. Doc comment updated.
- **`components/TopNav.tsx`** — white (`--surface-card`) background, height 56, hairline bottom. Brand weight 600, letter-spacing `-0.02em`. Links: 14px/500 `--muted`, radius `--radius-pill`, padding `6px 12px`; active: `--surface-soft` bg + `--ink` text.
- **`ui/PageTitle.tsx`** — 24px / 600, letter-spacing `-0.04em`, subtext 13px `--muted`.
- **Weight 700 → 600** everywhere: `ReportView.tsx:112`, `ExplorePage.tsx:147`, `TopNav.tsx:52`, `PageTitle.tsx:22`, plus any others found.
- **Tables** (`ui/tableStyles.ts` and tables using it) — header row bg `--canvas`, 12px / 500 / `--muted`, sentence case (no uppercase), row divider `--hairline`.
- **Cards** (`ui/CheckListCard.tsx` and inline card styles) — radius `--radius-card`, `--shadow-card` instead of `--hairline` border.
- **`ui/Badge.tsx`** — success/warning/error use the new `*-soft` bg + `*-deep` text tokens; radius `--radius-pill`.
- **`components/dashboard/WarningsPopover.tsx`** — `--shadow-popover`.

## 4. Hard-coded colors to replace

| File | Current | Replace with |
|---|---|---|
| `pages/DashboardPage.tsx:129`, `components/ErrorBanner.tsx:22-23`, `pages/WaferMapPage.tsx:315`, `pages/ExplorePage.tsx:168`, `components/wat/WatTrendTab.tsx:166`, `components/wat/WatSummaryTab.tsx:200` | `rgba(198,69,69,…)` bg/border | `--error-soft` bg, `--error` border/text (`--error-deep` for text on soft bg) |
| `pages/DashboardPage.tsx:160` | `rgba(250,249,245,.55)` loading veil | `rgba(250,250,250,.6)` |
| `components/wat/WatSummaryTable.tsx:149-150` | red/yellow row rgba | `--error-soft` / `--warning-soft` |
| `components/wat/WatScatterGrid.tsx:34-35`, `components/YieldChart.tsx:59` | `rgba(198,69,69,…)` (Plotly) | `rgba(238,0,0,…)` same alphas (literal, Plotly can't read CSS vars) |
| `components/wat/WatScatterGrid.tsx:140`, `pages/ReportPage.tsx:228` | coral border `rgba(204,120,92,.45)` | `1px solid var(--hairline-strong)` |
| `components/dashboard/WarningsPopover.tsx:177` | warm shadow | `var(--shadow-popover)` |
| `components/dashboard/Sparkline.tsx:10,38` | `#141413`, `rgba(20,20,19,.3)` | `INK`, `rgba(23,23,23,.3)` |
| `components/dashboard/SummaryTable.tsx:229` | `#c64545` / `#141413` | `STATUS_PLOT_COLOR.red` / `INK` |
| `components/wat/WatItemTrendChart.tsx:53` | `rgba(20,20,19,.45)` | `rgba(23,23,23,.45)` |
| `components/wafermap/WaferMapCanvas.tsx:41,50,51` | warm grays `#f3f2f0` `#eceae7` `#e3e1de` | neutral `#f2f2f2` `#ededed` `#e5e5e5` |
| `components/wafermap/WaferMapGrid.tsx:135` | `#c8c3ba` | `#a1a1a1` |

Final sweep: `grep -rnE '#[0-9a-fA-F]{6}|rgba\(' frontend/src` — any remaining warm tone (`141413`, `c64545`, `cc785c`, `d4a017`, beige grays, `rgba(20,20,19`, `rgba(198,69,69`, `rgba(204,120,92`, `rgba(212,160,23`, `rgba(93,184,114`) must be gone, except `BIN_COLORS` and WaferMapPage `PALETTE`.

## Out of scope

PDF / backend, layout and density, fonts, dark mode, `BIN_COLORS`, wafer-map Okabe-Ito palette, new components.

## Verification

1. `cd frontend && npm run lint && npm run build` pass.
2. Backend in mock mode; screenshot Dashboard (incl. warnings popover), Report (Yield + PCM/WAT tabs), Explore, Wafer Map. Check: no coral/beige left, status colors readable, charts render (no black markers from CSS vars in Plotly).
3. `cd backend && uv run pytest` still passes (no backend change expected; sanity only).
