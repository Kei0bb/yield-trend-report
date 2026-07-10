# Wafer Map — filter row redesign, sub-process, Y-flip, copy-to-clipboard

**Date:** 2026-07-10
**Scope:** Frontend `WaferMapPage` + wafermap components; one small backend endpoint. No change to Report/PDF or Dashboard/Explore code.

## Goals

Three user requests on the Wafer Map tab:

1. **Y axis is upside-down** — the per-die canvas renders +Y downward relative to
   the real wafer; flip it so +Y points up (or matches DB orientation).
2. **Sub-process selection + compact horizontal filter row** — allow choosing a
   CP/FT/SLT *sub-process* (小工程, e.g. `CP1`, `cFT1`), and move Product /
   Process / Sub / Date into the same single row as the Lots and Bin-filter
   cards. Drop the 50/50 lots+bin blocks (too wide); everything compact so the
   wafer map gets the full width and height below.
3. **Copy wafer map to clipboard as an image** — a button that copies the whole
   rendered map grid (labels + wafers) to the clipboard as one PNG.

## Design

### Layout — one filter row of three fixed-height cards

Replace the current top toolbar + 50/50 lots/bin row with a single row of three
equal-height (300px) cards, left-aligned at natural widths (NOT 50%):

```
┌ Filters ─────┐ ┌ Lots ────────┐ ┌ Bin filter ──┐
│ Product [▾]  │ │ ☑ PROD-…025  │ │ ☐●7_Leak     │
│ Process [▾]  │ │ ☑ PROD-…024  │ │ ☐●13_VDD     │
│ Sub     [▾]  │ │ …(scroll)    │ │ …(scroll)    │
│ From    [📅] │ │ Select all…  │ │              │
│ To      [📅] │ │ [Show maps]  │ │              │
│ [Load lots]  │ └──────────────┘ └──────────────┘
└──────────────┘
[ Wafer map — full width ]   header right: [📋 Copy image]
```

- **Filters card**: Product, Process, Sub, From, To selects stacked vertically
  (label + control per row), then the `Load lots` button. Width ~200px.
- **Lots card**: unchanged internals (scrollable checkbox list, Select all /
  Clear, counter, `Show maps` button). Width ~260px. `MAX_LOTS` stays **12**.
- **Bin filter card**: unchanged — keeps its scrollable checkbox list (`BinLegend`).
  Width ~220px.
- All three share the existing `halfCard` fixed-height + flex-column style,
  renamed to `filterCard` (drop the `width:50%`; add a per-card `width`/`flex`
  so they stay compact and left-aligned rather than stretching).
- The row wraps on narrow viewports (`flexWrap: wrap`).
- Wafer map card stays full-width below with a header row holding the meta text
  and the new `📋 Copy image` button (right-aligned).

### Sub-process

- **Backend**: new `GET /api/wafermap/process-subs?product_id=<id>` returning
  the sub-process DB PROCESS values per major process:
  `{ "CP": ["CP1","CP2"], "FT": ["cFT1"], "SLT": [] }`.
  Implemented with the existing `resolve_sub_processes(nickname, process)` for
  each of CP/FT/SLT (via `nickname_for_product_id`). In mock mode (no config)
  every list is empty → the Sub dropdown shows only "All".
- **Frontend**: fetch once when `productId` changes; store `subsByProcess`.
  The **Sub** `<select>` lists `All`（value `""`, merged/major view）plus each
  sub value for the current `process`. Selecting a sub sets the existing `sub`
  state, which already flows through `fetchWaferMapLots(..., sub)` and the
  `POST /wafermap` `sub` field end-to-end (no other backend change needed).
- Changing Process resets `sub` to `""` (already done on process change).

### Y-flip (#1)

In `WaferMapCanvas`, the die Y coordinate currently maps as
`(maxY - wafer.y[i] + 1) * cellY` ("+Y up"). The rendered map is vertically
mirrored vs. the real wafer, so change it to `(wafer.y[i] - minY + 1) * cellY`
(+Y down in screen space = correct orientation). X mapping unchanged. This is a
one-line change; verify visually that edge-ring / cluster patterns land where
expected (mock is symmetric, so confirm against a known asymmetric case if
available, else accept the flip as the correct convention).

### Copy image (#3)

- Add a `📋 Copy image` button in the wafer-map card header, shown only when
  `mapData` exists.
- `WaferMapGrid` takes a `ref` on its scroll container. On copy, the helper
  composites from the live DOM (single explicit approach):
  1. Measure the container's `scrollWidth`/`scrollHeight`. Create one offscreen
     canvas of that size × `devicePixelRatio`, fill white.
  2. For every `<canvas>` in the grid, compute its position relative to the
     container (`getBoundingClientRect` deltas, accounting for scroll) and
     `drawImage` it there. For every `<th>` header (column `W#` and row lot id),
     read its text + relative position and `fillText` it in matching font/color.
  3. `offscreen.toBlob(blob => navigator.clipboard.write([new ClipboardItem({
     "image/png": blob })]))`.
- `navigator.clipboard.write` requires a secure context; `localhost` and HTTPS
  qualify. On failure (older browser / permission), fall back to a temporary
  toast/error message; do not throw.
- Keep the composite helper in its own module
  (`frontend/src/components/wafermap/copyGrid.ts`) so `WaferMapGrid` stays
  focused. It receives the grid container element and returns a Promise.

## Out of scope / unchanged

- Report page, PDF export, Dashboard, Explore.
- The die-data query, caching, bin-label resolution, `MAX_LOTS=12`.
- No new external libraries — compositing uses the native Canvas API.

## Testing

- Backend: unit test the new `process-subs` endpoint (mock mode → all empty;
  and, if feasible, a config fixture → subs listed).
- Frontend: `npm run build` + `npm run lint`; manual verification via headless
  screenshot (filter row layout, Sub dropdown, Y-orientation, Copy image writes
  a PNG to the clipboard — verify the button path runs without error).
