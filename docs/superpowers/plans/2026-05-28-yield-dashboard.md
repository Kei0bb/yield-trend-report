# Yield Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing yield-report tool into a 3-tab app (Dashboard / Report / Explore) for daily yield monitoring, anomaly detection, and lot-level drill-down — without touching the PDF or existing `/api/yield-data` logic.

**Architecture:** New backend endpoints (`/api/dashboard/summary`, `/api/explore/lots`, `/api/anomaly/config`) backed by new services (`lot_queries`, `lot_service`, `summary_service`, `anomaly_service`) that query real lot-granular data (CP=`SUBSTRATE_ID`, FT/SLT=`ASSY_LOT_ID`) — entirely separate from the week-aggregated `yield_service`. Frontend gains React Router with three pages; the existing Report flow is moved verbatim into `ReportPage`.

**Tech Stack:** FastAPI + pydantic + pandas + oracledb (backend), pytest + httpx (tests), React 19 + react-router-dom + Plotly + axios + Vite (frontend).

---

## Invariants (DO NOT BREAK)

- `backend/app/services/pdf_service.py`, `backend/app/routers/export.py`, `POST /api/export-pdf` — never modified.
- `backend/app/services/yield_service.py`, `yield_queries.py`, `yield_aggregator.py`, `POST /api/yield-data` — never modified.
- `product_config.csv` / `bin_mappings/` structure unchanged (read-only reuse).
- Report tab behavior (charts + PDF) identical after the frontend refactor.

## Conventions

- Run all backend commands from `backend/` with `uv run`.
- JSON field for a yield percentage is `yield_pct` everywhere (matches existing codebase; avoids the Python `yield` keyword). The spec's `"yield"` is realized as `yield_pct`.
- `lot_date` is an ISO date string `"YYYY-MM-DD"`.
- Lot lists are always ordered oldest → newest; the **last** element is the "latest" lot.
- Anomaly warnings are computed against the latest lot vs. the prior lots, and attached to the **latest** lot only.

## File Structure

**Backend (new):**
- `backend/anomaly_config.yaml` — anomaly thresholds (defaults + per-product overrides)
- `backend/app/services/anomaly_service.py` — load YAML, resolve config, `evaluate(lots, config)`
- `backend/app/services/lot_queries.py` — real-lot-granular SQL + mock dispatch
- `backend/app/services/lot_service.py` — wafer→lot aggregation, bin breakdown, attach warnings
- `backend/app/services/summary_service.py` — build dashboard rows from lots
- `backend/app/routers/dashboard.py` — `GET /api/dashboard/summary`
- `backend/app/routers/explore.py` — `GET /api/explore/lots`
- `backend/app/routers/anomaly_config.py` — `GET /api/anomaly/config`
- `backend/tests/conftest.py`, `backend/tests/test_*.py`

**Backend (modified):**
- `backend/app/models/schemas.py` — add response models (append only)
- `backend/app/services/mock_data.py` — add `mock_lot_dataframe(...)` (append only)
- `backend/app/main.py` — register 3 new routers (3 lines)
- `backend/pyproject.toml` — add `pyyaml` dependency

**Frontend (new):**
- `frontend/src/pages/{DashboardPage,ReportPage,ExplorePage}.tsx`
- `frontend/src/components/TopNav.tsx`
- `frontend/src/components/dashboard/{SummaryTable,Sparkline}.tsx`
- `frontend/src/components/explore/{LotTrendChart,LotTable}.tsx`
- `frontend/src/utils/formatLotId.ts`

**Frontend (modified):**
- `frontend/src/App.tsx` — becomes router shell
- `frontend/src/api/client.ts` — add dashboard/explore/anomaly fetchers (append only)
- `frontend/src/types/index.ts` — add new types (append only)
- `frontend/package.json` — add `react-router-dom`

---

# Phase A — Backend: anomaly_service (pure logic, TDD)

### Task A1: Test scaffolding + pyyaml dependency

**Files:**
- Create: `backend/tests/__init__.py` (empty)
- Create: `backend/tests/conftest.py`
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add pyyaml + pytest config**

In `backend/pyproject.toml`, add `"pyyaml"` to `dependencies` (after `"python-dotenv",`) and append a pytest section at end of file:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 2: Sync deps**

Run: `uv sync`
Expected: resolves and installs `pyyaml`.

- [ ] **Step 3: Create test package + conftest**

Create `backend/tests/__init__.py` as an empty file.

Create `backend/tests/conftest.py`:

```python
import os

# Force mock mode for the whole test session (no Oracle needed).
os.environ.setdefault("USE_MOCK_DATA", "true")
```

- [ ] **Step 4: Verify pytest collects nothing yet (no error)**

Run: `uv run pytest -q`
Expected: `no tests ran` (exit code 5 is fine) — confirms collection works.

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/tests/__init__.py backend/tests/conftest.py backend/uv.lock
git commit -m "test: add pytest scaffolding and pyyaml dependency"
```

---

### Task A2: anomaly_config.yaml + config loading/resolution

**Files:**
- Create: `backend/anomaly_config.yaml`
- Create: `backend/app/services/anomaly_service.py`
- Create: `backend/tests/test_anomaly_config.py`

- [ ] **Step 1: Write the YAML config**

Create `backend/anomaly_config.yaml`:

```yaml
# 異常検知の閾値設定。編集後はサーバ再起動で反映されます。
defaults:
  yield_drop:
    threshold_pct: 3.0      # (過去平均 - 最新) >= 3.0% で警告
    min_lots: 3             # 過去ロットがこれ未満なら yield_drop 判定をスキップ
  bin_surge:
    multiplier: 2.0         # 最新Bin% >= 過去平均Bin% × 2.0 で警告
    min_percent: 1.0        # 過去平均がこれ未満の Bin はノイズとして無視

overrides:
  # 製品 nickname 単位で defaults を部分上書きできる
  Product-A:
    yield_drop:
      threshold_pct: 5.0
```

- [ ] **Step 2: Write failing tests for config loading/resolution**

Create `backend/tests/test_anomaly_config.py`:

```python
from app.services.anomaly_service import load_anomaly_config, resolve_config


def test_load_returns_defaults_and_overrides():
    cfg = load_anomaly_config()
    assert cfg["defaults"]["yield_drop"]["threshold_pct"] == 3.0
    assert cfg["defaults"]["bin_surge"]["multiplier"] == 2.0
    assert "Product-A" in cfg["overrides"]


def test_resolve_without_override_returns_defaults():
    cfg = {"defaults": {"yield_drop": {"threshold_pct": 3.0, "min_lots": 3}},
           "overrides": {}}
    resolved = resolve_config("Unknown", cfg)
    assert resolved["yield_drop"]["threshold_pct"] == 3.0


def test_resolve_deep_merges_override():
    cfg = {
        "defaults": {"yield_drop": {"threshold_pct": 3.0, "min_lots": 3},
                     "bin_surge": {"multiplier": 2.0, "min_percent": 1.0}},
        "overrides": {"Product-A": {"yield_drop": {"threshold_pct": 5.0}}},
    }
    resolved = resolve_config("Product-A", cfg)
    assert resolved["yield_drop"]["threshold_pct"] == 5.0   # overridden
    assert resolved["yield_drop"]["min_lots"] == 3          # preserved from defaults
    assert resolved["bin_surge"]["multiplier"] == 2.0       # untouched section preserved
```

- [ ] **Step 3: Run tests — verify they fail**

Run: `uv run pytest tests/test_anomaly_config.py -v`
Expected: FAIL — `ModuleNotFoundError: app.services.anomaly_service`.

- [ ] **Step 4: Implement config loading/resolution**

Create `backend/app/services/anomaly_service.py`:

```python
import copy
import logging
from functools import lru_cache
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

ANOMALY_CONFIG_YAML = Path(__file__).parent.parent.parent / "anomaly_config.yaml"

_EMPTY_CONFIG: dict = {
    "defaults": {
        "yield_drop": {"threshold_pct": 3.0, "min_lots": 3},
        "bin_surge": {"multiplier": 2.0, "min_percent": 1.0},
    },
    "overrides": {},
}


@lru_cache(maxsize=1)
def load_anomaly_config() -> dict:
    """Load anomaly_config.yaml. Falls back to built-in defaults when absent.

    Cached for the process lifetime; restart the server after editing the YAML.
    """
    if not ANOMALY_CONFIG_YAML.exists():
        logger.warning("anomaly_config.yaml not found at %s — using built-in defaults",
                       ANOMALY_CONFIG_YAML)
        return copy.deepcopy(_EMPTY_CONFIG)
    with ANOMALY_CONFIG_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("defaults", copy.deepcopy(_EMPTY_CONFIG["defaults"]))
    data.setdefault("overrides", {})
    return data


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def resolve_config(nickname: str, config: dict) -> dict:
    """Return the effective threshold config for a product: defaults deep-merged
    with overrides[nickname]."""
    defaults = config.get("defaults", {})
    override = config.get("overrides", {}).get(nickname, {})
    return _deep_merge(defaults, override)
```

- [ ] **Step 5: Run tests — verify pass**

Run: `uv run pytest tests/test_anomaly_config.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/anomaly_config.yaml backend/app/services/anomaly_service.py backend/tests/test_anomaly_config.py
git commit -m "feat(anomaly): add YAML config loading and per-product resolution"
```

---

### Task A3: anomaly evaluate() — yield_drop + bin_surge

**Files:**
- Modify: `backend/app/services/anomaly_service.py`
- Create: `backend/tests/test_anomaly_evaluate.py`

The `evaluate` function operates on a list of lightweight lot objects. Each lot has attributes `yield_pct: float` and `bin_breakdown: list[obj]` where each breakdown item has `.bin_name: str`, `.percent: float`, `.bin_codes: list[int]`. (Task B2 defines the `LotData`/`BinBreakdown` pydantic models with exactly these attributes; tests here use a simple stand-in with the same shape.)

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_anomaly_evaluate.py`:

```python
from types import SimpleNamespace

from app.services.anomaly_service import evaluate

CFG = {
    "yield_drop": {"threshold_pct": 3.0, "min_lots": 3},
    "bin_surge": {"multiplier": 2.0, "min_percent": 1.0},
}


def _lot(yield_pct, bins=None):
    bins = bins or []
    bb = [SimpleNamespace(bin_name=n, percent=p, bin_codes=c) for (n, p, c) in bins]
    return SimpleNamespace(yield_pct=yield_pct, bin_breakdown=bb)


def test_no_warning_when_stable():
    lots = [_lot(95.0), _lot(95.2), _lot(94.8), _lot(95.1)]
    assert evaluate(lots, CFG) == []


def test_yield_drop_triggers():
    # past avg ~95, latest 90 → drop 5 >= 3.0
    lots = [_lot(95.0), _lot(95.0), _lot(95.0), _lot(90.0)]
    warns = evaluate(lots, CFG)
    types = [w["type"] for w in warns]
    assert "yield_drop" in types


def test_yield_drop_skipped_when_too_few_past_lots():
    # only 2 past lots (< min_lots=3)
    lots = [_lot(95.0), _lot(95.0), _lot(80.0)]
    assert [w for w in evaluate(lots, CFG) if w["type"] == "yield_drop"] == []


def test_bin_surge_triggers():
    past = [("Short", 1.0, [5])]
    latest = [("Short", 3.0, [5])]  # 3.0 >= 1.0 * 2.0, and past avg 1.0 >= min_percent
    lots = [_lot(95.0, past), _lot(95.0, past), _lot(95.0, past), _lot(95.0, latest)]
    warns = [w for w in evaluate(lots, CFG) if w["type"] == "bin_surge"]
    assert len(warns) == 1
    assert warns[0]["bin_code"] == 5


def test_bin_surge_ignores_tiny_baseline():
    past = [("Leak", 0.2, [7])]       # below min_percent=1.0
    latest = [("Leak", 0.9, [7])]
    lots = [_lot(95.0, past), _lot(95.0, past), _lot(95.0, past), _lot(95.0, latest)]
    assert [w for w in evaluate(lots, CFG) if w["type"] == "bin_surge"] == []


def test_empty_or_single_lot_returns_empty():
    assert evaluate([], CFG) == []
    assert evaluate([_lot(95.0)], CFG) == []
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `uv run pytest tests/test_anomaly_evaluate.py -v`
Expected: FAIL — `ImportError: cannot import name 'evaluate'`.

- [ ] **Step 3: Implement evaluate()**

Append to `backend/app/services/anomaly_service.py`:

```python
def evaluate(lots: list, config: dict) -> list[dict]:
    """Compare the latest lot against the prior lots and return warning dicts.

    `lots` is ordered oldest→newest. Each lot exposes `.yield_pct` and
    `.bin_breakdown` (items with `.bin_name`, `.percent`, `.bin_codes`).
    `config` is a resolved threshold dict (see resolve_config).
    Returns [] when there is no latest+past pair to compare.
    """
    if len(lots) < 2:
        return []

    latest, past = lots[-1], lots[:-1]
    warnings: list[dict] = []

    # --- B: yield drop vs past average ---
    yd = config.get("yield_drop", {})
    min_lots = yd.get("min_lots", 3)
    threshold = yd.get("threshold_pct", 3.0)
    if len(past) >= min_lots:
        past_avg = sum(l.yield_pct for l in past) / len(past)
        drop = past_avg - latest.yield_pct
        if drop >= threshold:
            warnings.append({
                "type": "yield_drop",
                "message": f"前期比 -{drop:.1f}% (閾値 -{threshold:.1f}%)",
                "severity": "warn",
            })

    # --- C: fail-bin surge vs past average per bin ---
    bs = config.get("bin_surge", {})
    multiplier = bs.get("multiplier", 2.0)
    min_percent = bs.get("min_percent", 1.0)
    # past average percent per bin_name
    past_pct: dict[str, list[float]] = {}
    bin_codes_by_name: dict[str, list[int]] = {}
    for lot in past:
        for b in lot.bin_breakdown:
            past_pct.setdefault(b.bin_name, []).append(b.percent)
            bin_codes_by_name.setdefault(b.bin_name, b.bin_codes)
    for b in latest.bin_breakdown:
        history = past_pct.get(b.bin_name)
        if not history:
            continue
        avg = sum(history) / len(history)
        if avg >= min_percent and b.percent >= avg * multiplier:
            codes = b.bin_codes or bin_codes_by_name.get(b.bin_name, [])
            warnings.append({
                "type": "bin_surge",
                "message": f"{b.bin_name} が過去平均の {b.percent / avg:.1f}倍",
                "severity": "warn",
                "bin_code": codes[0] if codes else None,
            })

    return warnings
```

- [ ] **Step 4: Run tests — verify pass**

Run: `uv run pytest tests/test_anomaly_evaluate.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/anomaly_service.py backend/tests/test_anomaly_evaluate.py
git commit -m "feat(anomaly): implement yield_drop and bin_surge evaluation"
```

---

# Phase B — Backend: schemas, lot data layer

### Task B1: Response schemas

**Files:**
- Modify: `backend/app/models/schemas.py`
- Create: `backend/tests/test_schemas.py`

- [ ] **Step 1: Write a failing test that imports the new models**

Create `backend/tests/test_schemas.py`:

```python
from app.models.schemas import (
    BinBreakdown, LotData, Warning, SparkPoint, SummaryRow,
    ExploreLotsResponse, DashboardSummaryResponse,
)


def test_lotdata_roundtrip():
    lot = LotData(
        lot_id="LOT-1", lot_date="2026-05-25", wafer_count=25, yield_pct=87.5,
        bin_breakdown=[BinBreakdown(bin_name="Short", bin_codes=[5], count=10, percent=4.0)],
        warnings=[Warning(type="yield_drop", message="x")],
    )
    dumped = lot.model_dump()
    assert dumped["yield_pct"] == 87.5
    assert dumped["bin_breakdown"][0]["bin_name"] == "Short"
    assert dumped["warnings"][0]["severity"] == "warn"


def test_summary_row_defaults():
    row = SummaryRow(
        nickname="P", display_name="P", process="CP",
        latest_yield=None, latest_lot_id=None, latest_lot_date=None,
        avg_yield_6m=None, delta=None, sparkline=[], warnings=[],
    )
    assert row.sparkline == []
```

- [ ] **Step 2: Run test — verify it fails**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: FAIL — ImportError for the new names.

- [ ] **Step 3: Append models to schemas.py**

Append to `backend/app/models/schemas.py`:

```python
# ---------------------------------------------------------------------------
# Dashboard / Explore models (additive — existing models above are unchanged)
# ---------------------------------------------------------------------------


class Warning(BaseModel):
    type: str                      # "yield_drop" | "bin_surge"
    message: str
    severity: str = "warn"
    bin_code: int | None = None


class BinBreakdown(BaseModel):
    bin_name: str
    bin_codes: list[int]
    count: int
    percent: float


class LotData(BaseModel):
    lot_id: str
    lot_date: str                  # ISO "YYYY-MM-DD"
    wafer_count: int
    yield_pct: float
    bin_breakdown: list[BinBreakdown] = []
    warnings: list[Warning] = []


class ExploreLotsResponse(BaseModel):
    nickname: str
    process: str
    period: dict
    lots: list[LotData]
    available_bins: list[str]


class SparkPoint(BaseModel):
    lot_id: str
    lot_date: str
    yield_pct: float


class SummaryRow(BaseModel):
    nickname: str
    display_name: str
    process: str
    latest_yield: float | None
    latest_lot_id: str | None
    latest_lot_date: str | None
    avg_yield_6m: float | None
    delta: float | None
    sparkline: list[SparkPoint] = []
    warnings: list[Warning] = []


class DashboardSummaryResponse(BaseModel):
    generated_at: str
    period: dict
    rows: list[SummaryRow]
```

- [ ] **Step 4: Run test — verify pass**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/schemas.py backend/tests/test_schemas.py
git commit -m "feat(schemas): add dashboard and explore response models"
```

---

### Task B2: Mock lot-granular dataframe

**Files:**
- Modify: `backend/app/services/mock_data.py`
- Create: `backend/tests/test_mock_lots.py`

This produces multiple lots per week (the real-world case from the spec), with a real-ish `lot_id` string and a `lot_date`. Columns superset the existing `COMMON_COLUMNS` by adding `lot_date`.

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_mock_lots.py`:

```python
from app.services.mock_data import mock_lot_dataframe


def test_mock_lot_dataframe_shape():
    df = mock_lot_dataframe("Product-A", "CP", months=6)
    assert not df.empty
    for col in ["lot_id", "lot_date", "wafer_id", "yield_pct",
                "gross_die", "raw_bin_code", "bin_name", "bin_fail_count"]:
        assert col in df.columns


def test_mock_lot_dataframe_has_multiple_lots_per_week():
    df = mock_lot_dataframe("Product-A", "CP", months=6)
    # distinct real lot ids should exceed distinct iso-weeks present
    weeks = {d[:7] for d in df["lot_date"]}
    assert df["lot_id"].nunique() > len(weeks)


def test_mock_lot_dataframe_deterministic():
    a = mock_lot_dataframe("Product-A", "FT", months=6)
    b = mock_lot_dataframe("Product-A", "FT", months=6)
    assert a.equals(b)
```

- [ ] **Step 2: Run test — verify it fails**

Run: `uv run pytest tests/test_mock_lots.py -v`
Expected: FAIL — `ImportError: cannot import name 'mock_lot_dataframe'`.

- [ ] **Step 3: Implement mock_lot_dataframe**

Append to `backend/app/services/mock_data.py`:

```python
from datetime import date, timedelta


def mock_lot_dataframe(product: str, process: str, months: int = 6) -> pd.DataFrame:
    """Generate lot-granular mock data (multiple lots per week) for Dashboard/Explore.

    Deterministic per (product, process, months). Columns superset COMMON_COLUMNS
    with an added 'lot_date' (ISO string). The newest lot of each series gets a
    deliberate yield dip + bin spike so anomaly detection is exercised in mock mode.
    """
    random.seed(hash(f"lot-{product}-{process}-{months}") % 2**32)
    base_yield = _BASE_YIELD.get(process, 95.0)
    bin_codes = _BIN_CODES_BY_PROCESS.get(process, [3, 5, 7])

    today = date.today()
    start = today - timedelta(days=months * 30)

    rows: list[dict] = []
    seq = 0
    cur = start
    all_dates: list[date] = []
    while cur <= today:
        # 1–3 lots in this week
        for _ in range(random.randint(1, 3)):
            all_dates.append(cur)
        cur += timedelta(weeks=1)

    for i, lot_date in enumerate(all_dates):
        seq += 1
        is_latest = i == len(all_dates) - 1
        wafer_yield = round(base_yield + random.uniform(-2, 2), 2)
        if is_latest:
            wafer_yield = round(base_yield - 6.0, 2)  # force a yield_drop
        lot_id = f"{product[:4].upper()}-{lot_date.strftime('%Y%m%d')}-{seq:03d}"
        for wafer_id in range(1, random.randint(3, 6)):
            gross_die = random.randint(800, 1200)
            for bin_code in bin_codes:
                rate = random.uniform(0.001, 0.012)
                if is_latest and bin_code == bin_codes[0]:
                    rate *= 4.0  # force a bin_surge on the first bin
                fail_count = max(0, int(gross_die * rate))
                rows.append({
                    "lot_id": lot_id,
                    "lot_date": lot_date.isoformat(),
                    "wafer_id": wafer_id,
                    "yield_pct": wafer_yield,
                    "gross_die": gross_die,
                    "raw_bin_code": bin_code,
                    "bin_name": _BIN_NAMES.get(bin_code, f"Bin{bin_code}"),
                    "bin_fail_count": fail_count,
                })

    columns = COMMON_COLUMNS + ["lot_date"]
    return pd.DataFrame(rows, columns=columns)
```

- [ ] **Step 4: Run test — verify pass**

Run: `uv run pytest tests/test_mock_lots.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/mock_data.py backend/tests/test_mock_lots.py
git commit -m "feat(mock): add lot-granular mock dataframe with seeded anomalies"
```

---

### Task B3: Real lot query (lot_queries.py)

**Files:**
- Create: `backend/app/services/lot_queries.py`
- Create: `backend/tests/test_lot_queries.py`

Reuses the existing `_PROCESS_SPEC` (table names, join keys, fail-bin filter) from `yield_queries.py` but selects the real lot column instead of the ISO-week derivation. No DB is hit in tests — only the SQL-building helper is unit-tested.

- [ ] **Step 1: Write failing test for the lot-column mapping + SQL builder**

Create `backend/tests/test_lot_queries.py`:

```python
from app.services.lot_queries import lot_column_for, build_lot_query


def test_lot_column_for_cp_and_ft():
    assert lot_column_for("CP") == "SUBSTRATE_ID"
    assert lot_column_for("FT") == "ASSY_LOT_ID"
    assert lot_column_for("SLT") == "ASSY_LOT_ID"


def test_build_lot_query_selects_real_lot_column():
    sql, binds = build_lot_query(
        process="FT", product_ids=["Q67890-A"],
        start_month="2025-12", end_month="2026-05", process_values=None,
    )
    assert "ASSY_LOT_ID" in sql
    assert "AS lot_id" in sql
    assert "AS lot_date" in sql
    assert 'IYYY"W"IW' not in sql            # NOT week-aggregated
    assert binds["start_month"] == "2025-12"


def test_build_lot_query_unknown_process_returns_empty_sql():
    sql, binds = build_lot_query("XX", ["x"], "2025-12", "2026-05", None)
    assert sql == ""
```

- [ ] **Step 2: Run test — verify it fails**

Run: `uv run pytest tests/test_lot_queries.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement lot_queries.py**

Create `backend/app/services/lot_queries.py`:

```python
import logging

import pandas as pd

from app.database import get_connection, release_connection
from app.services.yield_queries import COMMON_COLUMNS, build_product_id_where, _PROCESS_SPEC

logger = logging.getLogger(__name__)

LOT_COLUMNS = COMMON_COLUMNS + ["lot_date"]

# Real per-lot identifier column by process (vs. yield_queries' ISO-week rollup).
_LOT_COLUMN: dict[str, str] = {
    "CP": "SUBSTRATE_ID",
    "FT": "ASSY_LOT_ID",
    "SLT": "ASSY_LOT_ID",
}


def lot_column_for(process: str) -> str | None:
    return _LOT_COLUMN.get(process.upper())


def build_lot_query(
    process: str,
    product_ids: list[str],
    start_month: str,
    end_month: str,
    process_values: list[str] | None,
) -> tuple[str, dict]:
    """Build the lot-granular SQL and bind dict. Returns ("", {}) for unknown process."""
    spec = _PROCESS_SPEC.get(process.upper())
    lot_col = lot_column_for(process)
    if spec is None or lot_col is None:
        return "", {}

    pid_where, pid_binds = build_product_id_where(product_ids)
    join_clause = " AND ".join(f"h.{k} = b.{k}" for k in spec["join_keys"])

    pv_list = process_values or [process]
    pv_names = [f"pv{i}" for i in range(len(pv_list))]
    pv_binds = dict(zip(pv_names, pv_list))
    process_where = f"h.PROCESS IN ({', '.join(f':{n}' for n in pv_names)})"

    date_col = spec["date_col"]
    sql = f"""
        SELECT
            h.{lot_col}                                    AS lot_id,
            TO_CHAR(MIN(h.{date_col}) OVER (PARTITION BY h.{lot_col}),
                    'YYYY-MM-DD')                          AS lot_date,
            h.WAFER_ID                                     AS wafer_id,
            CASE WHEN h.EFFECTIVE_NUM > 0
                 THEN ROUND(h.PASS_CHIP / h.EFFECTIVE_NUM * 100, 3)
                 ELSE 0 END                                AS yield_pct,
            h.EFFECTIVE_NUM                                AS gross_die,
            b.BIN_CODE                                     AS raw_bin_code,
            b.BIN_NAME                                     AS bin_name,
            b.BIN_COUNT                                    AS bin_fail_count
        FROM {spec['header']} h
        {spec['join_type']} {spec['bin_sum']} b
          ON {join_clause}
        WHERE {pid_where}
          AND {process_where}
          AND h.REWORK_NEW = 0
          AND h.{date_col} >= TO_DATE(:start_month || '-01', 'YYYY-MM-DD')
          AND h.{date_col}  < ADD_MONTHS(TO_DATE(:end_month || '-01', 'YYYY-MM-DD'), 1)
          AND UPPER(TRIM(COALESCE(b.BIN_QUALITY, ''))) <> 'PASS'
          AND UPPER(TRIM(COALESCE(b.BIN_NAME,    ''))) NOT IN ('PASS', 'PASSED', 'OK', 'GOOD')
        ORDER BY lot_date, lot_id, h.WAFER_ID
    """
    binds = {**pid_binds, **pv_binds, "start_month": start_month, "end_month": end_month}
    return sql, binds


def query_lot_data(
    process: str,
    product_ids: list[str],
    start_month: str,
    end_month: str,
    process_values: list[str] | None = None,
) -> pd.DataFrame:
    """Execute the lot-granular query and return a DataFrame (empty for unknown process)."""
    sql, binds = build_lot_query(process, product_ids, start_month, end_month, process_values)
    if not sql:
        return pd.DataFrame(columns=LOT_COLUMNS)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, binds)
        rows = cursor.fetchall()
        logger.info("Lot query returned %d rows (process=%s)", len(rows), process)
        return pd.DataFrame(rows, columns=LOT_COLUMNS)
    finally:
        release_connection(conn)
```

> Note: `_PROCESS_SPEC` is imported from `yield_queries` (read-only reuse — that file is not modified).

- [ ] **Step 4: Run test — verify pass**

Run: `uv run pytest tests/test_lot_queries.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/lot_queries.py backend/tests/test_lot_queries.py
git commit -m "feat(lot): add lot-granular SQL builder reusing process spec"
```

---

### Task B4: lot_service — aggregate wafers → lots + breakdown + warnings

**Files:**
- Create: `backend/app/services/lot_service.py`
- Create: `backend/tests/test_lot_service.py`

- [ ] **Step 1: Write failing tests (mock mode)**

Create `backend/tests/test_lot_service.py`:

```python
from app.services.lot_service import get_lots, period_months


def test_period_months_returns_start_end():
    start, end = period_months(6)
    assert len(start) == 7 and start[4] == "-"   # "YYYY-MM"
    assert len(end) == 7


def test_get_lots_returns_sorted_lotdata():
    lots = get_lots("Product-A", "CP", months=6)
    assert len(lots) > 1
    # ascending by date
    dates = [l.lot_date for l in lots]
    assert dates == sorted(dates)
    latest = lots[-1]
    assert latest.wafer_count >= 1
    assert 0 <= latest.yield_pct <= 100
    assert latest.bin_breakdown  # non-empty


def test_get_lots_attaches_warnings_to_latest_only():
    lots = get_lots("Product-A", "CP", months=6)
    # mock seeds a dip + bin spike on the newest lot
    assert lots[-1].warnings
    assert all(not l.warnings for l in lots[:-1])


def test_get_lots_unknown_process_returns_empty():
    assert get_lots("Product-A", "ZZ", months=6) == []
```

- [ ] **Step 2: Run test — verify it fails**

Run: `uv run pytest tests/test_lot_service.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement lot_service.py**

Create `backend/app/services/lot_service.py`:

```python
import logging
from datetime import date, timedelta

import pandas as pd

from app.config import settings
from app.models.schemas import BinBreakdown, LotData, Warning
from app.services.anomaly_service import evaluate, load_anomaly_config, resolve_config
from app.services.bin_mapping import apply_bin_groups
from app.services.lot_queries import LOT_COLUMNS, query_lot_data
from app.services.mock_data import mock_lot_dataframe
from app.services.product_config import (
    resolve_bin_group,
    resolve_process_filter,
    resolve_product_ids,
)

logger = logging.getLogger(__name__)

SUPPORTED_PROCESSES = {"CP", "FT", "SLT"}


def period_months(months: int) -> tuple[str, str]:
    """Return (start_month, end_month) as 'YYYY-MM' spanning the last `months` months."""
    today = date.today()
    end = f"{today.year:04d}-{today.month:02d}"
    start_date = today - timedelta(days=months * 30)
    start = f"{start_date.year:04d}-{start_date.month:02d}"
    return start, end


def _load_dataframe(nickname: str, process: str, months: int) -> pd.DataFrame:
    if process.upper() not in SUPPORTED_PROCESSES:
        return pd.DataFrame(columns=LOT_COLUMNS)
    if settings.USE_MOCK_DATA:
        return mock_lot_dataframe(nickname, process.upper(), months)
    product_ids = resolve_product_ids(nickname, process)
    if not product_ids:
        return pd.DataFrame(columns=LOT_COLUMNS)
    start, end = period_months(months)
    process_values = resolve_process_filter(nickname, process)
    return query_lot_data(process, product_ids, start, end, process_values)


def _aggregate(df: pd.DataFrame, bin_group: str, process: str) -> list[LotData]:
    if df.empty:
        return []
    df = apply_bin_groups(df, bin_group, process)  # adds 'bin_code' = group name

    lots: list[LotData] = []
    # preserve date order; group by lot_id keeping first-seen order
    for lot_id, g in df.groupby("lot_id", sort=False):
        wafer_count = int(g["wafer_id"].nunique())
        # one yield per wafer → average across wafers
        lot_yield = round(float(g.groupby("wafer_id")["yield_pct"].first().mean()), 2)
        total_gross = float(g.groupby("wafer_id")["gross_die"].first().sum())

        breakdown: list[BinBreakdown] = []
        for bin_name, bg in g.groupby("bin_code", sort=False):
            count = int(bg["bin_fail_count"].sum())
            percent = round(count / total_gross * 100, 3) if total_gross else 0.0
            raw_codes = sorted({int(c) for c in bg["raw_bin_code"].tolist()})
            breakdown.append(BinBreakdown(
                bin_name=str(bin_name), bin_codes=raw_codes,
                count=count, percent=percent,
            ))
        lots.append(LotData(
            lot_id=str(lot_id),
            lot_date=str(g["lot_date"].iloc[0]),
            wafer_count=wafer_count,
            yield_pct=lot_yield,
            bin_breakdown=breakdown,
            warnings=[],
        ))

    lots.sort(key=lambda l: (l.lot_date, l.lot_id))
    return lots


def get_lots(nickname: str, process: str, months: int = 6) -> list[LotData]:
    """Return lot-granular data for a product+process, oldest→newest, with
    anomaly warnings attached to the latest lot."""
    df = _load_dataframe(nickname, process, months)
    bin_group = resolve_bin_group(nickname, process)
    lots = _aggregate(df, bin_group, process)
    if lots:
        cfg = resolve_config(nickname, load_anomaly_config())
        warns = evaluate(lots, cfg)
        lots[-1].warnings = [Warning(**w) for w in warns]
    return lots
```

- [ ] **Step 4: Run test — verify pass**

Run: `uv run pytest tests/test_lot_service.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/lot_service.py backend/tests/test_lot_service.py
git commit -m "feat(lot): aggregate wafers to lots with bin breakdown and warnings"
```

---

### Task B5: summary_service — build dashboard rows

**Files:**
- Create: `backend/app/services/summary_service.py`
- Create: `backend/tests/test_summary_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_summary_service.py`:

```python
from app.services.summary_service import build_summary


def test_build_summary_returns_rows_for_all_products():
    resp = build_summary(months=6, process="all")
    assert resp["period"]["months"] == 6
    assert resp["rows"]
    sample = resp["rows"][0]
    for key in ["nickname", "display_name", "process", "latest_yield",
                "avg_yield_6m", "delta", "sparkline", "warnings"]:
        assert key in sample


def test_build_summary_filters_by_process():
    resp = build_summary(months=6, process="CP")
    assert all(r["process"] == "CP" for r in resp["rows"])


def test_build_summary_computes_delta_and_sparkline():
    resp = build_summary(months=6, process="CP")
    row = resp["rows"][0]
    assert row["delta"] == round(row["latest_yield"] - row["avg_yield_6m"], 2)
    assert len(row["sparkline"]) >= 1
```

- [ ] **Step 2: Run test — verify it fails**

Run: `uv run pytest tests/test_summary_service.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement summary_service.py**

Create `backend/app/services/summary_service.py`:

```python
import logging
from datetime import datetime, timezone

from app.models.schemas import DashboardSummaryResponse, SparkPoint, SummaryRow
from app.services.lot_service import SUPPORTED_PROCESSES, get_lots, period_months
from app.services.product_config import load_product_config, resolve_display_name
from app.services.yield_service import get_products

logger = logging.getLogger(__name__)


def _target_processes(process: str) -> list[str]:
    if process.lower() == "all":
        return ["CP", "FT"]            # SLT shares FT tables; CP+FT cover the dashboard
    p = process.upper()
    return [p] if p in SUPPORTED_PROCESSES else []


def _build_row(nickname: str, process: str, months: int) -> SummaryRow | None:
    lots = get_lots(nickname, process, months)
    if not lots:
        return None
    latest = lots[-1]
    yields = [l.yield_pct for l in lots]
    avg = round(sum(yields) / len(yields), 2)
    return SummaryRow(
        nickname=nickname,
        display_name=resolve_display_name(nickname),
        process=process,
        latest_yield=latest.yield_pct,
        latest_lot_id=latest.lot_id,
        latest_lot_date=latest.lot_date,
        avg_yield_6m=avg,
        delta=round(latest.yield_pct - avg, 2),
        sparkline=[SparkPoint(lot_id=l.lot_id, lot_date=l.lot_date, yield_pct=l.yield_pct)
                   for l in lots],
        warnings=latest.warnings,
    )


def build_summary(months: int = 6, process: str = "all") -> dict:
    """Build the dashboard summary for every configured product × target process."""
    start, end = period_months(months)
    nicknames = get_products()
    processes = _target_processes(process)

    rows: list[SummaryRow] = []
    for nickname in nicknames:
        for proc in processes:
            row = _build_row(nickname, proc, months)
            if row is not None:
                rows.append(row)

    resp = DashboardSummaryResponse(
        generated_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        period={"months": months, "start": start, "end": end},
        rows=rows,
    )
    return resp.model_dump()
```

> `load_product_config` is imported for parity with other services but `get_products()` already returns the nickname list (config keys in mock+real). If lint flags the unused import, remove it.

- [ ] **Step 4: Run test — verify pass**

Run: `uv run pytest tests/test_summary_service.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/summary_service.py backend/tests/test_summary_service.py
git commit -m "feat(summary): build dashboard rows from lot data"
```

---

# Phase C — Backend: routers + wiring

### Task C1: Three routers

**Files:**
- Create: `backend/app/routers/dashboard.py`
- Create: `backend/app/routers/explore.py`
- Create: `backend/app/routers/anomaly_config.py`

- [ ] **Step 1: Implement dashboard router**

Create `backend/app/routers/dashboard.py`:

```python
from fastapi import APIRouter, Query

from app.services.summary_service import build_summary

router = APIRouter()


@router.get("/dashboard/summary")
def dashboard_summary(
    months: int = Query(6, ge=1, le=24),
    process: str = Query("all"),
) -> dict:
    return build_summary(months=months, process=process)
```

- [ ] **Step 2: Implement explore router**

Create `backend/app/routers/explore.py`:

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.models.schemas import ExploreLotsResponse
from app.services.lot_service import get_lots, period_months

router = APIRouter()


@router.get("/explore/lots", response_model=ExploreLotsResponse)
def explore_lots(
    nickname: str = Query(...),
    process: str = Query(...),
    months: int = Query(6, ge=1, le=24),
) -> ExploreLotsResponse:
    lots = get_lots(nickname, process, months)
    start, end = period_months(months)
    available: list[str] = []
    for lot in lots:
        for b in lot.bin_breakdown:
            if b.bin_name not in available:
                available.append(b.bin_name)
    return ExploreLotsResponse(
        nickname=nickname,
        process=process,
        period={"months": months, "start": start, "end": end},
        lots=lots,
        available_bins=available,
    )
```

- [ ] **Step 3: Implement anomaly_config router**

Create `backend/app/routers/anomaly_config.py`:

```python
from fastapi import APIRouter

from app.services.anomaly_service import load_anomaly_config

router = APIRouter()


@router.get("/anomaly/config")
def anomaly_config() -> dict:
    return load_anomaly_config()
```

- [ ] **Step 4: Commit (wired + tested in C2)**

```bash
git add backend/app/routers/dashboard.py backend/app/routers/explore.py backend/app/routers/anomaly_config.py
git commit -m "feat(api): add dashboard, explore, anomaly_config routers"
```

---

### Task C2: Register routers + endpoint tests

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api_endpoints.py`

- [ ] **Step 1: Write failing endpoint tests**

Create `backend/tests/test_api_endpoints.py`:

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_dashboard_summary_endpoint():
    r = client.get("/api/dashboard/summary?months=6&process=CP")
    assert r.status_code == 200
    body = r.json()
    assert body["period"]["months"] == 6
    assert isinstance(body["rows"], list) and body["rows"]
    assert all(row["process"] == "CP" for row in body["rows"])


def test_explore_lots_endpoint():
    r = client.get("/api/explore/lots?nickname=Product-A&process=CP&months=6")
    assert r.status_code == 200
    body = r.json()
    assert body["nickname"] == "Product-A"
    assert body["lots"]
    assert "available_bins" in body
    assert "yield_pct" in body["lots"][0]


def test_anomaly_config_endpoint():
    r = client.get("/api/anomaly/config")
    assert r.status_code == 200
    body = r.json()
    assert "defaults" in body and "yield_drop" in body["defaults"]


def test_existing_yield_data_endpoint_unchanged():
    # guard: the existing Report endpoint still works
    r = client.post("/api/yield-data", json={
        "products": ["Product-A"], "start_month": "2026-01",
        "end_month": "2026-05", "processes": ["CP"],
    })
    assert r.status_code == 200
    assert "data" in r.json()
```

- [ ] **Step 2: Run test — verify it fails**

Run: `uv run pytest tests/test_api_endpoints.py -v`
Expected: FAIL — the three new routes return 404 (not yet registered).

- [ ] **Step 3: Register the routers**

In `backend/app/main.py`, change the import line:

```python
from app.routers import export, yield_data
```

to:

```python
from app.routers import anomaly_config, dashboard, explore, export, yield_data
```

And after the existing `app.include_router(export.router, prefix="/api")` line, add:

```python
app.include_router(dashboard.router, prefix="/api")
app.include_router(explore.router, prefix="/api")
app.include_router(anomaly_config.router, prefix="/api")
```

- [ ] **Step 4: Run test — verify pass**

Run: `uv run pytest tests/test_api_endpoints.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run the full backend suite**

Run: `uv run pytest -q`
Expected: all tests pass (Phases A–C).

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_api_endpoints.py
git commit -m "feat(api): register dashboard/explore/anomaly routers with endpoint tests"
```

---

# Phase D — Frontend: routing shell + Report move

### Task D1: Install react-router-dom

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install**

Run: `cd frontend && npm install react-router-dom`
Expected: `react-router-dom` added to dependencies.

- [ ] **Step 2: Verify build still works**

Run: `cd frontend && npm run build`
Expected: build succeeds (no usage yet).

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "build: add react-router-dom"
```

---

### Task D2: Add new frontend types

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Append types**

Append to `frontend/src/types/index.ts`:

```typescript
// ---- Dashboard / Explore types ----

export interface Warning {
  type: string;            // "yield_drop" | "bin_surge"
  message: string;
  severity: string;
  bin_code?: number | null;
}

export interface SparkPoint {
  lot_id: string;
  lot_date: string;
  yield_pct: number;
}

export interface SummaryRow {
  nickname: string;
  display_name: string;
  process: string;
  latest_yield: number | null;
  latest_lot_id: string | null;
  latest_lot_date: string | null;
  avg_yield_6m: number | null;
  delta: number | null;
  sparkline: SparkPoint[];
  warnings: Warning[];
}

export interface DashboardSummaryResponse {
  generated_at: string;
  period: { months: number; start: string; end: string };
  rows: SummaryRow[];
}

export interface BinBreakdown {
  bin_name: string;
  bin_codes: number[];
  count: number;
  percent: number;
}

export interface LotData {
  lot_id: string;
  lot_date: string;
  wafer_count: number;
  yield_pct: number;
  bin_breakdown: BinBreakdown[];
  warnings: Warning[];
}

export interface ExploreLotsResponse {
  nickname: string;
  process: string;
  period: { months: number; start: string; end: string };
  lots: LotData[];
  available_bins: string[];
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): add dashboard and explore response types"
```

---

### Task D3: API client functions

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Append fetchers**

Append to `frontend/src/api/client.ts` (the file already imports `axios`/`api`; add the type import at top and functions at bottom):

At the top, extend the existing type import:

```typescript
import type {
  YieldRequest, YieldResponse,
  DashboardSummaryResponse, ExploreLotsResponse,
} from "../types";
```

At the bottom, add:

```typescript
export async function fetchDashboardSummary(
  months = 6, process = "all"
): Promise<DashboardSummaryResponse> {
  const res = await api.get<DashboardSummaryResponse>("/dashboard/summary", {
    params: { months, process },
  });
  return res.data;
}

export async function fetchExploreLots(
  nickname: string, process: string, months = 6
): Promise<ExploreLotsResponse> {
  const res = await api.get<ExploreLotsResponse>("/explore/lots", {
    params: { nickname, process, months },
  });
  return res.data;
}

export async function fetchAnomalyConfig(): Promise<Record<string, unknown>> {
  const res = await api.get<Record<string, unknown>>("/anomaly/config");
  return res.data;
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(api-client): add dashboard/explore/anomaly fetchers"
```

---

### Task D4: ReportPage (move existing App logic verbatim)

**Files:**
- Create: `frontend/src/pages/ReportPage.tsx`

The current `App.tsx` body (state + Sidebar + ReportView + ErrorBanner) moves here unchanged in behavior. App.tsx becomes the router shell in D6.

- [ ] **Step 1: Create ReportPage with the existing logic**

Create `frontend/src/pages/ReportPage.tsx`:

```tsx
import { useState } from "react";
import Sidebar from "../components/Sidebar";
import ReportView from "../components/ReportView";
import ErrorBanner from "../components/ErrorBanner";
import { fetchYieldData } from "../api/client";
import type { YieldRequest, YieldResponse } from "../types";

export default function ReportPage() {
  const [data, setData] = useState<YieldResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [currentRequest, setCurrentRequest] = useState<YieldRequest | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async (req: YieldRequest) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchYieldData(req);
      setData(res);
      setCurrentRequest(req);
    } catch (err) {
      console.error("Failed to fetch yield data:", err);
      setError("データ取得に失敗しました。バックエンドが起動しているか確認してください。");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flex: 1, minWidth: 0 }}>
      <Sidebar onGenerate={handleGenerate} loading={loading} canPrint={data !== null} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
        <ReportView data={data} request={currentRequest} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: no errors (ReportPage not yet routed but compiles).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ReportPage.tsx
git commit -m "refactor(report): move App report logic into ReportPage (behavior unchanged)"
```

---

### Task D5: TopNav

**Files:**
- Create: `frontend/src/components/TopNav.tsx`

- [ ] **Step 1: Create TopNav**

Create `frontend/src/components/TopNav.tsx`:

```tsx
import { NavLink } from "react-router-dom";

const tabs = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/report", label: "Report" },
];

export default function TopNav() {
  return (
    <nav style={styles.nav}>
      <span style={styles.brand}>Yield</span>
      {tabs.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          style={({ isActive }) => ({
            ...styles.link,
            ...(isActive ? styles.linkActive : {}),
          })}
        >
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}

const styles: Record<string, React.CSSProperties> = {
  nav: {
    display: "flex",
    alignItems: "center",
    gap: 4,
    padding: "0 20px",
    height: 48,
    background: "var(--white)",
    borderBottom: "var(--border-whisper)",
    flexShrink: 0,
  },
  brand: { fontWeight: 700, marginRight: 20, color: "var(--gray-700)" },
  link: {
    padding: "8px 14px",
    borderRadius: 8,
    textDecoration: "none",
    color: "var(--gray-500)",
    fontSize: 14,
    fontWeight: 500,
  },
  linkActive: { background: "var(--badge-bg)", color: "var(--badge-text)" },
};
```

> Note: Explore is reached by clicking a Dashboard row, so it intentionally has no top-nav tab.

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TopNav.tsx
git commit -m "feat(nav): add TopNav with Dashboard/Report tabs"
```

---

### Task D6: App.tsx becomes router shell

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Replace App.tsx**

Replace the entire contents of `frontend/src/App.tsx` with:

```tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import TopNav from "./components/TopNav";
import ReportPage from "./pages/ReportPage";
import DashboardPage from "./pages/DashboardPage";
import ExplorePage from "./pages/ExplorePage";

export default function App() {
  return (
    <BrowserRouter>
      <div style={styles.app}>
        <TopNav />
        <div style={styles.body}>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/report" element={<ReportPage />} />
            <Route path="/explore/:nickname/:process" element={<ExplorePage />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}

const styles: Record<string, React.CSSProperties> = {
  app: {
    display: "flex",
    flexDirection: "column",
    minHeight: "100vh",
    background: "var(--warm-white)",
    fontFamily: "var(--font-sans)",
    color: "var(--gray-700)",
  },
  body: { display: "flex", flex: 1, minWidth: 0 },
};
```

> DashboardPage and ExplorePage are created in Phase E/F. Until then, build will fail on the missing imports — that is expected; D6 is committed together with E1/F1. To keep D6 independently compilable, create the two pages as stubs in Step 2 below first.

- [ ] **Step 2: Create temporary page stubs so the app compiles**

Create `frontend/src/pages/DashboardPage.tsx`:

```tsx
export default function DashboardPage() {
  return <div style={{ padding: 40 }}>Dashboard (coming soon)</div>;
}
```

Create `frontend/src/pages/ExplorePage.tsx`:

```tsx
export default function ExplorePage() {
  return <div style={{ padding: 40 }}>Explore (coming soon)</div>;
}
```

- [ ] **Step 3: Build + manual smoke test**

Run: `cd frontend && npm run build`
Expected: build succeeds.

Then from `backend/`: `uv run uvicorn app.main:app --port 8000` and open `http://localhost:8000`. Verify: redirect to `/dashboard`, TopNav shows Dashboard/Report, clicking **Report** shows the existing report UI and Generate Report still works (and PDF export still works).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/pages/DashboardPage.tsx frontend/src/pages/ExplorePage.tsx
git commit -m "feat(routing): convert App to router shell with page stubs"
```

---

# Phase E — Frontend: Dashboard page

### Task E1: Sparkline component

**Files:**
- Create: `frontend/src/components/dashboard/Sparkline.tsx`

- [ ] **Step 1: Create Sparkline**

Create `frontend/src/components/dashboard/Sparkline.tsx`:

```tsx
interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  color?: string;
}

export default function Sparkline({
  values, width = 90, height = 22, color = "#3a7bbf",
}: SparklineProps) {
  if (values.length < 2) {
    return <svg width={width} height={height} />;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const stepX = width / (values.length - 1);
  const points = values
    .map((v, i) => {
      const x = i * stepX;
      const y = height - ((v - min) / span) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg width={width} height={height} aria-hidden>
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/dashboard/Sparkline.tsx
git commit -m "feat(dashboard): add inline SVG Sparkline"
```

---

### Task E2: SummaryTable component

**Files:**
- Create: `frontend/src/components/dashboard/SummaryTable.tsx`

- [ ] **Step 1: Create SummaryTable**

Create `frontend/src/components/dashboard/SummaryTable.tsx`:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { SummaryRow } from "../../types";
import Sparkline from "./Sparkline";

type SortKey = "display_name" | "process" | "latest_yield" | "avg_yield_6m" | "delta";

interface Props {
  rows: SummaryRow[];
}

export default function SummaryTable({ rows }: Props) {
  const navigate = useNavigate();
  const [sortKey, setSortKey] = useState<SortKey>("delta");
  const [asc, setAsc] = useState(true);

  const sorted = [...rows].sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    if (av == null) return 1;
    if (bv == null) return -1;
    if (av < bv) return asc ? -1 : 1;
    if (av > bv) return asc ? 1 : -1;
    return 0;
  });

  const toggleSort = (k: SortKey) => {
    if (k === sortKey) setAsc(!asc);
    else { setSortKey(k); setAsc(true); }
  };

  const fmt = (n: number | null, suffix = "") =>
    n == null ? "—" : `${n.toFixed(1)}${suffix}`;

  return (
    <table style={styles.table}>
      <thead>
        <tr>
          <th style={styles.thLeft} onClick={() => toggleSort("display_name")}>製品 / Proc</th>
          <th style={styles.th} onClick={() => toggleSort("latest_yield")}>直近歩留</th>
          <th style={styles.th} onClick={() => toggleSort("avg_yield_6m")}>6m平均</th>
          <th style={styles.th} onClick={() => toggleSort("delta")}>差分</th>
          <th style={styles.th}>トレンド</th>
          <th style={styles.thLeft}>要注意</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((r) => {
          const warn = r.warnings.length > 0;
          const deltaColor = r.delta == null ? "#888" : r.delta < 0 ? "#b13a2a" : "#2f8a3e";
          return (
            <tr
              key={`${r.nickname}-${r.process}`}
              style={{ ...styles.tr, ...(warn ? styles.trWarn : {}) }}
              onClick={() => navigate(`/explore/${encodeURIComponent(r.nickname)}/${r.process}`)}
            >
              <td style={styles.tdLeft}>
                <b>{r.display_name}</b> <span style={styles.proc}>/ {r.process}</span>
              </td>
              <td style={styles.td}>{fmt(r.latest_yield, "%")}</td>
              <td style={styles.td}>{fmt(r.avg_yield_6m, "%")}</td>
              <td style={{ ...styles.td, color: deltaColor }}>
                {r.delta == null ? "—" : `${r.delta < 0 ? "▼" : "▲"} ${Math.abs(r.delta).toFixed(1)}`}
              </td>
              <td style={styles.td}>
                <Sparkline
                  values={r.sparkline.map((p) => p.yield_pct)}
                  color={warn ? "#b13a2a" : "#3a7bbf"}
                />
              </td>
              <td style={styles.tdLeft}>
                {r.warnings.map((w, i) => (
                  <span key={i} style={styles.badge}>⚠ {w.message}</span>
                ))}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

const styles: Record<string, React.CSSProperties> = {
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: { textAlign: "right", padding: "8px 12px", background: "#f3efe4", cursor: "pointer", color: "#5a5547", fontWeight: 600, borderBottom: "1px solid #e6e1d4" },
  thLeft: { textAlign: "left", padding: "8px 12px", background: "#f3efe4", cursor: "pointer", color: "#5a5547", fontWeight: 600, borderBottom: "1px solid #e6e1d4" },
  tr: { cursor: "pointer", borderBottom: "1px solid #eee" },
  trWarn: { background: "#fff8e6" },
  td: { textAlign: "right", padding: "8px 12px" },
  tdLeft: { textAlign: "left", padding: "8px 12px" },
  proc: { color: "#888" },
  badge: { display: "inline-block", background: "#fff2d6", color: "#a06800", fontSize: 11, padding: "1px 6px", borderRadius: 10, marginRight: 4 },
};
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/dashboard/SummaryTable.tsx
git commit -m "feat(dashboard): add sortable SummaryTable with warning highlight"
```

---

### Task E3: DashboardPage (replace stub)

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`

- [ ] **Step 1: Replace stub with real page**

Replace the contents of `frontend/src/pages/DashboardPage.tsx` with:

```tsx
import { useEffect, useState, useCallback } from "react";
import { fetchDashboardSummary } from "../api/client";
import type { DashboardSummaryResponse } from "../types";
import SummaryTable from "../components/dashboard/SummaryTable";

export default function DashboardPage() {
  const [months, setMonths] = useState(6);
  const [process, setProcess] = useState("all");
  const [data, setData] = useState<DashboardSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchDashboardSummary(months, process));
    } catch (e) {
      console.error(e);
      setError("ダッシュボードデータの取得に失敗しました。");
    } finally {
      setLoading(false);
    }
  }, [months, process]);

  useEffect(() => { load(); }, [load]);

  return (
    <main style={{ flex: 1, padding: "28px 40px", overflowY: "auto" }}>
      <div style={styles.toolbar}>
        <label>期間:
          <select value={months} onChange={(e) => setMonths(Number(e.target.value))} style={styles.select}>
            <option value={3}>過去3ヶ月</option>
            <option value={6}>過去6ヶ月</option>
            <option value={12}>過去12ヶ月</option>
          </select>
        </label>
        <label>プロセス:
          <select value={process} onChange={(e) => setProcess(e.target.value)} style={styles.select}>
            <option value="all">All</option>
            <option value="CP">CP</option>
            <option value="FT">FT</option>
          </select>
        </label>
        <button onClick={load} disabled={loading} style={styles.refresh}>
          {loading ? "更新中…" : "🔄 更新"}
        </button>
        {data && <span style={styles.updated}>最終更新: {new Date(data.generated_at).toLocaleString()}</span>}
      </div>

      {error && <div style={styles.error}>{error}</div>}
      {data && <SummaryTable rows={data.rows} />}
      {data && data.rows.length === 0 && !loading && <p>データがありません。</p>}
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  toolbar: { display: "flex", alignItems: "center", gap: 16, marginBottom: 20, flexWrap: "wrap" },
  select: { marginLeft: 6, padding: "4px 8px" },
  refresh: { padding: "6px 14px", cursor: "pointer", borderRadius: 8, border: "1px solid #d8d4c8", background: "#fff" },
  updated: { fontSize: 12, color: "#888", marginLeft: "auto" },
  error: { background: "#fdecea", color: "#b13a2a", padding: "10px 14px", borderRadius: 8, marginBottom: 16 },
};
```

- [ ] **Step 2: Build + manual smoke test**

Run: `cd frontend && npm run build`
Expected: build succeeds.

Restart backend, open `http://localhost:8000/dashboard`. Verify: table loads, at least one row has a ⚠ badge + highlighted row (mock seeds anomalies), changing 期間/プロセス + 🔄更新 refetches, sorting by clicking headers works, clicking a row navigates to `/explore/...` (stub page for now).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/DashboardPage.tsx
git commit -m "feat(dashboard): wire DashboardPage with summary fetch and controls"
```

---

# Phase F — Frontend: Explore page

### Task F1: formatLotId utility

**Files:**
- Create: `frontend/src/utils/formatLotId.ts`

- [ ] **Step 1: Create utility**

Create `frontend/src/utils/formatLotId.ts`:

```typescript
export type LotIdFormat = "raw" | "date" | "yearweek";

const STORAGE_KEY = "dashboard.lotIdFormat";

export function getLotIdFormat(): LotIdFormat {
  const v = localStorage.getItem(STORAGE_KEY);
  return v === "date" || v === "yearweek" ? v : "raw";
}

export function setLotIdFormat(mode: LotIdFormat): void {
  localStorage.setItem(STORAGE_KEY, mode);
}

function isoWeek(d: Date): string {
  // ISO week number per ISO-8601
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const day = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  const week = Math.ceil((((date.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  return `${date.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

export function formatLotId(lotId: string, lotDate: string, mode: LotIdFormat): string {
  if (mode === "date") return lotDate;
  if (mode === "yearweek") {
    const d = new Date(lotDate);
    return isNaN(d.getTime()) ? lotId : isoWeek(d);
  }
  return lotId;
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/utils/formatLotId.ts
git commit -m "feat(explore): add lot id display format utility"
```

---

### Task F2: LotTrendChart

**Files:**
- Create: `frontend/src/components/explore/LotTrendChart.tsx`

Uses `react-plotly.js` (already a dependency). Check `PlotlyChart.tsx` for the existing import pattern and match it.

- [ ] **Step 1: Confirm Plotly import pattern**

Run: `cd frontend && sed -n '1,15p' src/components/PlotlyChart.tsx`
Expected: shows how Plotly is imported (e.g. `import Plot from "react-plotly.js"`). Match this exact import in the next step.

- [ ] **Step 2: Create LotTrendChart**

Create `frontend/src/components/explore/LotTrendChart.tsx` (match the Plotly import you saw in Step 1):

```tsx
import Plot from "react-plotly.js";
import type { LotData } from "../../types";
import { formatLotId, type LotIdFormat } from "../../utils/formatLotId";

interface Props {
  lots: LotData[];
  format: LotIdFormat;
}

export default function LotTrendChart({ lots, format }: Props) {
  const x = lots.map((l) => formatLotId(l.lot_id, l.lot_date, format));
  const y = lots.map((l) => l.yield_pct);
  const warnIdx = lots
    .map((l, i) => (l.warnings.length > 0 ? i : -1))
    .filter((i) => i >= 0);

  return (
    <Plot
      data={[
        {
          x, y, type: "scatter", mode: "lines+markers",
          name: "歩留り", line: { color: "#3a7bbf" },
          marker: { size: 6 },
        },
        {
          x: warnIdx.map((i) => x[i]),
          y: warnIdx.map((i) => y[i]),
          type: "scatter", mode: "markers", name: "要注意",
          marker: { size: 12, color: "#b13a2a", symbol: "circle-open", line: { width: 2 } },
        },
      ]}
      layout={{
        height: 320,
        margin: { t: 20, r: 20, b: 60, l: 50 },
        yaxis: { title: "歩留り (%)", range: [0, 102] },
        xaxis: { tickangle: -45 },
        showlegend: true,
      }}
      style={{ width: "100%" }}
      useResizeHandler
      config={{ displayModeBar: false }}
    />
  );
}
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/explore/LotTrendChart.tsx
git commit -m "feat(explore): add lot yield trend chart with warning markers"
```

---

### Task F3: LotTable

**Files:**
- Create: `frontend/src/components/explore/LotTable.tsx`

- [ ] **Step 1: Create LotTable**

Create `frontend/src/components/explore/LotTable.tsx`:

```tsx
import type { LotData } from "../../types";
import { formatLotId, type LotIdFormat } from "../../utils/formatLotId";

interface Props {
  lots: LotData[];
  availableBins: string[];
  format: LotIdFormat;
}

export default function LotTable({ lots, availableBins, format }: Props) {
  const pctFor = (lot: LotData, bin: string) => {
    const b = lot.bin_breakdown.find((x) => x.bin_name === bin);
    return b ? b.percent : 0;
  };
  // newest first for the table
  const rows = [...lots].reverse();

  return (
    <table style={styles.table}>
      <thead>
        <tr>
          <th style={styles.thLeft}>Lot ID</th>
          <th style={styles.th}>日付</th>
          <th style={styles.th}>Wafer数</th>
          <th style={styles.th}>歩留</th>
          {availableBins.map((b) => <th key={b} style={styles.th}>{b}</th>)}
          <th style={styles.thLeft}>⚠</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((lot) => (
          <tr key={lot.lot_id} style={lot.warnings.length ? styles.warn : undefined}>
            <td style={styles.tdLeft}>{formatLotId(lot.lot_id, lot.lot_date, format)}</td>
            <td style={styles.td}>{lot.lot_date}</td>
            <td style={styles.td}>{lot.wafer_count}</td>
            <td style={styles.td}>{lot.yield_pct.toFixed(1)}%</td>
            {availableBins.map((b) => <td key={b} style={styles.td}>{pctFor(lot, b).toFixed(2)}%</td>)}
            <td style={styles.tdLeft}>
              {lot.warnings.map((w, i) => <span key={i} style={styles.badge}>⚠ {w.message}</span>)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const styles: Record<string, React.CSSProperties> = {
  table: { width: "100%", borderCollapse: "collapse", fontSize: 12, marginTop: 20 },
  th: { textAlign: "right", padding: "6px 8px", background: "#f3efe4", borderBottom: "1px solid #e6e1d4", whiteSpace: "nowrap" },
  thLeft: { textAlign: "left", padding: "6px 8px", background: "#f3efe4", borderBottom: "1px solid #e6e1d4" },
  td: { textAlign: "right", padding: "5px 8px", borderBottom: "1px solid #eee" },
  tdLeft: { textAlign: "left", padding: "5px 8px", borderBottom: "1px solid #eee" },
  warn: { background: "#fff8e6" },
  badge: { display: "inline-block", background: "#fff2d6", color: "#a06800", fontSize: 10, padding: "1px 5px", borderRadius: 8, marginRight: 4 },
};
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/explore/LotTable.tsx
git commit -m "feat(explore): add lot table with fail-bin breakdown"
```

---

### Task F4: ExplorePage (replace stub)

**Files:**
- Modify: `frontend/src/pages/ExplorePage.tsx`

- [ ] **Step 1: Replace stub with real page**

Replace the contents of `frontend/src/pages/ExplorePage.tsx` with:

```tsx
import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { fetchExploreLots } from "../api/client";
import type { ExploreLotsResponse } from "../types";
import LotTrendChart from "../components/explore/LotTrendChart";
import LotTable from "../components/explore/LotTable";
import { getLotIdFormat, setLotIdFormat, type LotIdFormat } from "../utils/formatLotId";

export default function ExplorePage() {
  const { nickname = "", process = "" } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<ExploreLotsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [format, setFormat] = useState<LotIdFormat>(getLotIdFormat());

  useEffect(() => {
    let active = true;
    fetchExploreLots(nickname, process, 6)
      .then((d) => { if (active) setData(d); })
      .catch((e) => { console.error(e); if (active) setError("ロットデータの取得に失敗しました。"); });
    return () => { active = false; };
  }, [nickname, process]);

  const changeFormat = (f: LotIdFormat) => { setFormat(f); setLotIdFormat(f); };

  return (
    <main style={{ flex: 1, padding: "28px 40px", overflowY: "auto" }}>
      <div style={styles.header}>
        <button onClick={() => navigate("/dashboard")} style={styles.back}>← Dashboard</button>
        <h2 style={{ margin: 0 }}>{nickname} / {process}</h2>
        <label style={{ marginLeft: "auto", fontSize: 13 }}>
          Lot ID 表示:
          <select value={format} onChange={(e) => changeFormat(e.target.value as LotIdFormat)} style={{ marginLeft: 6 }}>
            <option value="raw">実ロット番号</option>
            <option value="date">日付</option>
            <option value="yearweek">年週</option>
          </select>
        </label>
      </div>

      {error && <div style={styles.error}>{error}</div>}
      {data && data.lots.length === 0 && <p>該当するロットがありません。</p>}
      {data && data.lots.length > 0 && (
        <>
          <LotTrendChart lots={data.lots} format={format} />
          <LotTable lots={data.lots} availableBins={data.available_bins} format={format} />
        </>
      )}
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  header: { display: "flex", alignItems: "center", gap: 16, marginBottom: 16 },
  back: { padding: "6px 12px", cursor: "pointer", borderRadius: 8, border: "1px solid #d8d4c8", background: "#fff" },
  error: { background: "#fdecea", color: "#b13a2a", padding: "10px 14px", borderRadius: 8, marginBottom: 16 },
};
```

- [ ] **Step 2: Build + manual smoke test**

Run: `cd frontend && npm run build`
Expected: build succeeds.

Restart backend, open `http://localhost:8000/dashboard`, click a row. Verify on Explore: trend chart renders with a red open-circle marker on the newest (seeded) lot, lot table lists lots newest-first with per-bin % columns, the Lot ID 表示 dropdown switches the lot label between raw/date/yearweek and persists across reload, ← Dashboard returns.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ExplorePage.tsx
git commit -m "feat(explore): wire ExplorePage with trend chart, lot table, format toggle"
```

---

# Phase G — Verification & finalize

### Task G1: Full verification

- [ ] **Step 1: Backend test suite**

Run: `cd backend && uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 2: Frontend lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: lint clean (fix any unused-import warnings introduced), build succeeds.

- [ ] **Step 3: End-to-end smoke (single server)**

Run from `backend/`: `uv run uvicorn app.main:app --port 8000`
Open `http://localhost:8000` and verify the full flow:
- `/` redirects to `/dashboard`; summary table loads with anomalies highlighted.
- Period/process controls + 🔄更新 refetch.
- Row click → Explore; chart + table render; format toggle persists.
- **Report tab**: Generate Report renders charts; **PDF export downloads a valid PDF** (regression check — the critical invariant).

- [ ] **Step 4: Confirm PDF invariant via git**

Run: `git diff main --stat -- backend/app/services/pdf_service.py backend/app/routers/export.py backend/app/services/yield_service.py backend/app/services/yield_queries.py backend/app/services/yield_aggregator.py`
Expected: **no output** (these files are untouched).

- [ ] **Step 5: Final commit (if any lint fixes were needed)**

```bash
git add -A
git commit -m "chore: lint fixes and final verification for yield dashboard"
```

---

## Self-Review (completed by plan author)

- **Spec coverage:** 3 tabs (D5/D6), Dashboard table 6-month manual refresh (E3), real lot granularity CP=SUBSTRATE_ID/FT=ASSY_LOT_ID (B3), anomaly B+C via YAML (A2/A3), row→Explore drill-down to lots+bin breakdown (F4), lot_id display format on frontend localStorage (F1), PDF/yield-data untouched (G1 step 4 guard). All covered.
- **Placeholder scan:** No TBD/TODO; every code step contains full code. The only intentional "coming soon" stubs (D6) are explicitly replaced in E3/F4.
- **Type consistency:** `yield_pct` used uniformly in backend models, mock columns, services, and frontend types; `LotData`/`BinBreakdown`/`Warning`/`SummaryRow`/`SparkPoint` names match between schemas (B1), services (B4/B5), routers (C1), and TS types (D2). `get_lots`, `period_months`, `build_summary`, `evaluate`, `resolve_config`, `load_anomaly_config` signatures consistent across tasks. `formatLotId`/`LotIdFormat` consistent across F1/F2/F3/F4.
