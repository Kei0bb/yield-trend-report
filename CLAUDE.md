# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Backend
```bash
cd backend

# Install dependencies (uv manages venv automatically)
uv sync

# Run with mock data (no Oracle DB required)
uv run uvicorn app.main:app --reload --port 8000

# Run against real Oracle DB
USE_MOCK_DATA=false uv run uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Frontend
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
npm run build      # production build → dist/
npm run lint       # ESLint
```

## Architecture

### Data Flow
1. User selects product(s), date range, and process(es) in `Sidebar.tsx`
2. `App.tsx` calls `POST /api/yield-data` via `api/client.ts`
3. Backend resolves product nicknames → actual `PRODUCT_ID`s via `product_config.csv`
4. `yield_service.py` queries Oracle (`SEMI_CP_HEADER`/`SEMI_CP_BIN_SUM` for CP, `SEMI_FT_HEADER`/`SEMI_FT_BIN_SUM` for FT)
5. Raw bin codes are mapped to group names via `bin_mappings/<bin_group>.csv`
6. Results are aggregated per lot (wafer → lot) and returned as `YieldResponse`
7. `ReportView.tsx` renders one `YieldChart.tsx` per (product × process) combination using Plotly

### Key Backend Files
- `backend/app/services/yield_service.py` — core data layer: product config, bin mapping, DB queries, mock data, aggregation
- `backend/app/routers/yield_data.py` — API routes including debug endpoints (`/api/debug/config`, `/api/debug/probe`)
- `backend/app/services/pdf_service.py` — PDF generation with ReportLab + kaleido (Plotly → image → A4 landscape)
- `backend/app/database.py` — Oracle connection pool (`oracledb` thin mode, no Instant Client needed)
- `backend/app/config.py` — reads `backend/.env`, `USE_MOCK_DATA` defaults to `true`

### Configuration Files (backend root)
- `product_config.csv` — maps UI nickname → CP/FT `PRODUCT_ID`(s) + `bin_group`
  - Supports `;`-delimited multiple IDs and Oracle `LIKE` wildcards (`%`)
  - `display_name` groups multiple nicknames into a single merged chart
- `bin_mappings/<bin_group>.csv` — maps numeric bin codes to group names, optionally per-process
- `bin_group.csv` — legacy fallback for the `default` bin group

### Product Nickname System
The nickname system decouples UI names from DB `PRODUCT_ID`s:
- `product_config.csv` is checked first (both mock and real DB)
- Multiple nicknames with the same `display_name` are merged into one chart series
- `cp_product_id` / `ft_product_id` can contain `;`-delimited IDs or `%` wildcards for LIKE queries

### Mock Mode
`USE_MOCK_DATA=true` (default) generates deterministic random data without Oracle. Bin mappings from CSV files are still applied to mock data, so `bin_mappings/*.csv` is exercised even in development.

### PDF Export
`POST /api/export-pdf` generates an A4 landscape PDF. Customize company branding at the top of `pdf_service.py` (`COMPANY_NAME`, `LOGO_PATH`, `CONFIDENTIAL`).

## Oracle DB Schema
The app reads from two pairs of tables:
- `SEMI_CP_HEADER` / `SEMI_CP_BIN_SUM` — CP test results
- `SEMI_FT_HEADER` / `SEMI_FT_BIN_SUM` — FT test results

Data is wafer-level (one row per wafer+bin_code); the app aggregates to lot-level. `lot_id` is derived as `IYYY"W"IW` (ISO year-week) from `CREATE_DATE`.

## Debugging
- `/api/debug/config?nickname=<name>` — inspect product config and bin mapping resolution
- `/api/debug/probe?nickname=<name>&process=CP&start_month=2025-01&end_month=2025-05` — run the actual DB query and see row counts
- Backend logs at WARNING level by default to ensure visibility; DB query logs always appear in terminal
