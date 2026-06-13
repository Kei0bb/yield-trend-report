# Dashboard & Explore Improvements — Design

Date: 2026-06-13

## Goal

Four scoped improvements to the **Dashboard** and **Explore (drill-down)** pages.
The **Report page and all PDF generation logic are out of scope and MUST NOT
change** (hard constraint).

| # | Page | Change |
|---|------|--------|
| 1 | Explore | Show **raw** bin categories (no CSV mapping); keep **top 10** bins by average %, collapse the rest into **"Other"** |
| 2 | Dashboard | Show major process + sub-processes as **hierarchical rows** (大工程CP + CP1 + CP2; FT likewise) |
| 3 | Explore | Remove the week (year-week) display; show **lot_id only** |
| 4 | All | Translate remaining **Japanese anomaly warning messages** to English |

## Non-Goals

- No change to the Report page, `yield_service.py`, `pdf_service.py`, `export.py`,
  or any PDF output.
- No sub-process-level drill-down on Explore (Explore stays at major-process level).
- No change to bin handling on the Dashboard path or to anomaly *thresholds*.

---

## Requirement 1 — Explore: raw bins, top 10 + Other

### Backend

- `lot_service.get_lots(nickname, process, months, *, raw_bins=False)` — new
  keyword arg threaded into `_load_dataframe` / `_aggregate`. When `raw_bins=True`,
  `_aggregate` **skips `apply_bin_groups`** and uses the DB `bin_name` directly as
  the bin category (`bin_code = bin_name`). The `raw_bin_code` values are still
  carried into `BinBreakdown.bin_codes`.
- Anomaly evaluation stays **inside `get_lots`**, running on the raw (full,
  pre-collapse) breakdown — `evaluate()` matches bins by name, which works
  identically for raw names.
- New `explore_service.build_explore(nickname, process, months)`:
  1. `lots = get_lots(nickname, process, months, raw_bins=True)`
  2. Compute each bin's **mean percent across all lots** (lots where the bin is
     absent count as 0% for that lot).
  3. Keep the **top 10** by mean percent. All remaining bins collapse into a
     single **"Other"** category: per lot, sum the collapsed bins' `percent` and
     `count`, union their `bin_codes`.
  4. `available_bins = [<top10 ordered by mean desc>, "Other"]` ("Other" only
     present when something was collapsed).
- `explore` router delegates to `build_explore`. **`ExploreLotsResponse` shape is
  unchanged** → the frontend receives ≤ 11 categories with no structural change.

### Scope guard

- Dashboard's `get_lots()` calls omit `raw_bins` → still CSV-mapped → anomaly
  behavior on the Dashboard is unchanged.
- `yield_service` / `pdf_service` are not touched (Report keeps CSV groups).

---

## Requirement 2 — Dashboard: hierarchical major + sub-process rows

### Backend

- `get_lots` / `_load_dataframe` gain an optional `process_values: list[str] | None`
  override. When provided, it bypasses `resolve_process_filter` and queries that
  exact PROCESS value list (used to fetch a single sub-process).
- `summary_service.build_summary`: for each `nickname` × major process in
  `{CP, FT}`:
  - Build the **major row** (`level=0`) exactly as today (all sub-processes
    combined via `resolve_process_filter`).
  - For each value in `resolve_process_filter(nickname, major)`, build a **sub
    row** (`level=1`) via `get_lots(..., process_values=[value])`, label = the DB
    PROCESS value verbatim.
  - Sub rows are emitted immediately after their major row (ordering preserved).
- `SummaryRow` schema gains:
  - `level: int` — `0` major, `1` sub-process.
  - `process_label: str` — display label (major name for level 0, DB PROCESS
    value for level 1). `process` stays the **major** name (used for navigation).
- Graceful degradation: no config / empty sub-process list → only the major row
  (current behavior).

### Mock

- `get_lots(..., process_values=[value])` → `_load_dataframe` passes the value to
  `mock_lot_dataframe(nickname, value, months)`, which seeds per process string so
  each sub-process differs. **Note:** in mock mode the major row is *not* the
  arithmetic sum of its sub rows (independent fake series); real DB data is
  correct. Acceptable for development.

### Frontend (`SummaryTable.tsx`)

- Render sub rows **indented** beneath their major row (visual hierarchy via
  left padding / a leading glyph on `level===1`).
- Display `process_label` instead of `process` in the label cell.
- Row click still navigates to `/explore/<product_id>/<process>` (major process)
  for both levels — sub-process-only Explore is out of scope.
- Sorting: keep major+sub grouped together (sort majors, keep subs attached).

---

## Requirement 3 — Explore: lot_id only

- Remove the Lot ID format `<select>` (raw / date / **year-week**) and all format
  state from `ExplorePage.tsx`; always render the raw `lot.lot_id`.
- `toProcessData` and `LotTable` use `lot.lot_id` directly (drop `formatLotId`).
- Delete `frontend/src/utils/formatLotId.ts` (only consumers are the three Explore
  files — verified via grep).

---

## Requirement 4 — English-only anomaly messages

- `anomaly_service.evaluate()` currently emits Japanese:
  - `f"前期比 -{drop:.1f}% (閾値 -{threshold:.1f}%)"`
  - `f"{b.bin_name} が過去平均の {b.percent / avg:.1f}倍"`
- Translate to English, e.g.:
  - `f"-{drop:.1f}% vs prior avg (threshold -{threshold:.1f}%)"`
  - `f"{b.bin_name} is {b.percent / avg:.1f}× the prior average"`
- No threshold/logic change — string-only.

---

## Verification

- Backend: `uv run python -c "import app.main"` import check; hit
  `/api/explore/lots` and `/api/dashboard/summary` in mock mode and inspect JSON
  (≤11 bins incl. "Other"; hierarchical rows with `level`/`process_label`).
- Frontend: `npm run build` + `npm run lint`.
- **Browser UI check (required by user):** build, run the single server, open the
  Dashboard and Explore pages, confirm no layout breakage (hierarchical rows
  render cleanly, Explore charts/tables show raw bins + lot_id, no week selector).

## Files Touched

Backend: `lot_service.py`, `explore_service.py` (new), `summary_service.py`,
`schemas.py` (`SummaryRow`), `routers/explore.py`, `anomaly_service.py`.
Frontend: `pages/ExplorePage.tsx`, `components/explore/LotTable.tsx`,
`components/dashboard/SummaryTable.tsx`, `types.ts` (`SummaryRow`), delete
`utils/formatLotId.ts`.

**Untouched (hard constraint):** `yield_service.py`, `pdf_service.py`,
`routers/export.py`, Report page components.
