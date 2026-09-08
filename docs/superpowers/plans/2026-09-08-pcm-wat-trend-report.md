# PCM/WAT トレンドレポート Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PCM/WAT を「ロット単体レポート（既存・無変更）」と「ロット横断トレンドレポート（新規・既定 3 ヶ月）」の 2 本に分ける。

**Architecture:** 期間内の全ロット明細を 1 クエリで取り、生サイト測定値をプールした期間通算統計と、ロット別の系列 (`lot_series`) を返す新サービスを足す。既存の単ロット経路は Cpk 計算などの純関数を共有するだけで、公開 API・出力ともに一切変えない。画面は Report ページの 3 番目のタブ、PDF は A4 縦の新モジュール。

**Tech Stack:** FastAPI / pydantic / pandas / oracledb (thin) / ReportLab + kaleido + plotly / React + TypeScript + Plotly.js / pytest

**Spec:** `docs/superpowers/specs/2026-09-07-pcm-wat-trend-report-design.md`

## Global Constraints

- **`WAT_MEASURE_DETAIL` は `REWORK_NEW` / `DEL_FLAG` でフィルタしない。** この工程は rework 運用がない。SEMI_CP_* 系の `REWORK_NEW = 0` 必須ルールをここに持ち込むと有効な行を落とす（CLAUDE.md）。
- **バインド名に Oracle 予約語を使わない。** `:start` / `:end` は実行時に ORA-01745。必ず `:start_dt` / `:end_dt`。
- **期間の上限は排他（`<`）。** 呼び出し側が翌日を渡して当日分を含める。
- **Cpk のしきい値は `CPK_RED = 1.00` / `CPK_YELLOW = 1.33`、比較は strict less-than。** Cpk ちょうど 1.00 は yellow、ちょうど 1.33 は ok。新しい定数を作らず `wat_service` の既存定数を使う。
- **JSON は Infinity を運べない。** σ=0 かつ規格内は `cpk=None, cpk_state="infinite"`。
- **既存の公開 API を変えない:** `GET /api/wat/lots`、`GET /api/wat/summary`、`POST /api/wat/export-pdf`、`get_wat_lots()`、`get_wat_summary()`、`compute_item_stats()` の入出力は不変。
- **テストは mock モードで動く。** `tests/conftest.py` が `USE_MOCK_DATA=true` を強制する。Oracle は不要。
- バックエンドのコマンドは `backend/` から `uv run pytest ...`、フロントは `frontend/` から `npm run lint` / `npx tsc --noEmit`。

---

## File Structure

**バックエンド（新規）**

| ファイル | 責務 |
|---|---|
| `backend/app/services/wat_trend_service.py` | 期間内明細 → `WatTrendResponse`。ロット横断の集計だけを持つ |
| `backend/app/services/wat_pdf_common.py` | 単ロット PDF とトレンド PDF が共有する部品（色・列定義・数値整形・kaleido 一括描画・テーブル描画） |
| `backend/app/services/wat_trend_pdf_service.py` | トレンド PDF（A4 縦）のレイアウトだけ |

**バックエンド（変更）**

| ファイル | 変更内容 |
|---|---|
| `backend/app/services/wat_queries.py` | `WAT_TREND_COLUMNS` / `build_wat_trend_query()` / `query_wat_trend()` 追加、`_normalize_detail()` 抽出 |
| `backend/app/services/wat_service.py` | `_item_core()` 抽出（出力は不変） |
| `backend/app/services/wat_pdf_service.py` | 共通部品を `wat_pdf_common` から import する形に整理 |
| `backend/app/services/mock_data.py` | `mock_wat_trend_dataframe()` 追加 |
| `backend/app/models/schemas.py` | `WatLotPoint` / `WatTrendItemStats` / `WatTrendResponse` / `WatTrendExportRequest` |
| `backend/app/routers/wat.py` | `GET /wat/trend`、`POST /wat/export-trend-pdf` |

**フロントエンド（新規）**

| ファイル | 責務 |
|---|---|
| `frontend/src/components/wat/WatTrendTab.tsx` | トレンドタブの状態管理とレイアウト |

**フロントエンド（変更）**

| ファイル | 変更内容 |
|---|---|
| `frontend/src/components/wat/WatItemTrendChart.tsx` | ウェハ軸/ロット軸の両方を描ける汎用形に |
| `frontend/src/components/wat/WatSummaryTable.tsx` | ジェネリック化し、展開チャートを `renderChart` prop で受け取る |
| `frontend/src/components/wat/WatSummaryTab.tsx` | 新しい props に合わせて呼び出しを更新（見た目は不変） |
| `frontend/src/pages/ReportPage.tsx` | タブを 3 つに |
| `frontend/src/api/client.ts` | `fetchWatTrend()` / `exportWatTrendPdf()` |
| `frontend/src/types/index.ts` | トレンド系の型 |

新しいチャートコンポーネントは作らない。ロットトレンドは汎用化した `WatItemTrendChart` に系列を渡して描く。

---

### Task 1: トレンドクエリと正規化の共通化

**Files:**
- Modify: `backend/app/services/wat_queries.py`
- Test: `backend/tests/test_wat_trend_queries.py` (create)
- Test: `backend/tests/test_query_bind_names.py` (modify)

**Interfaces:**
- Consumes: 既存の `WAT_TABLE`、`_product_id_clause()`、`_run()`
- Produces:
  - `WAT_TREND_COLUMNS: list[str]` = `["lot_id", "wafer_id", "site_no", "item_name", "item_unit", "spec_low", "spec_high", "meas_data", "start_time"]`
  - `build_wat_trend_query(product_id: str, start: date, end: date) -> tuple[str, dict]`
  - `query_wat_trend(product_id: str, start: date, end: date) -> pd.DataFrame`
  - `_normalize_detail(df: pd.DataFrame) -> pd.DataFrame`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_wat_trend_queries.py`:

```python
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pandas as pd

import app.services.wat_queries as wat_queries
from app.services.wat_queries import (
    WAT_TABLE, WAT_TREND_COLUMNS, build_wat_trend_query,
)


def test_trend_query_binds_product_and_period():
    sql, binds = build_wat_trend_query("P12345-A", date(2026, 6, 9), date(2026, 9, 8))
    assert WAT_TABLE in sql
    assert binds == {
        "pid": "P12345-A",
        "start_dt": date(2026, 6, 9),
        "end_dt": date(2026, 9, 8),
    }


def test_trend_query_uses_equality_without_a_wildcard():
    sql, _ = build_wat_trend_query("P12345-A", date(2026, 1, 1), date(2026, 2, 1))
    assert "PRODUCT_ID = :pid" in sql
    assert "LIKE" not in sql


def test_trend_query_uses_like_with_a_wildcard():
    sql, _ = build_wat_trend_query("SC0G29B%", date(2026, 1, 1), date(2026, 2, 1))
    assert "PRODUCT_ID LIKE :pid" in sql


def test_trend_query_upper_bound_is_exclusive():
    sql, _ = build_wat_trend_query("P", date(2026, 1, 1), date(2026, 2, 1))
    assert "START_TIME >= :start_dt" in sql
    assert "START_TIME <  :end_dt" in sql or "START_TIME < :end_dt" in sql


def test_trend_query_selects_every_declared_column():
    sql, _ = build_wat_trend_query("P", date(2026, 1, 1), date(2026, 2, 1))
    select_body = sql.split("FROM")[0]
    for col in WAT_TREND_COLUMNS:
        assert col in select_body, f"{col} missing from SELECT"


def test_trend_query_is_empty_without_a_product_id():
    assert build_wat_trend_query("", date(2026, 1, 1), date(2026, 2, 1)) == ("", {})


def test_query_wat_trend_returns_empty_frame_without_a_product_id():
    df = wat_queries.query_wat_trend("", date(2026, 1, 1), date(2026, 2, 1))
    assert df.empty
    assert list(df.columns) == WAT_TREND_COLUMNS


def test_query_wat_trend_normalizes_padded_text_and_decimals(monkeypatch):
    """Oracle CHAR pads with spaces and can hand back decimal.Decimal.

    Unstripped names never match the configured `wat: pairs`, and an
    object-dtype column breaks Series.std(ddof=1) downstream.
    """
    rows = [(
        "LOT-1  ", 3, 5, "VTHN_RVT  ", "V  ",
        Decimal("0.30"), Decimal("0.60"), Decimal("0.45"), "2026-06-14",
    )]
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    conn = MagicMock()
    conn.cursor.return_value = cursor
    monkeypatch.setattr(wat_queries, "get_connection", lambda: conn)
    monkeypatch.setattr(wat_queries, "release_connection", lambda c: None)

    df = wat_queries.query_wat_trend("P", date(2026, 1, 1), date(2026, 2, 1))

    assert df["lot_id"].iloc[0] == "LOT-1"
    assert df["item_name"].iloc[0] == "VTHN_RVT"
    assert df["item_unit"].iloc[0] == "V"
    assert pd.api.types.is_numeric_dtype(df["meas_data"])
    assert pd.api.types.is_numeric_dtype(df["spec_low"])
    assert pd.api.types.is_numeric_dtype(df["spec_high"])
```

Append to `backend/tests/test_query_bind_names.py`: add `build_wat_trend_query` to the `app.services.wat_queries` import line, and add these two cases to `BUILDER_CASES` right after the `wat_detail` entry:

```python
    ("wat_trend", lambda: build_wat_trend_query("P1", date(2026, 1, 1), date(2026, 2, 1))),
    ("wat_trend_wildcard", lambda: build_wat_trend_query("P%", date(2026, 1, 1), date(2026, 2, 1))),
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_wat_trend_queries.py tests/test_query_bind_names.py -v`
Expected: FAIL with `ImportError: cannot import name 'WAT_TREND_COLUMNS'`

- [ ] **Step 3: Implement**

In `backend/app/services/wat_queries.py`, add next to `WAT_DETAIL_COLUMNS`:

```python
# Column names in the SAME order as the trend SELECT below. lot_id leads
# because the trend path aggregates per lot; everything after it matches
# WAT_DETAIL_COLUMNS so the two frames share one normalizer.
WAT_TREND_COLUMNS = [
    "lot_id", "wafer_id", "site_no", "item_name", "item_unit",
    "spec_low", "spec_high", "meas_data", "start_time",
]
```

Add after `build_wat_detail_query`:

```python
def build_wat_trend_query(product_id: str, start: date, end: date) -> tuple[str, dict]:
    """Every measurement of every lot measured in [start, end).

    One query, not one per lot: 25 wafers x 9 sites x 30 items is ~6,750 rows
    per lot, so a 3-month window is ~70k rows — a single fetch pandas handles
    comfortably, against N round trips that do not.

    The `_dt` bind suffixes are mandatory: bare START / END are Oracle
    reserved words and oracledb raises ORA-01745 only at execute time, against
    a real database. See tests/test_query_bind_names.py.
    """
    if not product_id:
        return "", {}
    sql = f"""
        SELECT LOT_ID     AS lot_id,
               WAFER_ID   AS wafer_id,
               SITE_NO    AS site_no,
               ITEM_NAME  AS item_name,
               ITEM_UNIT  AS item_unit,
               SPEC_LOW   AS spec_low,
               SPEC_HIGH  AS spec_high,
               MEAS_DATA  AS meas_data,
               START_TIME AS start_time
        FROM {WAT_TABLE}
        WHERE {_product_id_clause(product_id)}
          AND START_TIME >= :start_dt
          AND START_TIME <  :end_dt
        ORDER BY item_name, start_time, lot_id, wafer_id, site_no
    """
    return sql, {"pid": product_id, "start_dt": start, "end_dt": end}
```

Add the normalizer above `query_wat_detail` and route both readers through it:

```python
def _normalize_detail(df: pd.DataFrame) -> pd.DataFrame:
    """Boundary normalisation so mock and real-DB frames end up the same shape.

    - LOT_ID / ITEM_NAME / ITEM_UNIT come back space-padded from Oracle CHAR
      columns; unstripped, the configured `wat:` item names never match and a
      lot id renders with trailing blanks.
    - MEAS_DATA / SPEC_LOW / SPEC_HIGH can arrive as decimal.Decimal (e.g. if
      oracledb.defaults.fetch_decimals is set), which makes the column
      object-dtype and breaks Series.std(ddof=1) downstream with a TypeError.

    Shared by the detail and trend readers on purpose: this is exactly the
    kind of fix that gets applied to one path and forgotten on the other.
    """
    if df.empty:
        return df
    for col in ("lot_id", "item_name", "item_unit"):
        if col in df.columns:
            df[col] = df[col].str.strip()
    for col in ("meas_data", "spec_low", "spec_high"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
```

Replace the body of `query_wat_detail` after the `_run(...)` call (drop its inline strip/to_numeric loops, keep the docstring pointing at `_normalize_detail`):

```python
def query_wat_detail(product_id: str, lot_id: str) -> pd.DataFrame:
    """Detail rows for one lot, normalised by _normalize_detail()."""
    sql, binds = build_wat_detail_query(product_id, lot_id)
    return _normalize_detail(_run(sql, binds, WAT_DETAIL_COLUMNS, "detail"))


def query_wat_trend(product_id: str, start: date, end: date) -> pd.DataFrame:
    """Detail rows for every lot in the period, normalised the same way."""
    sql, binds = build_wat_trend_query(product_id, start, end)
    return _normalize_detail(_run(sql, binds, WAT_TREND_COLUMNS, "trend"))
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && uv run pytest tests/test_wat_trend_queries.py tests/test_query_bind_names.py tests/test_wat_queries.py -v`
Expected: PASS（`test_wat_queries.py` の既存テストも全て通ること — 正規化の抽出で挙動が変わっていない証拠）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/wat_queries.py backend/tests/test_wat_trend_queries.py backend/tests/test_query_bind_names.py
git commit -m "feat(wat): add the cross-lot trend query and share detail normalization"
```

---

### Task 2: スキーマと統計コアの抽出

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/services/wat_service.py`
- Test: `backend/tests/test_wat_item_core.py` (create)

**Interfaces:**
- Consumes: 既存の `resolve_spec()`、`count_out_of_spec()`、`compute_cpk()`、`classify_status()`、`_wafer_series()`
- Produces:
  - `_item_core(group: pd.DataFrame, item_name: str, spec_low: float | None, spec_high: float | None) -> dict` — `wafer_series` / `lot_series` を除く全スカラー列
  - pydantic: `WatLotPoint`、`WatTrendItemStats`、`WatTrendResponse`、`WatTrendExportRequest`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_wat_item_core.py`:

```python
import pandas as pd

from app.models.schemas import (
    WatLotPoint, WatTrendItemStats, WatTrendResponse,
)
from app.services.mock_data import mock_wat_lots
from app.services.wat_service import _item_core, compute_item_stats, get_wat_summary


def _group(values, spec_low=0.0, spec_high=1.0):
    return pd.DataFrame({
        "wafer_id": [1] * len(values),
        "site_no": list(range(1, len(values) + 1)),
        "item_name": ["ITEM"] * len(values),
        "item_unit": ["V"] * len(values),
        "spec_low": [spec_low] * len(values),
        "spec_high": [spec_high] * len(values),
        "meas_data": values,
    })


def test_item_core_carries_every_scalar_column_but_no_series():
    core = _item_core(_group([0.4, 0.5, 0.6]), "ITEM", 0.0, 1.0)
    assert set(core) == {
        "item_name", "unit", "spec_low", "spec_high", "n", "mean", "sigma",
        "min", "max", "cpk", "cpk_state", "oos_count", "oos_pct", "status",
    }


def test_item_core_uses_the_spec_it_is_given_not_the_frame():
    """The trend path resolves one spec for the whole period and applies it to
    every lot; a per-lot re-resolve would let a chart's spec line disagree with
    the point judged against it."""
    group = _group([0.4, 0.5, 0.6], spec_low=0.0, spec_high=1.0)
    core = _item_core(group, "ITEM", 0.45, 0.55)
    assert core["spec_low"] == 0.45
    assert core["spec_high"] == 0.55
    assert core["oos_count"] == 2      # 0.4 and 0.6 are outside 0.45..0.55
    assert core["status"] == "red"


def test_compute_item_stats_still_returns_the_wafer_series():
    stats = compute_item_stats(_group([0.4, 0.5, 0.6]), "ITEM")
    assert stats["item_name"] == "ITEM"
    assert [w["wafer_id"] for w in stats["wafer_series"]] == [1]


def test_get_wat_summary_output_is_unchanged_by_the_extraction():
    """Regression guard: the single-lot report must not shift at all."""
    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[-1]
    summary = get_wat_summary("product_a", "P12345-A", lot)
    assert len(summary.items) == 30
    vthn = next(i for i in summary.items if i.item_name == "VTHN_ULVT")
    assert vthn.status == "red"
    assert len(vthn.wafer_series) == 25


def test_trend_models_accept_a_minimal_payload():
    point = WatLotPoint(
        lot_id="LOT-1", measured_date="2026-06-14", n=225,
        mean=0.45, sigma=0.02, cpk=1.2, cpk_state="value", status="yellow",
    )
    item = WatTrendItemStats(
        item_name="VTHN_RVT", unit="V", spec_low=0.3, spec_high=0.6,
        n=225, mean=0.45, sigma=0.02, min=0.4, max=0.5,
        cpk=1.2, cpk_state="value", oos_count=0, oos_pct=0.0,
        status="yellow", lot_series=[point],
    )
    res = WatTrendResponse(
        product_id="P12345-A", display_name="Product A", months=3,
        start_date="2026-06-09", end_date="2026-09-08", lots=[], items=[item],
    )
    assert res.items[0].lot_series[0].lot_id == "LOT-1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_wat_item_core.py -v`
Expected: FAIL with `ImportError: cannot import name 'WatLotPoint'`

- [ ] **Step 3: Implement**

In `backend/app/models/schemas.py`, append after `WatExportRequest`:

```python
class WatLotPoint(BaseModel):
    """One lot's statistics for one item — a point on the trend chart."""
    lot_id: str
    measured_date: str
    n: int
    mean: float | None = None
    sigma: float | None = None
    cpk: float | None = None
    cpk_state: str          # "value" | "infinite" | "undefined"
    status: str             # "red" | "yellow" | "gray" | "ok"


class WatTrendItemStats(BaseModel):
    """Period-wide statistics for one item, pooled over every lot's raw site
    measurements — not an average of lot averages."""
    item_name: str
    unit: str = ""
    spec_low: float | None = None
    spec_high: float | None = None
    n: int
    mean: float | None = None
    sigma: float | None = None
    min: float | None = None
    max: float | None = None
    cpk: float | None = None
    cpk_state: str
    oos_count: int
    oos_pct: float
    status: str
    lot_series: list[WatLotPoint]


class WatTrendResponse(BaseModel):
    """`lots` is newest first (header strip); `lot_series` inside each item is
    oldest first (chart X axis). The two orders differ on purpose."""
    product_id: str
    display_name: str
    months: int
    start_date: str         # inclusive
    end_date: str           # exclusive
    lots: list[WatLotInfo]
    items: list[WatTrendItemStats]


class WatTrendExportRequest(BaseModel):
    product_id: str
    months: int = 3
```

In `backend/app/services/wat_service.py`, replace `compute_item_stats` with the extracted pair:

```python
def _item_core(group: pd.DataFrame, item_name: str,
               spec_low: float | None, spec_high: float | None) -> dict:
    """Every scalar statistic for one item over `group`, judged against the
    spec limits it is handed.

    The caller resolves the spec, because the two callers resolve it over
    different scopes: the single-lot report over one lot, the trend report
    once for the whole period (so a lot's point and the chart's spec line
    can never disagree). Series generation lives in the callers too — this
    function is the shared Cpk/OOS/judgement core, and there is exactly one
    of it.
    """
    units = group["item_unit"].dropna()
    unit = str(units.iloc[0]) if not units.empty else ""

    values = group["meas_data"].dropna()
    n = int(len(values))
    oos_count = count_out_of_spec(group["meas_data"], spec_low, spec_high)

    mean = _clean(values.mean()) if n else None
    sigma = _clean(values.std(ddof=1)) if n >= 2 else None
    cpk, cpk_state = compute_cpk(mean, sigma, spec_low, spec_high, n, oos_count)

    return {
        "item_name": item_name,
        "unit": unit,
        "spec_low": spec_low,
        "spec_high": spec_high,
        "n": n,
        "mean": mean,
        "sigma": sigma,
        "min": _clean(values.min()) if n else None,
        "max": _clean(values.max()) if n else None,
        "cpk": _clean(cpk),
        "cpk_state": cpk_state,
        "oos_count": oos_count,
        "oos_pct": round(oos_count / n * 100, 4) if n else 0.0,
        "status": classify_status(cpk, cpk_state, oos_count),
    }


def compute_item_stats(group: pd.DataFrame, item_name: str) -> dict:
    """Statistics for one ITEM_NAME across every wafer and site of one lot."""
    spec_low = resolve_spec(group["spec_low"], item_name)
    spec_high = resolve_spec(group["spec_high"], item_name)
    return {
        **_item_core(group, item_name, spec_low, spec_high),
        "wafer_series": _wafer_series(group),
    }
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && uv run pytest tests/test_wat_item_core.py tests/test_wat_stats.py tests/test_wat_service_integration.py tests/test_schemas.py -v`
Expected: PASS（既存の WAT テストが全て通ること）

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/schemas.py backend/app/services/wat_service.py backend/tests/test_wat_item_core.py
git commit -m "feat(wat): add trend schemas and extract the shared item stats core"
```

---

### Task 3: モックのトレンド明細

**Files:**
- Modify: `backend/app/services/mock_data.py`
- Test: `backend/tests/test_wat_trend_mock.py` (create)

**Interfaces:**
- Consumes: 既存の `mock_wat_lots()`、`mock_wat_dataframe()`
- Produces: `mock_wat_trend_dataframe(product_id: str, months: int) -> pd.DataFrame`（列は `WAT_TREND_COLUMNS` と同順）

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_wat_trend_mock.py`:

```python
import pandas as pd

from app.services.mock_data import (
    mock_wat_dataframe, mock_wat_lots, mock_wat_trend_dataframe,
)
from app.services.wat_queries import WAT_TREND_COLUMNS


def test_trend_frame_covers_every_lot_in_the_period():
    lots = mock_wat_lots("P12345-A", 3)
    df = mock_wat_trend_dataframe("P12345-A", 3)
    assert set(df["lot_id"]) == set(lots["lot_id"])


def test_trend_frame_column_order_matches_the_query():
    df = mock_wat_trend_dataframe("P12345-A", 3)
    assert list(df.columns) == WAT_TREND_COLUMNS


def test_trend_frame_rows_match_the_single_lot_frame():
    """Same generator, so a lot's rows must not change when read via trend."""
    lot = str(mock_wat_lots("P12345-A", 3)["lot_id"].iloc[0])
    single = mock_wat_dataframe("P12345-A", lot)
    trend = mock_wat_trend_dataframe("P12345-A", 3)
    subset = trend[trend["lot_id"] == lot]
    assert len(subset) == len(single)
    assert subset["meas_data"].sum() == single["meas_data"].sum()


def test_trend_frame_is_deterministic():
    a = mock_wat_trend_dataframe("P12345-A", 3)
    b = mock_wat_trend_dataframe("P12345-A", 3)
    assert a.equals(b)


def test_trend_frame_is_empty_when_the_period_holds_no_lots(monkeypatch):
    """The mock lot generator fabricates lots for ANY product id, so the empty
    path has to be forced — a made-up product id would not reach it."""
    import app.services.mock_data as mock_data
    monkeypatch.setattr(
        mock_data, "mock_wat_lots",
        lambda pid, months: pd.DataFrame(columns=mock_data.WAT_LOT_COLUMNS),
    )
    df = mock_data.mock_wat_trend_dataframe("P12345-A", 3)
    assert df.empty
    assert list(df.columns) == WAT_TREND_COLUMNS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_wat_trend_mock.py -v`
Expected: FAIL with `ImportError: cannot import name 'mock_wat_trend_dataframe'`

- [ ] **Step 3: Implement**

In `backend/app/services/mock_data.py`, add next to the existing `WAT_DETAIL_COLUMNS` / `WAT_LOT_COLUMNS` constants (this module deliberately keeps its own copies rather than importing from `wat_queries` — follow that existing convention):

```python
WAT_TREND_COLUMNS = ["lot_id"] + WAT_DETAIL_COLUMNS
```

Append at the end of the file:

```python
def mock_wat_trend_dataframe(product_id: str, months: int) -> pd.DataFrame:
    """Deterministic per-site WAT measurements for every lot in the period.

    Reuses mock_wat_dataframe per lot, so a lot's rows are identical whether
    read through the single-lot path or the trend path, and the deliberate
    defects (VTHN_ULVT red, RS_NDIFF yellow) show up on the trend too.
    """
    lots = mock_wat_lots(product_id, months)
    frames: list[pd.DataFrame] = []
    for lot_id in lots["lot_id"]:
        df = mock_wat_dataframe(product_id, str(lot_id))
        if df.empty:
            continue
        df = df.copy()
        df.insert(0, "lot_id", str(lot_id))
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=WAT_TREND_COLUMNS)
    return pd.concat(frames, ignore_index=True)[WAT_TREND_COLUMNS]
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && uv run pytest tests/test_wat_trend_mock.py tests/test_wat_mock.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/mock_data.py backend/tests/test_wat_trend_mock.py
git commit -m "feat(wat): add deterministic mock data for the trend report"
```

---

### Task 4: トレンド集計サービス

**Files:**
- Create: `backend/app/services/wat_trend_service.py`
- Test: `backend/tests/test_wat_trend_stats.py` (create)

**Interfaces:**
- Consumes: `_item_core()`、`resolve_spec()`、`compute_cpk()`、`classify_status()`、`count_out_of_spec()`（Task 2）、`query_wat_trend()`・`WAT_TREND_COLUMNS`（Task 1）、`mock_wat_trend_dataframe()`（Task 3）、`WatTrendResponse` ほか（Task 2）
- Produces: `get_wat_trend(nickname: str, product_id: str, months: int) -> WatTrendResponse`、`build_lot_series(group: pd.DataFrame, item_name: str, spec_low, spec_high) -> list[dict]`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_wat_trend_stats.py`:

```python
import logging

import pandas as pd
import pytest

from app.services.wat_trend_service import build_lot_series, get_wat_trend


def _frame(rows):
    """rows: (lot_id, start_time, wafer_id, site_no, meas, spec_low, spec_high)"""
    return pd.DataFrame([
        {
            "lot_id": lot, "start_time": ts, "wafer_id": w, "site_no": s,
            "item_name": "ITEM", "item_unit": "V",
            "spec_low": lo, "spec_high": hi, "meas_data": v,
        }
        for lot, ts, w, s, v, lo, hi in rows
    ])


def test_lot_series_is_ordered_oldest_first():
    df = _frame([
        ("L3", "2026-08-01", 1, 1, 0.5, 0.0, 1.0),
        ("L1", "2026-06-01", 1, 1, 0.5, 0.0, 1.0),
        ("L2", "2026-07-01", 1, 1, 0.5, 0.0, 1.0),
    ])
    series = build_lot_series(df, "ITEM", 0.0, 1.0)
    assert [p["lot_id"] for p in series] == ["L1", "L2", "L3"]
    assert [p["measured_date"] for p in series] == [
        "2026-06-01", "2026-07-01", "2026-08-01",
    ]


def test_lot_series_sigma_is_none_for_a_single_measurement():
    df = _frame([("L1", "2026-06-01", 1, 1, 0.5, 0.0, 1.0)])
    series = build_lot_series(df, "ITEM", 0.0, 1.0)
    assert series[0]["n"] == 1
    assert series[0]["sigma"] is None


def test_lot_series_flags_the_lot_that_went_out_of_spec():
    df = _frame([
        ("L1", "2026-06-01", 1, 1, 0.50, 0.0, 1.0),
        ("L1", "2026-06-01", 1, 2, 0.52, 0.0, 1.0),
        ("L2", "2026-07-01", 1, 1, 0.50, 0.0, 1.0),
        ("L2", "2026-07-01", 1, 2, 1.40, 0.0, 1.0),
    ])
    series = build_lot_series(df, "ITEM", 0.0, 1.0)
    assert series[0]["status"] == "ok"
    assert series[1]["status"] == "red"


def test_period_stats_pool_raw_measurements_not_lot_means():
    """Two tight lots at different centers: pooling sees the spread between
    them, averaging lot means would not."""
    df = _frame([
        ("L1", "2026-06-01", 1, 1, 0.40, 0.0, 1.0),
        ("L1", "2026-06-01", 1, 2, 0.40, 0.0, 1.0),
        ("L2", "2026-07-01", 1, 1, 0.60, 0.0, 1.0),
        ("L2", "2026-07-01", 1, 2, 0.60, 0.0, 1.0),
    ])
    from app.services.wat_service import _item_core
    core = _item_core(df, "ITEM", 0.0, 1.0)
    assert core["n"] == 4
    assert core["mean"] == pytest.approx(0.5)
    assert core["sigma"] == pytest.approx(0.11547, rel=1e-3)   # not 0.0


def test_period_spec_conflict_takes_the_most_common_and_warns(caplog):
    df = _frame([
        ("L1", "2026-06-01", 1, 1, 0.5, 0.0, 1.0),
        ("L1", "2026-06-01", 1, 2, 0.5, 0.0, 1.0),
        ("L2", "2026-07-01", 1, 1, 0.5, 0.0, 1.2),
    ])
    from app.services.wat_service import resolve_spec
    with caplog.at_level(logging.WARNING):
        assert resolve_spec(df["spec_high"], "ITEM") == 1.0
    assert "distinct spec values" in caplog.text


def test_get_wat_trend_reports_the_mock_products_items_and_lots():
    res = get_wat_trend("product_a", "P12345-A", 3)
    assert res.product_id
    assert res.months == 3
    assert len(res.items) == 30
    assert [i.item_name for i in res.items] == sorted(i.item_name for i in res.items)
    assert res.lots, "the mock product has lots in a 3-month window"
    # lots newest first, lot_series oldest first — deliberately opposite
    assert [l.last_measured for l in res.lots] == sorted(
        [l.last_measured for l in res.lots], reverse=True
    )
    series = res.items[0].lot_series
    assert [p.measured_date for p in series] == sorted(p.measured_date for p in series)
    assert len(series) == len(res.lots)


def test_get_wat_trend_still_flags_the_deliberate_mock_defects():
    res = get_wat_trend("product_a", "P12345-A", 3)
    by_name = {i.item_name: i for i in res.items}
    assert by_name["VTHN_ULVT"].status == "red"


def test_get_wat_trend_with_no_data_is_empty_not_an_error(monkeypatch):
    """Mock mode fabricates lots for any product id, so the no-data path has
    to be forced at the loader."""
    import app.services.wat_trend_service as svc
    monkeypatch.setattr(svc, "_load_trend", lambda pid, months: pd.DataFrame())
    res = svc.get_wat_trend("product_a", "P12345-A", 3)
    assert res.items == []
    assert res.lots == []
    assert res.months == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_wat_trend_stats.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.wat_trend_service'`

- [ ] **Step 3: Implement**

Create `backend/app/services/wat_trend_service.py`:

```python
"""PCM/WAT trend service: item statistics pooled over a period, plus a
per-lot series for each item.

The counterpart of wat_service, which is scoped to a single lot. Everything
here spans lots; the Cpk/OOS/judgement core itself is shared (_item_core), so
the two reports can never disagree about what a Cpk of 1.2 means.
"""

import logging
from datetime import date, timedelta

import pandas as pd

from app.config import settings
from app.models.schemas import (
    WatLotInfo, WatLotPoint, WatTrendItemStats, WatTrendResponse,
)
from app.services.mock_data import mock_wat_trend_dataframe
from app.services.product_config import primary_product_id, resolve_display_name
from app.services.wat_queries import WAT_TREND_COLUMNS, query_wat_trend
from app.services.wat_service import _item_core, resolve_spec

logger = logging.getLogger(__name__)


def _period(months: int) -> tuple[date, date]:
    """[start, end) for the window. The end is exclusive and one day ahead so
    today's measurements are included — the same contract as _load_lots()."""
    today = date.today()
    return today - timedelta(days=months * 30), today + timedelta(days=1)


def _load_trend(product_id: str, months: int) -> pd.DataFrame:
    if settings.USE_MOCK_DATA:
        return mock_wat_trend_dataframe(product_id, months)
    start, end = _period(months)
    return query_wat_trend(product_id, start, end)


def _measured_date(stamps: pd.Series) -> str:
    """A lot's date is its latest measurement, trimmed to YYYY-MM-DD."""
    clean = stamps.dropna()
    return str(clean.max())[:10] if not clean.empty else ""


def build_lot_series(group: pd.DataFrame, item_name: str,
                     spec_low: float | None,
                     spec_high: float | None) -> list[dict]:
    """One point per lot for a single item, oldest measured date first.

    The spec limits are passed in rather than re-resolved per lot: the chart
    draws one spec line for the whole period, so judging each lot against a
    different limit would put a red point under a line it never crossed.
    """
    points: list[dict] = []
    for lot_id, g in group.groupby("lot_id", sort=False):
        core = _item_core(g, item_name, spec_low, spec_high)
        points.append({
            "lot_id": str(lot_id),
            "measured_date": _measured_date(g["start_time"]),
            "n": core["n"],
            "mean": core["mean"],
            "sigma": core["sigma"],
            "cpk": core["cpk"],
            "cpk_state": core["cpk_state"],
            "status": core["status"],
        })
    points.sort(key=lambda p: (p["measured_date"], p["lot_id"]))
    return points


def _lot_infos(df: pd.DataFrame) -> list[WatLotInfo]:
    """Lot list for the header strip, newest measured date first."""
    rows: list[WatLotInfo] = []
    for lot_id, g in df.groupby("lot_id", sort=False):
        rows.append(WatLotInfo(
            lot_id=str(lot_id),
            last_measured=_measured_date(g["start_time"]),
            wafer_count=int(g["wafer_id"].nunique()),
        ))
    rows.sort(key=lambda r: (r.last_measured, r.lot_id), reverse=True)
    return rows


def get_wat_trend(nickname: str, product_id: str, months: int) -> WatTrendResponse:
    """Period-wide item statistics and per-lot series for one product."""
    df = _load_trend(product_id, months)
    if df.empty:
        df = pd.DataFrame(columns=WAT_TREND_COLUMNS)

    start, end = _period(months)
    items: list[WatTrendItemStats] = []

    for item_name, group in df.groupby("item_name", sort=True):
        name = str(item_name)
        # Resolved once over the whole period, then applied to every lot.
        spec_low = resolve_spec(group["spec_low"], name)
        spec_high = resolve_spec(group["spec_high"], name)
        core = _item_core(group, name, spec_low, spec_high)
        series = [WatLotPoint(**p)
                  for p in build_lot_series(group, name, spec_low, spec_high)]
        items.append(WatTrendItemStats(**core, lot_series=series))

    lots = _lot_infos(df) if not df.empty else []
    logger.info(
        "WAT trend: product=%s months=%d lots=%d items=%d",
        product_id, months, len(lots), len(items),
    )

    return WatTrendResponse(
        product_id=primary_product_id(nickname) or product_id,
        display_name=resolve_display_name(nickname),
        months=months,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        lots=lots,
        items=items,
    )
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && uv run pytest tests/test_wat_trend_stats.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/wat_trend_service.py backend/tests/test_wat_trend_stats.py
git commit -m "feat(wat): add the cross-lot trend aggregation service"
```

---

### Task 5: トレンド API エンドポイント

**Files:**
- Modify: `backend/app/routers/wat.py`
- Test: `backend/tests/test_wat_trend_api.py` (create)

**Interfaces:**
- Consumes: `get_wat_trend()`（Task 4）、`WatTrendResponse`（Task 2）、既存の `nickname_for_product_id()`
- Produces: `GET /api/wat/trend?product_id=&months=` → `WatTrendResponse`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_wat_trend_api.py`:

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_trend_endpoint_returns_items_and_lots():
    res = client.get("/api/wat/trend", params={"product_id": "P12345-A", "months": 3})
    assert res.status_code == 200
    body = res.json()
    assert body["months"] == 3
    assert body["start_date"] < body["end_date"]
    assert len(body["items"]) == 30
    assert body["lots"]


def test_trend_endpoint_defaults_to_three_months():
    res = client.get("/api/wat/trend", params={"product_id": "P12345-A"})
    assert res.status_code == 200
    assert res.json()["months"] == 3


def test_trend_endpoint_rejects_out_of_range_months():
    for months in (0, 7):
        res = client.get("/api/wat/trend",
                         params={"product_id": "P12345-A", "months": months})
        assert res.status_code == 422, months


def test_trend_endpoint_items_carry_a_lot_series():
    res = client.get("/api/wat/trend", params={"product_id": "P12345-A", "months": 3})
    item = res.json()["items"][0]
    assert item["lot_series"]
    point = item["lot_series"][0]
    assert set(point) == {
        "lot_id", "measured_date", "n", "mean", "sigma",
        "cpk", "cpk_state", "status",
    }


def test_trend_endpoint_survives_an_unconfigured_product_id():
    """Mock mode fabricates data for any product id, so this checks the
    unconfigured-nickname path returns 200 rather than 500 — not emptiness."""
    res = client.get("/api/wat/trend",
                     params={"product_id": "nope-nope", "months": 3})
    assert res.status_code == 200
    assert res.json()["product_id"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_wat_trend_api.py -v`
Expected: FAIL with 404 on `/api/wat/trend`

- [ ] **Step 3: Implement**

In `backend/app/routers/wat.py`, extend the imports and add the route after `wat_summary`:

```python
from app.models.schemas import (
    WatExportRequest, WatLotsResponse, WatSummaryResponse, WatTrendResponse,
)
from app.services.wat_trend_service import get_wat_trend
```

```python
@router.get("/wat/trend", response_model=WatTrendResponse)
def wat_trend(
    product_id: str = Query(...),
    months: int = Query(3, ge=1, le=6),
) -> WatTrendResponse:
    nickname = nickname_for_product_id(product_id) or product_id
    try:
        return get_wat_trend(nickname, product_id, months)
    except Exception:
        logger.error("get_wat_trend failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=503, detail="WAT data source unavailable")
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && uv run pytest tests/test_wat_trend_api.py tests/test_wat_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/wat.py backend/tests/test_wat_trend_api.py
git commit -m "feat(wat): expose GET /api/wat/trend"
```

---

### Task 6: PDF 共通部品の抽出（純リファクタ）

**Files:**
- Create: `backend/app/services/wat_pdf_common.py`
- Modify: `backend/app/services/wat_pdf_service.py`
- Test: `backend/tests/test_wat_pdf.py` (modify — import 元の変更のみ)

このタスクは**挙動を一切変えない**。既存 PDF テストが緑のままであることが唯一の合格条件。

**Interfaces:**
- Produces（`wat_pdf_common` から公開）:
  - `STATUS_MARK: dict[str, str]`、`STATUS_RGB: dict[str, tuple[float, float, float]]`、`STATUS_HEX: dict[str, str]`
  - `COL_WIDTHS: list[int]`、`COL_HEADERS: list[str]`、`ROW_H: float`、`TABLE_FONT: float`、`PAGE_BREAK_MARGIN: float`
  - `fmt_value(v) -> str`、`fmt_cpk(cpk, cpk_state: str) -> str`
  - `base_layout(width: int, height: int, title: str) -> dict`、`axis(title: str) -> dict`
  - `render_batch(figs: list[go.Figure]) -> list[bytes]`
  - `draw_table_header(c: canvas.Canvas, y: float) -> float`
  - `draw_item_row(c: canvas.Canvas, y: float, item) -> float` — `item` は `WatItemStats` と `WatTrendItemStats` の両方を受ける（読むのは共通のスカラー列だけ）
  - `rows_per_page(content_top: float) -> int`

- [ ] **Step 1: Create the shared module**

Create `backend/app/services/wat_pdf_common.py` by **moving** (not copying) these from `wat_pdf_service.py`, renaming the private ones to public:

- `STATUS_MARK`、`STATUS_RGB`
- `COL_WIDTHS`、`COL_HEADERS`、`ROW_H`、`TABLE_FONT`、`PAGE_BREAK_MARGIN`
- `fmt_value`、`fmt_cpk`
- `_base_layout` → `base_layout`
- `_axis` → `axis`
- `_render_batch` → `render_batch`
- `_draw_table_header` → `draw_table_header`
- `_draw_item_row` → `draw_item_row`
- `_rows_per_page` → `rows_per_page`

`draw_item_row` の型注釈は `WatItemStats` 固定をやめる（トレンド側の項目も同じスカラー列を持つため）:

```python
def draw_item_row(c: canvas.Canvas, y: float, item) -> float:
    """One table row. `item` is any object carrying the scalar stats columns —
    WatItemStats or WatTrendItemStats; the series field is never read here."""
```

Add the hex palette that Plotly needs (ReportLab wants floats, Plotly wants strings — one source, two forms):

```python
# Plotly needs hex; ReportLab needs float triples. Same colors, both forms.
STATUS_HEX: dict[str, str] = {
    "red": "#c64545", "yellow": "#d4a017", "gray": "#8e8b82", "ok": "#141413",
}
```

モジュール docstring:

```python
"""Parts shared by the two PCM/WAT PDFs (single-lot and trend).

The item table is the reason this module exists: it was drawn identically by
both reports, and a copy would drift the moment one of them gained a column.
"""
```

- [ ] **Step 2: Rewire `wat_pdf_service.py`**

Delete the moved definitions and import them instead:

```python
from app.services.wat_pdf_common import (
    COL_HEADERS, COL_WIDTHS, PAGE_BREAK_MARGIN, ROW_H, STATUS_HEX,
    STATUS_MARK, STATUS_RGB, TABLE_FONT, axis, base_layout, draw_item_row,
    draw_table_header, fmt_cpk, fmt_value, render_batch, rows_per_page,
)
```

Update every call site inside the file: `_base_layout(` → `base_layout(`, `_axis(` → `axis(`, `_render_batch(` → `render_batch(`, `_draw_table_header(` → `draw_table_header(`, `_draw_item_row(` → `draw_item_row(`, `_rows_per_page(` → `rows_per_page(`. `_draw_header`、`_scatter_figure`、`_trend_figure`、`count_pages`、`generate_wat_pdf`、`WAFER_COLORSCALE`、`PLOT_TITLES` はこのファイルに残す（単ロット固有）。

- [ ] **Step 3: Update the test's import**

In `backend/tests/test_wat_pdf.py`, change:

```python
from app.services.wat_pdf_service import (
    STATUS_MARK, fmt_cpk, fmt_value, generate_wat_pdf,
)
```

to:

```python
from app.services.wat_pdf_common import STATUS_MARK, fmt_cpk, fmt_value
from app.services.wat_pdf_service import generate_wat_pdf
```

- [ ] **Step 4: Run the full backend suite**

Run: `cd backend && uv run pytest -q`
Expected: PASS — 純リファクタなので既存テストが 1 件も落ちてはいけない。落ちたら移動漏れかリネーム漏れ。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/wat_pdf_common.py backend/app/services/wat_pdf_service.py backend/tests/test_wat_pdf.py
git commit -m "refactor(wat): extract the shared PDF parts into wat_pdf_common"
```

---

### Task 7: トレンド PDF と書き出しエンドポイント

**Files:**
- Create: `backend/app/services/wat_trend_pdf_service.py`
- Modify: `backend/app/routers/wat.py`
- Test: `backend/tests/test_wat_trend_pdf.py` (create)

**Interfaces:**
- Consumes: `wat_pdf_common` の全公開部品（Task 6）、`WatTrendResponse` / `WatTrendItemStats` / `WatTrendExportRequest`（Task 2）、`get_wat_trend()`（Task 4）、既存の `pdf_common`（`MARGIN`、`FOOTER_H`、`draw_logo`、`draw_footer`、`content_disposition`）
- Produces: `generate_wat_trend_pdf(trend: WatTrendResponse) -> bytes`、`count_pages(trend: WatTrendResponse, content_top: float) -> int`、`POST /api/wat/export-trend-pdf`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_wat_trend_pdf.py`:

```python
import io
import math

from pypdf import PdfReader

from app.models.schemas import WatTrendResponse
from app.services.wat_pdf_common import rows_per_page
from app.services.wat_trend_pdf_service import count_pages, generate_wat_trend_pdf
from app.services.wat_trend_service import get_wat_trend


def _empty_trend() -> WatTrendResponse:
    return WatTrendResponse(
        product_id="P12345-A", display_name="Product A", months=3,
        start_date="2026-06-09", end_date="2026-09-08", lots=[], items=[],
    )


def test_count_pages_is_table_pages_plus_two_charts_per_page():
    trend = get_wat_trend("product_a", "P12345-A", 3)
    content_top = 700.0
    per_page = rows_per_page(content_top)
    expected = (max(1, math.ceil(len(trend.items) / per_page))
                + math.ceil(len(trend.items) / 2))
    assert count_pages(trend, content_top) == expected


def test_generate_trend_pdf_produces_a_portrait_pdf():
    trend = get_wat_trend("product_a", "P12345-A", 3)
    out = generate_wat_trend_pdf(trend)
    assert out.startswith(b"%PDF")

    reader = PdfReader(io.BytesIO(out))
    box = reader.pages[0].mediabox
    assert box.height > box.width, "A4 portrait"
    assert len(reader.pages) > 1, "30 items cannot fit on one page"


def test_generate_trend_pdf_with_no_items_does_not_raise():
    out = generate_wat_trend_pdf(_empty_trend())
    assert out.startswith(b"%PDF")
    assert len(PdfReader(io.BytesIO(out)).pages) == 1
```

Append to `backend/tests/test_wat_trend_api.py`:

```python
def test_export_trend_pdf_returns_a_pdf_attachment():
    res = client.post("/api/wat/export-trend-pdf",
                      json={"product_id": "P12345-A", "months": 3})
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "attachment" in res.headers["content-disposition"]
    assert res.content.startswith(b"%PDF")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_wat_trend_pdf.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.wat_trend_pdf_service'`

- [ ] **Step 3: Implement the PDF module**

Create `backend/app/services/wat_trend_pdf_service.py`:

```python
"""PCM/WAT trend report PDF (A4 portrait).

Layout: period header + the full item table, then a lot-trend chart for
EVERY item, two per page. The single-lot report charts only its flagged
items; this one is the period's record, so nothing is dropped.
"""

import io
import logging
import math

import plotly.graph_objects as go
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.models.schemas import WatTrendItemStats, WatTrendResponse
from app.services.pdf_common import FOOTER_H, MARGIN, draw_footer, draw_logo
from app.services.wat_pdf_common import (
    PAGE_BREAK_MARGIN, STATUS_HEX, STATUS_RGB, axis, base_layout,
    draw_item_row, draw_table_header, render_batch, rows_per_page,
)

logger = logging.getLogger(__name__)


def _lot_trend_figure(item: WatTrendItemStats,
                      width: int = 1000, height: int = 647) -> go.Figure:
    """Lot means with +/-3 sigma whiskers against the period's spec lines.

    Marker color carries each lot's own judgement, so a reader can see which
    lot went out without cross-referencing the table.
    """
    series = item.lot_series
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[p.lot_id for p in series],
        y=[p.mean for p in series],
        mode="lines+markers",
        line=dict(color="#141413", width=2),
        marker=dict(
            size=8,
            color=[STATUS_HEX.get(p.status, STATUS_HEX["ok"]) for p in series],
        ),
        error_y=dict(
            type="data",
            array=[(p.sigma * 3 if p.sigma is not None else 0) for p in series],
            visible=True, color="rgba(20,20,19,0.35)", thickness=1.2, width=3,
        ),
    ))
    for limit, label in ((item.spec_low, "LSL"), (item.spec_high, "USL")):
        if limit is not None:
            fig.add_hline(y=limit, line=dict(color="#c64545", width=1, dash="dash"),
                          annotation_text=label,
                          annotation_font=dict(size=9, color="#c64545"))

    unit = f" [{item.unit}]" if item.unit else ""
    fig.update_layout(**base_layout(width, height, f"{item.item_name}{unit}"),
                      xaxis=dict(**axis("Lot"), type="category"),
                      yaxis=axis(""))
    return fig


def _draw_header(c: canvas.Canvas, page_width: float, page_height: float,
                 trend: WatTrendResponse) -> float:
    """Draws the header band; returns the y coordinate where content starts."""
    top = page_height - MARGIN
    logo_h = 10 * mm
    draw_logo(c, MARGIN, top - logo_h, logo_h)

    c.saveState()
    c.setFillColorRGB(0.216, 0.208, 0.184)
    c.setFont("Helvetica-Bold", 13)
    title = f"PCM / WAT Trend  —  {trend.product_id}"
    if trend.display_name and trend.display_name != trend.product_id:
        title += f"  ({trend.display_name})"
    c.drawString(MARGIN, top - logo_h - 7 * mm, title)

    latest = trend.lots[0].last_measured if trend.lots else "—"
    c.setFont("Helvetica", 8.5)
    c.setFillColorRGB(0.38, 0.36, 0.35)
    meta = (f"{trend.start_date} — {latest}    Last {trend.months} months    "
            f"{len(trend.lots)} lots    {len(trend.items)} items")
    c.drawString(MARGIN, top - logo_h - 12 * mm, meta)

    reds = sum(1 for i in trend.items if i.status == "red")
    yellows = sum(1 for i in trend.items if i.status == "yellow")
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColorRGB(*STATUS_RGB["red"])
    c.drawRightString(page_width - MARGIN - 18 * mm, top - logo_h - 12 * mm,
                      f"● {reds}")
    c.setFillColorRGB(*STATUS_RGB["yellow"])
    c.drawRightString(page_width - MARGIN, top - logo_h - 12 * mm, f"▲ {yellows}")

    rule_y = top - logo_h - 15 * mm
    c.setStrokeColorRGB(0, 0, 0, alpha=0.12)
    c.setLineWidth(0.6)
    c.line(MARGIN, rule_y, page_width - MARGIN, rule_y)
    c.restoreState()
    return rule_y - 6 * mm


def count_pages(trend: WatTrendResponse, content_top: float) -> int:
    """Total page count, known before drawing — ReportLab cannot revisit a
    finished page, so "Page n of N" needs N up front."""
    per_page = rows_per_page(content_top)
    table_pages = max(1, math.ceil(len(trend.items) / per_page))
    chart_pages = math.ceil(len(trend.items) / 2)
    return table_pages + chart_pages


def generate_wat_trend_pdf(trend: WatTrendResponse) -> bytes:
    """A4 portrait PCM/WAT trend report."""
    buf = io.BytesIO()
    page_width, page_height = A4
    c = canvas.Canvas(buf, pagesize=A4)

    # Every figure is known before any page is drawn, so the whole batch goes
    # through one kaleido call instead of one call per figure.
    chart_images = render_batch([_lot_trend_figure(i) for i in trend.items])

    probe_top = _draw_header(c, page_width, page_height, trend)
    total_pages = count_pages(trend, probe_top)
    logger.info(
        "WAT trend PDF: product=%s months=%d lots=%d items=%d pages=%d",
        trend.product_id, trend.months, len(trend.lots), len(trend.items),
        total_pages,
    )

    page_no = 1

    def end_page() -> float:
        """Footer the current page, start the next, return its content top."""
        nonlocal page_no
        draw_footer(c, page_width, page_no, total_pages)
        c.showPage()
        page_no += 1
        return _draw_header(c, page_width, page_height, trend)

    # --- Item table ---------------------------------------------------------
    y = draw_table_header(c, probe_top)
    if not trend.items:
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(*STATUS_RGB["gray"])
        c.drawString(MARGIN, y, "No WAT data for this period.")
    for item in trend.items:
        if y < PAGE_BREAK_MARGIN:
            y = draw_table_header(c, end_page())
        y = draw_item_row(c, y, item)

    # --- Lot trend charts, 2 per page ---------------------------------------
    for i in range(0, len(chart_images), 2):
        top = end_page()
        chunk = chart_images[i:i + 2]
        cell_h = (top - FOOTER_H - 4 * mm) / 2
        for j, img_bytes in enumerate(chunk):
            img = ImageReader(io.BytesIO(img_bytes))
            c.drawImage(
                img,
                MARGIN, top - (j + 1) * cell_h,
                width=page_width - 2 * MARGIN, height=cell_h - 2 * mm,
                preserveAspectRatio=True, anchor="n", mask="auto",
            )

    draw_footer(c, page_width, page_no, total_pages)
    c.save()
    return buf.getvalue()
```

- [ ] **Step 4: Add the export route**

In `backend/app/routers/wat.py`, extend the imports (`WatTrendExportRequest` from schemas, `generate_wat_trend_pdf` from the new module) and append:

```python
@router.post("/wat/export-trend-pdf")
def wat_export_trend_pdf(req: WatTrendExportRequest) -> Response:
    nickname = nickname_for_product_id(req.product_id) or req.product_id
    try:
        trend = get_wat_trend(nickname, req.product_id, req.months)
        pdf_bytes = generate_wat_trend_pdf(trend)
    except Exception as e:
        logger.error("wat_export_trend_pdf failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    name = f"WAT_TREND_{req.product_id}_{req.months}M"
    headers = {"Content-Disposition": content_disposition(name)}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
```

- [ ] **Step 5: Run the tests**

Run: `cd backend && uv run pytest tests/test_wat_trend_pdf.py tests/test_wat_trend_api.py tests/test_wat_pdf.py -v`
Expected: PASS（kaleido が 30 図を描くので 1 分近くかかることがある）

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/wat_trend_pdf_service.py backend/app/routers/wat.py backend/tests/test_wat_trend_pdf.py backend/tests/test_wat_trend_api.py
git commit -m "feat(wat): add the trend report PDF and its export endpoint"
```

---

### Task 8: フロントエンドの型と API クライアント

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/client.ts`

**Interfaces:**
- Consumes: Task 5 / Task 7 のエンドポイント
- Produces: `WatLotPoint`、`WatTrendItemStats`、`WatTrendResponse`、`fetchWatTrend(productId, months)`、`exportWatTrendPdf(productId, months)`

- [ ] **Step 1: Add the types**

In `frontend/src/types/index.ts`, append after `WatSummaryResponse`:

```ts
export interface WatLotPoint {
  lot_id: string;
  measured_date: string;
  n: number;
  mean: number | null;
  sigma: number | null;
  cpk: number | null;
  cpk_state: WatCpkState;
  status: WatStatus;
}

export interface WatTrendItemStats {
  item_name: string;
  unit: string;
  spec_low: number | null;
  spec_high: number | null;
  n: number;
  mean: number | null;
  sigma: number | null;
  min: number | null;
  max: number | null;
  cpk: number | null;
  cpk_state: WatCpkState;
  oos_count: number;
  oos_pct: number;
  status: WatStatus;
  lot_series: WatLotPoint[];
}

/** `lots` is newest first; each item's `lot_series` is oldest first. */
export interface WatTrendResponse {
  product_id: string;
  display_name: string;
  months: number;
  start_date: string;
  end_date: string;
  lots: WatLotInfo[];
  items: WatTrendItemStats[];
}
```

- [ ] **Step 2: Add the client calls**

In `frontend/src/api/client.ts`, add `WatTrendResponse` to the type import block and append after `exportWatPdf`:

```ts
export async function fetchWatTrend(
  productId: string, months: number
): Promise<WatTrendResponse> {
  const res = await api.get<WatTrendResponse>("/wat/trend", {
    params: { product_id: productId, months },
  });
  return res.data;
}

export async function exportWatTrendPdf(
  productId: string, months: number
): Promise<void> {
  const res = await api.post(
    "/wat/export-trend-pdf",
    { product_id: productId, months },
    { responseType: "blob" },
  );
  const blob = new Blob([res.data], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `WAT_TREND_${productId}_${months}M.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: エラーなし

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/api/client.ts
git commit -m "feat(wat): add trend types and API client calls"
```

---

### Task 9: チャートの汎用化とテーブルのジェネリック化

**Files:**
- Modify: `frontend/src/components/wat/WatItemTrendChart.tsx`
- Modify: `frontend/src/components/wat/WatSummaryTable.tsx`
- Modify: `frontend/src/components/wat/WatSummaryTab.tsx`

このタスクは**単ロットタブの見た目を変えない**。純粋に受け口を広げる変更。

**Interfaces:**
- Produces:
  - `WatItemTrendChart` の props: `{ title: string; points: TrendPoint[]; xTitle: string; specLow: number | null; specHigh: number | null; categoryAxis?: boolean }`
  - `export interface TrendPoint { label: string | number; mean: number | null; sigma: number | null; color?: string }`
  - `WatSummaryTable` の props: `{ items: T[]; renderChart: (item: T) => React.ReactNode }`（`T extends WatTableRow`）
  - `export type WatTableRow = Omit<WatItemStats, "wafer_series">`

> spec §6.4 は `renderChart: (item: WatTableRow) => ReactNode` と書いているが、ここではコンポーネントをジェネリックにして呼び出し側が完全な項目型を受け取れるようにする（`wafer_series` / `lot_series` へアクセスするために毎回キャストするのを避けるため）。テーブル自身は依然としてスカラー列しか読まない。

- [ ] **Step 1: Generalize the chart**

Replace `frontend/src/components/wat/WatItemTrendChart.tsx` with:

```tsx
import Plot from "../PlotlyChart";
import { INK, MUTED_SOFT, SPEC_LINE_COLOR, plotlyBaseLayout } from "../../theme";

export interface TrendPoint {
  /** X value: a wafer number, or a lot id. */
  label: string | number;
  mean: number | null;
  sigma: number | null;
  /** Marker color; defaults to INK. Used to carry a lot's own judgement. */
  color?: string;
}

interface Props {
  title: string;
  points: TrendPoint[];
  xTitle: string;
  specLow: number | null;
  specHigh: number | null;
  /** Lot ids are categories, not numbers — keeps them evenly spaced. */
  categoryAxis?: boolean;
}

/** Means with ±3σ whiskers and the spec limits. One series, so no legend —
 *  the title names it. Shared by the wafer axis (single-lot report) and the
 *  lot axis (trend report); the two must not drift apart. */
export default function WatItemTrendChart({
  title, points, xTitle, specLow, specHigh, categoryAxis = false,
}: Props) {
  const shapes = [];
  const annotations = [];
  for (const [limit, label] of [[specLow, "LSL"], [specHigh, "USL"]] as const) {
    if (limit === null || limit === undefined) continue;
    shapes.push({
      type: "line" as const, xref: "paper" as const, x0: 0, x1: 1,
      y0: limit, y1: limit,
      line: { color: SPEC_LINE_COLOR, width: 1, dash: "dash" as const },
    });
    annotations.push({
      xref: "paper" as const, x: 1, y: limit, xanchor: "left" as const,
      text: label, showarrow: false,
      font: { size: 10, color: SPEC_LINE_COLOR },
    });
  }

  return (
    <Plot
      data={[{
        x: points.map((p) => p.label),
        y: points.map((p) => p.mean),
        type: "scatter",
        mode: "lines+markers",
        line: { color: INK, width: 2 },
        marker: { size: 8, color: points.map((p) => p.color ?? INK) },
        error_y: {
          type: "data",
          array: points.map((p) => (p.sigma === null ? 0 : p.sigma * 3)),
          visible: true,
          color: "rgba(20,20,19,0.35)",
          thickness: 1.2,
          width: 3,
        },
        hovertemplate: "%{x}<br>%{y:.4g}<extra></extra>",
      }]}
      layout={{
        ...plotlyBaseLayout(),
        title: { text: title, font: { size: 13 } },
        height: 300,
        margin: { l: 64, r: 56, t: 40, b: categoryAxis ? 96 : 44 },
        showlegend: false,
        xaxis: {
          title: { text: xTitle, font: { size: 11, color: MUTED_SOFT } },
          gridcolor: "rgba(0,0,0,0.05)",
          zeroline: false,
          ...(categoryAxis ? { type: "category" as const, tickangle: -45 } : {}),
        },
        yaxis: { gridcolor: "rgba(0,0,0,0.05)", zeroline: false },
        shapes,
        annotations,
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: "100%" }}
    />
  );
}
```

- [ ] **Step 2: Make the table generic**

In `frontend/src/components/wat/WatSummaryTable.tsx`:

Replace the import of `WatItemTrendChart` (the table no longer builds charts) and change the header:

```tsx
import { useState } from "react";
import type { WatItemStats } from "../../types";
import { STATUS_COLOR, STATUS_MARK } from "../../theme";
import { tableStyles } from "../../ui/tableStyles";
import { fmtCpk, fmtValue } from "../../ui/format";

/** The scalar columns this table draws. Both the single-lot and the trend
 *  item types satisfy it; neither series field is read here. */
export type WatTableRow = Omit<WatItemStats, "wafer_series">;

interface Props<T extends WatTableRow> {
  items: T[];
  /** Rendered inside the expanded row, under the clicked item. */
  renderChart: (item: T) => React.ReactNode;
}

export default function WatSummaryTable<T extends WatTableRow>(
  { items, renderChart }: Props<T>
) {
```

and replace the expanded-row body:

```tsx
              open ? (
                <tr key={`${item.item_name}-chart`}>
                  <td colSpan={12} style={styles.chartCell}>
                    {renderChart(item)}
                  </td>
                </tr>
              ) : null,
```

Everything else in the file (columns, status colors, open/close state) stays as it is.

- [ ] **Step 3: Update the single-lot caller**

In `frontend/src/components/wat/WatSummaryTab.tsx`, add the import and pass the wafer chart:

```tsx
import WatItemTrendChart from "./WatItemTrendChart";
```

```tsx
          <WatSummaryTable
            items={summary.items}
            renderChart={(item) => (
              <WatItemTrendChart
                title={`${item.item_name}${item.unit ? ` [${item.unit}]` : ""}`}
                points={item.wafer_series.map((w) => ({
                  label: w.wafer_id, mean: w.mean, sigma: w.sigma,
                }))}
                xTitle="Wafer #"
                specLow={item.spec_low}
                specHigh={item.spec_high}
              />
            )}
          />
```

- [ ] **Step 4: Type-check and eyeball the single-lot tab**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: エラーなし

Run the app (`cd frontend && npm run build && cd ../backend && uv run uvicorn app.main:app --port 8000`), open `http://localhost:8000`, go to Report → PCM / WAT, click an item row.
Expected: 展開されるウェハトレンドが変更前と同じに見えること。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/wat/WatItemTrendChart.tsx frontend/src/components/wat/WatSummaryTable.tsx frontend/src/components/wat/WatSummaryTab.tsx
git commit -m "refactor(wat): generalize the trend chart and the summary table"
```

---

### Task 10: トレンドタブと 3 タブ化

**Files:**
- Create: `frontend/src/components/wat/WatTrendTab.tsx`
- Modify: `frontend/src/pages/ReportPage.tsx`

**Interfaces:**
- Consumes: `fetchWatTrend()` / `exportWatTrendPdf()`（Task 8）、`WatSummaryTable` + `WatItemTrendChart`（Task 9）、`STATUS_COLOR` / `STATUS_MARK`（`theme.ts`）
- Produces: `<WatTrendTab productId={string} />`

- [ ] **Step 1: Write the tab**

Create `frontend/src/components/wat/WatTrendTab.tsx`:

```tsx
import { useCallback, useEffect, useRef, useState } from "react";
import { exportWatTrendPdf, fetchWatTrend } from "../../api/client";
import type { WatTrendResponse } from "../../types";
import Button from "../../ui/Button";
import Select from "../../ui/Select";
import { STATUS_COLOR, STATUS_MARK } from "../../theme";
import WatSummaryTable from "./WatSummaryTable";
import WatItemTrendChart from "./WatItemTrendChart";

interface Props {
  productId: string;
}

export default function WatTrendTab({ productId }: Props) {
  const [months, setMonths] = useState(3);
  const [trend, setTrend] = useState<WatTrendResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Guards against out-of-order responses: only the latest request may write
  // state when product or period changes mid-fetch (same idiom as
  // WatSummaryTab's loadSummary).
  const reqIdRef = useRef(0);

  const loadTrend = useCallback(async () => {
    if (!productId) {
      setTrend(null);
      return;
    }
    const id = ++reqIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWatTrend(productId, months);
      if (id !== reqIdRef.current) return; // stale response
      setTrend(res);
    } catch (e) {
      if (id !== reqIdRef.current) return; // stale response
      console.error("Failed to load WAT trend:", e);
      setError("Failed to load WAT trend.");
      setTrend(null);
    } finally {
      if (id === reqIdRef.current) setLoading(false);
    }
  }, [productId, months]);

  useEffect(() => { void loadTrend(); }, [loadTrend]);

  const handleExport = async () => {
    if (!productId) return;
    setExporting(true);
    try {
      await exportWatTrendPdf(productId, months);
    } catch (e) {
      console.error("WAT trend PDF export failed:", e);
      setError("PDF export failed.");
    } finally {
      setExporting(false);
    }
  };

  const reds = trend?.items.filter((i) => i.status === "red").length ?? 0;
  const yellows = trend?.items.filter((i) => i.status === "yellow").length ?? 0;
  const latest = trend?.lots[0]?.last_measured ?? "—";

  return (
    <div>
      <div style={styles.toolbar}>
        <label style={styles.field}>
          <span style={styles.fieldLabel}>Period</span>
          <Select value={String(months)} onChange={(e) => setMonths(Number(e.target.value))}>
            <option value="1">Last 1 month</option>
            <option value="3">Last 3 months</option>
            <option value="6">Last 6 months</option>
          </Select>
        </label>

        <Button onClick={handleExport} disabled={!trend || loading || exporting}>
          {exporting ? "Generating…" : "Export PDF"}
        </Button>
        {exporting && <span style={styles.hint}>One chart per item — this takes a while</span>}
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {loading && <div style={styles.hint}>Loading…</div>}

      {!loading && trend && trend.items.length === 0 && (
        <div style={styles.empty}>No WAT data for this period.</div>
      )}

      {!loading && trend && trend.items.length > 0 && (
        <>
          <div style={styles.header}>
            <strong style={styles.period}>{trend.start_date} — {latest}</strong>
            <span>{trend.lots.length} lots</span>
            <span>{trend.items.length} items</span>
            <span style={styles.counts}>
              <span style={{ color: STATUS_COLOR.red, fontWeight: 600 }}>
                {STATUS_MARK.red} {reds}
              </span>
              <span style={{ color: STATUS_COLOR.yellow, fontWeight: 600 }}>
                {STATUS_MARK.yellow} {yellows}
              </span>
            </span>
          </div>
          <WatSummaryTable
            items={trend.items}
            renderChart={(item) => (
              <WatItemTrendChart
                title={`${item.item_name}${item.unit ? ` [${item.unit}]` : ""}`}
                points={item.lot_series.map((p) => ({
                  label: p.lot_id,
                  mean: p.mean,
                  sigma: p.sigma,
                  color: STATUS_COLOR[p.status],
                }))}
                xTitle="Lot"
                specLow={item.spec_low}
                specHigh={item.spec_high}
                categoryAxis
              />
            )}
          />
        </>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  toolbar: { display: "flex", alignItems: "center", gap: 18, marginBottom: 20, flexWrap: "wrap" },
  field: { display: "inline-flex", alignItems: "center", gap: 8 },
  fieldLabel: {
    fontSize: 11, fontWeight: 600, textTransform: "uppercase",
    letterSpacing: "0.06em", color: "var(--muted-soft)",
  },
  hint: { fontSize: 12, color: "var(--muted-soft)" },
  empty: {
    padding: "28px 0", textAlign: "center",
    color: "var(--muted-soft)", fontSize: 13,
  },
  error: {
    background: "rgba(198, 69, 69, 0.08)", color: "var(--error)",
    padding: "10px 14px", borderRadius: "var(--radius-control)",
    marginBottom: 16, fontSize: 13,
  },
  header: {
    display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap",
    padding: "12px 16px", marginBottom: 16,
    background: "var(--surface-card)", border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    fontSize: 13, color: "var(--muted)",
  },
  period: { color: "var(--ink)", fontSize: 14 },
  counts: { display: "inline-flex", gap: 14, marginLeft: "auto" },
};
```

- [ ] **Step 2: Wire the third tab**

In `frontend/src/pages/ReportPage.tsx`:

Add the import:

```tsx
import WatTrendTab from "../components/wat/WatTrendTab";
```

Widen the tab state:

```tsx
  const [tab, setTab] = useState<"yield" | "wat" | "watTrend">("yield");
```

Extend the tab list:

```tsx
          {([
            ["yield", "Yield Trend"],
            ["wat", "PCM / WAT (Lot)"],
            ["watTrend", "PCM / WAT (Trend)"],
          ] as const).map(([key, label]) => (
```

Replace the content switch at the bottom of `<main>`:

```tsx
        {tab === "yield" && <ReportView data={data} request={request} />}
        {tab === "wat" && <WatSummaryTab productId={productId} />}
        {tab === "watTrend" && <WatTrendTab productId={productId} />}
```

The `tab === "yield"` guard around the Process chips / Generate / Export PDF controls already hides them on both WAT tabs — leave it as it is.

- [ ] **Step 3: Type-check and lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: エラーなし

- [ ] **Step 4: Verify in the running app**

Run: `cd frontend && npm run build && cd ../backend && uv run uvicorn app.main:app --port 8000`
Open `http://localhost:8000` → Report → **PCM / WAT (Trend)**.
Expected:
- Period セレクタと Export PDF だけがツールバーに出る（Lot セレクタは出ない）
- 30 行のテーブルが出て、VTHN_ULVT の行が赤く、RS_NDIFF が黄色
- 行をクリックすると X 軸がロット ID のチャートが開き、LSL/USL 線が出る
- Export PDF がダウンロードされ、表 + 全項目のチャートが入っている

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/wat/WatTrendTab.tsx frontend/src/pages/ReportPage.tsx
git commit -m "feat(wat): add the PCM/WAT trend tab to the Report page"
```

---

### Task 11: ドキュメント更新

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/pcm-wat-summary.md`

**Interfaces:**
- Consumes: 完成した全機能
- Produces: なし（ドキュメントのみ）

- [ ] **Step 1: Update CLAUDE.md**

In the `### PCM/WAT (WAT_MEASURE_DETAIL)` section, append:

```markdown
PCM/WAT は 2 本のレポートに分かれる。**単ロットレポート** (`wat_service.py` /
`wat_pdf_service.py`、`/wat/lots` + `/wat/summary` + `/wat/export-pdf`) は 1 ロット
に閉じ、散布図を持つ。**トレンドレポート** (`wat_trend_service.py` /
`wat_trend_pdf_service.py`、`/wat/trend` + `/wat/export-trend-pdf`) は期間 (既定
3 ヶ月) の全ロットを 1 クエリで読み、**生サイト測定値をプールした**通算統計と
`lot_series` を返す。散布図は持たない。

Cpk / OOS / 判定は `wat_service._item_core()` 1 箇所だけにある。規格値はトレンド側
では**期間全体で 1 度だけ解決**して全ロットに適用する — ロットごとに引き直すと、
チャートの規格線と、その線に対して赤と判定された点が食い違う。

`WatTrendResponse.lots` は新しい順、各項目の `lot_series` は古い順。**逆順なのは
意図的** (前者はヘッダ帯、後者はチャートの X 軸)。

PDF の共通部品 (テーブル列定義・行描画・kaleido 一括描画・ステータス色) は
`wat_pdf_common.py` にある。テーブル描画を各 PDF にコピーしないこと。
```

- [ ] **Step 2: Update docs/pcm-wat-summary.md**

Add a line at the top of that document pointing at the trend report and its spec:

```markdown
> 本書は**単ロットレポート**の仕様。ロット横断のトレンドレポートは
> `docs/superpowers/specs/2026-09-07-pcm-wat-trend-report-design.md` を参照。
```

- [ ] **Step 3: Run the full suite one more time**

Run: `cd backend && uv run pytest -q && cd ../frontend && npx tsc --noEmit && npm run lint`
Expected: すべて PASS

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/pcm-wat-summary.md
git commit -m "docs(wat): document the single-lot / trend report split"
```
