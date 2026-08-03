# PCM/WAT ロットサマリー Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Report ページに 2 つ目のタブを追加し、選択した 1 ロットの WAT パラメトリック測定サマリー（項目別統計・ウェハ別トレンド・Vth/Idsat 散布図）を表示し、A4 縦の PDF として出力できるようにする。

**Architecture:** 既存の Wafer Map 機能と同じ三層（`wat_queries.py` → `wat_service.py` → `routers/wat.py`）。統計計算はすべてバックエンドで完結させ、画面と PDF が同一の数値を使う。PDF は `wat_pdf_service.py` に分け、既存 `pdf_service.py` と共有するブランディング部品だけを `pdf_common.py` に切り出す。

**Tech Stack:** FastAPI / pandas / oracledb (thin) / ReportLab + kaleido / React 19 + Vite / react-plotly.js

**Spec:** `docs/superpowers/specs/2026-07-28-pcm-wat-lot-summary-design.md`

## Global Constraints

- データソースは `WAT_MEASURE_DETAIL`。`PRODUCT_ID` には既存 `product_config.yaml` の `product_id` と**同じ値**が入る
- `DEL_FLAG` / `REWORK_NEW` / `REWORK_CNT` では**フィルタしない**（この工程は rework 運用がない）
- すべての表示・集計・PDF は**単一ロットに閉じる**。期間横断の集計は行わない
- 統計の母集団は生の測定値全件（ウェハ × サイト）。`MEAS_DATA` が NULL の行は N から除外
- 規格外の判定は `value < SPEC_LOW` または `value > SPEC_HIGH`。**規格値ちょうどは規格内**
- Cpk は `cpk`（`number | null`）と `cpk_state`（`"value"` / `"infinite"` / `"undefined"`）の 2 フィールドで返す
- 判定は上から順に評価し最初に該当したものを採用する: ①規格外 1 件以上 or (`cpk_state == "value"` かつ `cpk < 1.00`) → `red` ②`cpk_state == "value"` かつ `1.00 <= cpk < 1.33` → `yellow` ③`cpk_state == "undefined"` → `gray` ④それ以外 → `ok`
- 判定は**色と記号の両方**で表す（`red`=`●` / `yellow`=`▲` / `gray`=`–` / `ok`=空）。PDF の白黒印刷で色が失われるため記号は必須
- テーブルの並びは `ITEM_NAME` **昇順の固定順**
- 数値表示は有効数字 4 桁（`%.4g`）。`n` / `oos_count` は整数、`cpk` は小数 2 桁
- 既存の Yield Trend タブの挙動は**一切変更しない**
- `USE_MOCK_DATA=true`（既定）で Oracle なしに全機能が動くこと
- 既存テストを壊さないこと（現在 76 件が通っている）

## File Structure

**Backend（新規）**

| ファイル | 責務 |
| --- | --- |
| `app/services/wat_queries.py` | SQL 組み立てと実行 → DataFrame |
| `app/services/wat_service.py` | 統計集計・判定・散布図ペアリング・モック分岐 |
| `app/services/pdf_common.py` | ブランディング定数 / ロゴ / フッタ / 余白定数の共有 |
| `app/services/wat_pdf_service.py` | WAT の PDF 生成（A4 縦） |
| `app/routers/wat.py` | エンドポイント 3 本 |
| `tests/test_wat_config.py` | `wat:` ブロックの読み出し |
| `tests/test_wat_mock.py` | モックの決定性と形 |
| `tests/test_wat_queries.py` | SQL 組み立て |
| `tests/test_wat_stats.py` | Cpk・判定・規格解決 |
| `tests/test_wat_scatter.py` | 散布図ペアリング |
| `tests/test_wat_api.py` | ルータの疎通 |
| `tests/test_wat_pdf.py` | PDF 生成スモーク |

**Backend（変更）**

| ファイル | 変更内容 |
| --- | --- |
| `app/services/product_config.py` | `wat:` の parse と `resolve_wat_pairs()` |
| `app/services/mock_data.py` | `mock_wat_lots()` / `mock_wat_dataframe()` |
| `app/models/schemas.py` | WAT レスポンス型 |
| `app/services/pdf_service.py` | 共通部品を `pdf_common.py` から import |
| `app/main.py` | `wat` ルータ登録 |
| `product_config.yaml.example` | `wat:` の記述例 |

**Frontend（新規）**

| ファイル | 責務 |
| --- | --- |
| `src/components/wat/WatSummaryTab.tsx` | タブ全体（ロット選択・取得・レイアウト） |
| `src/components/wat/WatSummaryTable.tsx` | 項目別テーブルと行展開 |
| `src/components/wat/WatItemTrendChart.tsx` | ウェハ別トレンド |
| `src/components/wat/WatScatterGrid.tsx` | フレーバー切替 + 散布図 4 図 |

**Frontend（変更）**

| ファイル | 変更内容 |
| --- | --- |
| `src/pages/ReportPage.tsx` | タブ切替の追加のみ |
| `src/api/client.ts` | WAT の 3 関数 |
| `src/types.ts` | WAT の型 |
| `src/theme.ts` | ウェハ配色ランプと判定色 |

---

### Task 1: `product_config.yaml` の `wat:` ブロック読み出し

**Files:**
- Modify: `backend/app/services/product_config.py`
- Modify: `backend/product_config.yaml.example`
- Test: `backend/tests/test_wat_config.py`

**Interfaces:**
- Consumes: 既存の `_config_from_yaml()` / `load_product_config()`
- Produces: `resolve_wat_pairs(nickname: str) -> list[dict]`。各要素は
  `{"label": str, "vth_n": str, "vth_p": str, "idsat_n": str, "idsat_p": str}`。
  設定が無い・壊れている場合は空リスト

- [ ] **Step 1: 失敗するテストを書く**

`backend/tests/test_wat_config.py` を新規作成:

```python
import json

from app.services.product_config import _parse_wat_pairs, resolve_wat_pairs


def test_parse_wat_pairs_reads_labels_and_items():
    raw = {
        "pairs": [
            {"label": "Core RVT",
             "vth": {"n": "VTHN_RVT", "p": "VTHP_RVT"},
             "idsat": {"n": "IDSATN_RVT", "p": "IDSATP_RVT"}},
        ]
    }
    pairs = _parse_wat_pairs(raw, "prod_a")
    assert pairs == [{
        "label": "Core RVT",
        "vth_n": "VTHN_RVT", "vth_p": "VTHP_RVT",
        "idsat_n": "IDSATN_RVT", "idsat_p": "IDSATP_RVT",
    }]


def test_parse_wat_pairs_preserves_declaration_order():
    raw = {"pairs": [
        {"label": "B", "vth": {"n": "a", "p": "b"}, "idsat": {"n": "c", "p": "d"}},
        {"label": "A", "vth": {"n": "e", "p": "f"}, "idsat": {"n": "g", "p": "h"}},
    ]}
    assert [p["label"] for p in _parse_wat_pairs(raw, "prod_a")] == ["B", "A"]


def test_parse_wat_pairs_skips_incomplete_entry(caplog):
    raw = {"pairs": [
        {"label": "Broken", "vth": {"n": "VTHN"}, "idsat": {"n": "I", "p": "J"}},
        {"label": "Good", "vth": {"n": "a", "p": "b"}, "idsat": {"n": "c", "p": "d"}},
    ]}
    with caplog.at_level("WARNING"):
        pairs = _parse_wat_pairs(raw, "prod_a")
    assert [p["label"] for p in pairs] == ["Good"]
    assert "Broken" in caplog.text


def test_parse_wat_pairs_missing_block_returns_empty():
    assert _parse_wat_pairs(None, "prod_a") == []
    assert _parse_wat_pairs({}, "prod_a") == []
    assert _parse_wat_pairs({"pairs": "not-a-list"}, "prod_a") == []


def test_parse_wat_pairs_defaults_label_when_absent():
    raw = {"pairs": [{"vth": {"n": "a", "p": "b"}, "idsat": {"n": "c", "p": "d"}}]}
    assert _parse_wat_pairs(raw, "prod_a")[0]["label"] == "pair1"


def test_resolve_wat_pairs_unknown_nickname_is_empty():
    assert resolve_wat_pairs("__no_such_product__") == []


def test_resolve_wat_pairs_parses_stored_json(monkeypatch):
    import app.services.product_config as pc
    stored = json.dumps([{"label": "X", "vth_n": "a", "vth_p": "b",
                          "idsat_n": "c", "idsat_p": "d"}])
    monkeypatch.setattr(pc, "load_product_config", lambda: {"p": {"wat": stored}})
    assert pc.resolve_wat_pairs("p")[0]["label"] == "X"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd backend && uv run python -m pytest tests/test_wat_config.py -v`
Expected: FAIL — `ImportError: cannot import name '_parse_wat_pairs'`

- [ ] **Step 3: `_parse_wat_pairs` を実装**

`backend/app/services/product_config.py` の `_parse_target` の直後に追加:

```python
def _parse_wat_pairs(raw, nickname: str) -> list[dict]:
    """Parse the `wat:` block into a flat list of device-flavor pairs.

    Shape:
        wat:
          pairs:
            - label: Core RVT
              vth:   {n: VTHN_RVT, p: VTHP_RVT}
              idsat: {n: IDSATN_RVT, p: IDSATP_RVT}

    Returns [] when the block is absent or unusable — the scatter section is
    simply omitted for that product rather than erroring.
    """
    if not isinstance(raw, dict):
        return []
    pairs = raw.get("pairs")
    if not isinstance(pairs, list):
        return []

    out: list[dict] = []
    for i, entry in enumerate(pairs):
        label = f"pair{i + 1}"
        if not isinstance(entry, dict):
            logger.warning(
                "product_config[%s].wat.pairs[%d] is not a mapping; skipped", nickname, i
            )
            continue
        label = str(entry.get("label") or label).strip() or label
        vth = entry.get("vth") if isinstance(entry.get("vth"), dict) else {}
        idsat = entry.get("idsat") if isinstance(entry.get("idsat"), dict) else {}
        pair = {
            "label": label,
            "vth_n": str(vth.get("n") or "").strip(),
            "vth_p": str(vth.get("p") or "").strip(),
            "idsat_n": str(idsat.get("n") or "").strip(),
            "idsat_p": str(idsat.get("p") or "").strip(),
        }
        missing = [k for k in ("vth_n", "vth_p", "idsat_n", "idsat_p") if not pair[k]]
        if missing:
            logger.warning(
                "product_config[%s].wat.pairs[%s] missing %s; skipped",
                nickname, label, ", ".join(missing),
            )
            continue
        out.append(pair)
    return out
```

`_config_from_yaml()` の `row["report"] = json.dumps(report_units)` の直後に追加:

```python
        row["wat"] = json.dumps(_parse_wat_pairs(entry.get("wat"), name))
```

`resolve_report_unit` の直後に追加:

```python
def resolve_wat_pairs(nickname: str) -> list[dict]:
    """Device-flavor pairs for the PCM/WAT scatter plots, in declaration order."""
    config = load_product_config() or {}
    raw = (config.get(nickname) or {}).get("wat") or "[]"
    try:
        pairs = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("product_config[%s].wat is not valid JSON; ignored", nickname)
        return []
    return pairs if isinstance(pairs, list) else []
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd backend && uv run python -m pytest tests/test_wat_config.py -v`
Expected: PASS（新規テストが全件 green）

- [ ] **Step 5: `product_config.yaml.example` に記述例を追加**

ファイル末尾に追加:

```yaml
#
# wat (optional — PCM/WAT tab の散布図に必要)
# ─────────────────────────────────────────────────────────────────
#   WAT_MEASURE_DETAIL.ITEM_NAME の命名は製品ごとに違うため、散布図で
#   使う Vth / Idsat の N・P 項目名をここで対応付ける。
#   pairs は宣言順に表示され、1 組につき 4 図（Vth n/p, Idsat n/p,
#   Ion-Vt N, Ion-Vt P）を描く。
#   このブロックを省くと散布図セクションごと非表示になる
#   （サマリーテーブルは通常どおり表示される）。
#
#   wat:
#     pairs:
#       - label: Core RVT
#         vth:   {n: VTHN_RVT,   p: VTHP_RVT}
#         idsat: {n: IDSATN_RVT, p: IDSATP_RVT}
#       - label: Core LVT
#         vth:   {n: VTHN_LVT,   p: VTHP_LVT}
#         idsat: {n: IDSATN_LVT, p: IDSATP_LVT}
```

- [ ] **Step 6: 既存テストが壊れていないことを確認**

Run: `cd backend && uv run python -m pytest tests/ -q`
Expected: 失敗 0（既存分がすべて残っていること）

- [ ] **Step 7: コミット**

```bash
git add backend/app/services/product_config.py backend/product_config.yaml.example backend/tests/test_wat_config.py
git commit -m "feat(wat): read wat: device-flavor pairs from product_config"
```

---

### Task 2: WAT モックデータ

**Files:**
- Modify: `backend/app/services/mock_data.py`
- Test: `backend/tests/test_wat_mock.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `mock_wat_lots(product_id: str, months: int) -> pd.DataFrame` — 列 `["lot_id", "last_measured", "wafer_count"]`、`last_measured` は ISO 日付文字列、**古い順**（降順への並べ替えは呼び出し側の責務）
  - `mock_wat_dataframe(product_id: str, lot_id: str) -> pd.DataFrame` — 列 `["wafer_id", "site_no", "item_name", "item_unit", "spec_low", "spec_high", "meas_data", "start_time"]`。`start_time` はそのロットの測定日（ISO 文字列）で全行同値
  - `MOCK_WAT_FLAVORS: list[str]` — `["RVT", "LVT", "HVT", "ULVT", "IO25", "IO18"]`。項目名は `VTHN_<flavor>` / `VTHP_<flavor>` / `IDSATN_<flavor>` / `IDSATP_<flavor>`

- [ ] **Step 1: 失敗するテストを書く**

`backend/tests/test_wat_mock.py` を新規作成:

```python
import pandas as pd

from app.services.mock_data import (
    MOCK_WAT_FLAVORS, mock_wat_dataframe, mock_wat_lots,
)

WAT_DETAIL_COLUMNS = [
    "wafer_id", "site_no", "item_name", "item_unit",
    "spec_low", "spec_high", "meas_data", "start_time",
]


def test_mock_wat_lots_shape_and_determinism():
    a = mock_wat_lots("P12345-A", 3)
    b = mock_wat_lots("P12345-A", 3)
    assert list(a.columns) == ["lot_id", "last_measured", "wafer_count"]
    assert a.equals(b)
    assert len(a) >= 3
    # oldest first — the router is what reverses
    assert list(a["last_measured"]) == sorted(a["last_measured"])


def test_mock_wat_lots_differ_per_product():
    a = mock_wat_lots("P12345-A", 3)
    b = mock_wat_lots("P12345-B", 3)
    assert set(a["lot_id"]) != set(b["lot_id"])


def test_mock_wat_dataframe_shape_and_determinism():
    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[0]
    a = mock_wat_dataframe("P12345-A", lot)
    b = mock_wat_dataframe("P12345-A", lot)
    assert list(a.columns) == WAT_DETAIL_COLUMNS
    assert a.equals(b)
    assert a["wafer_id"].nunique() == 25
    assert a["site_no"].nunique() == 9


def test_mock_wat_dataframe_covers_every_flavor():
    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[0]
    df = mock_wat_dataframe("P12345-A", lot)
    names = set(df["item_name"])
    for flavor in MOCK_WAT_FLAVORS:
        for prefix in ("VTHN", "VTHP", "IDSATN", "IDSATP"):
            assert f"{prefix}_{flavor}" in names


def test_mock_wat_dataframe_has_spec_and_units():
    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[0]
    df = mock_wat_dataframe("P12345-A", lot)
    vth = df[df["item_name"] == "VTHN_RVT"]
    assert vth["item_unit"].iloc[0] == "V"
    # spec is constant within an item
    assert vth["spec_low"].nunique() == 1
    assert vth["spec_high"].nunique() == 1


def test_mock_wat_dataframe_contains_out_of_spec_and_low_cpk():
    """Mock must exercise the red/yellow rendering paths without a real DB."""
    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[0]
    df = mock_wat_dataframe("P12345-A", lot)
    oos = df[(df["meas_data"] < df["spec_low"]) | (df["meas_data"] > df["spec_high"])]
    assert not oos.empty, "mock must include out-of-spec measurements"


def test_mock_wat_dataframe_unknown_lot_is_empty():
    df = mock_wat_dataframe("P12345-A", "__no_such_lot__")
    assert df.empty
    assert list(df.columns) == WAT_DETAIL_COLUMNS
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd backend && uv run python -m pytest tests/test_wat_mock.py -v`
Expected: FAIL — `ImportError: cannot import name 'MOCK_WAT_FLAVORS'`

- [ ] **Step 3: モック生成を実装**

`backend/app/services/mock_data.py` の末尾に追加（`import hashlib, random` と `pandas as pd`、`from datetime import date, timedelta` は既に上部にある）:

```python
# ---------------------------------------------------------------------------
# PCM / WAT mock
# ---------------------------------------------------------------------------

MOCK_WAT_FLAVORS: list[str] = ["RVT", "LVT", "HVT", "ULVT", "IO25", "IO18"]

WAT_DETAIL_COLUMNS = [
    "wafer_id", "site_no", "item_name", "item_unit",
    "spec_low", "spec_high", "meas_data", "start_time",
]

WAT_LOT_COLUMNS = ["lot_id", "last_measured", "wafer_count"]

# (item suffix, unit, center, spread, spec half-width) per flavor family.
# Vth centers differ per flavor so the Ion-Vt clusters separate visibly.
_WAT_VTH_CENTER = {"RVT": 0.45, "LVT": 0.32, "HVT": 0.58,
                   "ULVT": 0.24, "IO25": 0.70, "IO18": 0.62}
_WAT_IDSAT_CENTER = {"RVT": 620.0, "LVT": 780.0, "HVT": 480.0,
                     "ULVT": 880.0, "IO25": 340.0, "IO18": 400.0}

# Extra non-paired items so the summary table is not only Vth/Idsat.
_WAT_MISC_ITEMS = [
    ("RS_POLY", "Ohm/sq", 1040.0, 20.0, None, None),
    ("RS_NDIFF", "Ohm/sq", 78.0, 2.5, 68.0, 88.0),
    ("RS_PDIFF", "Ohm/sq", 132.0, 4.0, 118.0, 146.0),
    ("CAP_MIM", "fF/um2", 2.05, 0.04, 1.90, 2.20),
    ("VIA_CHAIN_R", "Ohm", 1.85, 0.09, 1.50, 2.20),
    ("GATE_OX_TOX", "nm", 2.20, 0.05, 2.05, 2.35),
]


def _wat_seed(*parts: str) -> int:
    return int(hashlib.md5("|".join(parts).encode()).hexdigest(), 16) % 2**32


def mock_wat_lots(product_id: str, months: int) -> pd.DataFrame:
    """Deterministic WAT lot list for a product, oldest first.

    Callers order for display; the API returns newest first.
    """
    rng = random.Random(_wat_seed("wat-lots", product_id, str(months)))
    today = date.today()
    start = today - timedelta(days=months * 30)

    rows: list[dict] = []
    cur = start
    seq = 0
    while cur <= today:
        seq += 1
        rows.append({
            "lot_id": f"WAT{product_id[:4].upper()}-{cur.strftime('%y%m%d')}-{seq:03d}",
            "last_measured": cur.isoformat(),
            "wafer_count": 25,
        })
        cur += timedelta(days=rng.randint(5, 12))

    return pd.DataFrame(rows, columns=WAT_LOT_COLUMNS)


def mock_wat_dataframe(product_id: str, lot_id: str) -> pd.DataFrame:
    """Deterministic per-site WAT measurements for one lot.

    25 wafers x 9 sites x (6 flavors x 4 items + 6 misc items) = 30 items.
    Two items are deliberately degraded so the red/yellow paths render in
    mock mode: VTHN_ULVT drifts out of spec (red) and RS_NDIFF is given a
    wide spread that lands its Cpk between 1.00 and 1.33 (yellow).
    """
    lots = mock_wat_lots(product_id, 6)
    match = lots[lots["lot_id"] == lot_id]
    if match.empty:
        return pd.DataFrame(columns=WAT_DETAIL_COLUMNS)
    start_time = str(match["last_measured"].iloc[0])

    rng = random.Random(_wat_seed("wat-detail", product_id, lot_id))

    specs: list[tuple] = []
    for flavor in MOCK_WAT_FLAVORS:
        vc = _WAT_VTH_CENTER[flavor]
        ic = _WAT_IDSAT_CENTER[flavor]
        specs.append((f"VTHN_{flavor}", "V", vc, 0.018, vc - 0.07, vc + 0.07))
        specs.append((f"VTHP_{flavor}", "V", -vc, 0.018, -vc - 0.07, -vc + 0.07))
        specs.append((f"IDSATN_{flavor}", "uA/um", ic, ic * 0.03, ic * 0.88, ic * 1.12))
        specs.append((f"IDSATP_{flavor}", "uA/um", ic * 0.45, ic * 0.014,
                      ic * 0.45 * 0.88, ic * 0.45 * 1.12))
    specs.extend(_WAT_MISC_ITEMS)

    rows: list[dict] = []
    for item_name, unit, center, spread, spec_low, spec_high in specs:
        # Deliberate defects so mock exercises red / yellow rendering.
        if item_name == "VTHN_ULVT":
            center += spread * 3.2       # pushes tail past the upper spec → red
        if item_name == "RS_NDIFF":
            spread *= 2.6                # widens sigma → Cpk lands in [1.00, 1.33)
        for wafer_id in range(1, 26):
            wafer_bias = rng.gauss(0, spread * 0.35)
            for site_no in range(1, 10):
                rows.append({
                    "wafer_id": wafer_id,
                    "site_no": site_no,
                    "item_name": item_name,
                    "item_unit": unit,
                    "spec_low": spec_low,
                    "spec_high": spec_high,
                    "meas_data": center + wafer_bias + rng.gauss(0, spread),
                    "start_time": start_time,
                })

    return pd.DataFrame(rows, columns=WAT_DETAIL_COLUMNS)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd backend && uv run python -m pytest tests/test_wat_mock.py -v`
Expected: PASS（新規テストが全件 green）

`test_mock_wat_dataframe_contains_out_of_spec_and_low_cpk` が失敗する場合は `VTHN_ULVT` の `center` 加算係数（`3.2`）を上げて調整する。**乱数を無効化してはならない** — 実データに近い分布のままで規格外が出ることが確認したい性質。

- [ ] **Step 5: 全テストを実行**

Run: `cd backend && uv run python -m pytest tests/ -q`
Expected: 失敗 0

- [ ] **Step 6: コミット**

```bash
git add backend/app/services/mock_data.py backend/tests/test_wat_mock.py
git commit -m "feat(wat): deterministic WAT mock data with seeded defects"
```

---

### Task 3: WAT クエリ層

**Files:**
- Create: `backend/app/services/wat_queries.py`
- Test: `backend/tests/test_wat_queries.py`

**Interfaces:**
- Consumes: `app.database.get_connection` / `release_connection`（既存）
- Produces:
  - `WAT_TABLE = "WAT_MEASURE_DETAIL"`
  - `WAT_DETAIL_COLUMNS` / `WAT_LOT_COLUMNS`（Task 2 と同じ並び）
  - `build_wat_lots_query(product_id: str, start: date, end: date) -> tuple[str, dict]`
  - `build_wat_detail_query(product_id: str, lot_id: str) -> tuple[str, dict]`
  - `query_wat_lots(product_id, start, end) -> pd.DataFrame`
  - `query_wat_detail(product_id, lot_id) -> pd.DataFrame`

- [ ] **Step 1: 失敗するテストを書く**

`backend/tests/test_wat_queries.py` を新規作成:

```python
from datetime import date

from app.services.wat_queries import (
    WAT_DETAIL_COLUMNS, WAT_LOT_COLUMNS, WAT_TABLE,
    build_wat_detail_query, build_wat_lots_query,
)


def test_lots_query_binds_product_and_period():
    sql, binds = build_wat_lots_query("P12345-A", date(2026, 5, 1), date(2026, 7, 29))
    assert WAT_TABLE in sql
    assert binds == {"pid": "P12345-A", "start": date(2026, 5, 1), "end": date(2026, 7, 29)}
    assert ":pid" in sql and ":start" in sql and ":end" in sql


def test_lots_query_upper_bound_is_exclusive():
    sql, _ = build_wat_lots_query("P", date(2026, 1, 1), date(2026, 2, 1))
    assert "START_TIME >= :start" in sql
    assert "START_TIME <  :end" in sql or "START_TIME < :end" in sql


def test_lots_query_orders_newest_last_by_max_start_time():
    sql, _ = build_wat_lots_query("P", date(2026, 1, 1), date(2026, 2, 1))
    assert "GROUP BY LOT_ID" in sql
    assert "ORDER BY MAX(START_TIME)" in sql


def test_lots_query_column_order_matches_select():
    sql, _ = build_wat_lots_query("P", date(2026, 1, 1), date(2026, 2, 1))
    select_body = sql.split("FROM")[0]
    for i, col in enumerate(WAT_LOT_COLUMNS):
        assert col in select_body, f"{col} missing from SELECT"


def test_detail_query_binds_product_and_lot():
    sql, binds = build_wat_detail_query("P12345-A", "LOT-1")
    assert binds == {"pid": "P12345-A", "lot": "LOT-1"}
    assert "PRODUCT_ID = :pid" in sql
    assert "LOT_ID = :lot" in sql


def test_detail_query_does_not_filter_rework_or_del_flag():
    """This process has no rework; filtering would silently drop valid rows."""
    sql, _ = build_wat_detail_query("P", "L")
    assert "REWORK" not in sql.upper()
    assert "DEL_FLAG" not in sql.upper()


def test_detail_query_column_order_matches_select():
    sql, _ = build_wat_detail_query("P", "L")
    select_body = sql.split("FROM")[0]
    positions = [select_body.index(col) for col in WAT_DETAIL_COLUMNS]
    assert positions == sorted(positions), "SELECT order must match WAT_DETAIL_COLUMNS"


def test_empty_inputs_produce_no_sql():
    assert build_wat_lots_query("", date(2026, 1, 1), date(2026, 2, 1)) == ("", {})
    assert build_wat_detail_query("P", "") == ("", {})
    assert build_wat_detail_query("", "L") == ("", {})
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd backend && uv run python -m pytest tests/test_wat_queries.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.wat_queries'`

- [ ] **Step 3: `wat_queries.py` を実装**

`backend/app/services/wat_queries.py` を新規作成:

```python
"""PCM/WAT queries against WAT_MEASURE_DETAIL.

Single-table reads. This process has no rework operation, so neither
REWORK_NEW nor DEL_FLAG is filtered here — unlike the SEMI_CP_* pair, where
REWORK_NEW = 0 must be applied on BOTH tables (see CLAUDE.md).
"""

import logging
from datetime import date

import pandas as pd

from app.database import get_connection, release_connection

logger = logging.getLogger(__name__)

WAT_TABLE = "WAT_MEASURE_DETAIL"

# Column names in the SAME order as the SELECT below (pandas labels
# positionally — keep aligned).
WAT_LOT_COLUMNS = ["lot_id", "last_measured", "wafer_count"]

# start_time rides along on every detail row so the summary can report the
# lot's measured date without issuing a second GROUP BY query.
WAT_DETAIL_COLUMNS = [
    "wafer_id", "site_no", "item_name", "item_unit",
    "spec_low", "spec_high", "meas_data", "start_time",
]


def build_wat_lots_query(product_id: str, start: date, end: date) -> tuple[str, dict]:
    """Lots measured in [start, end). The upper bound is exclusive so the
    caller can pass tomorrow's date and still include everything measured
    today."""
    if not product_id:
        return "", {}
    sql = f"""
        SELECT LOT_ID                   AS lot_id,
               MAX(START_TIME)          AS last_measured,
               COUNT(DISTINCT WAFER_ID) AS wafer_count
        FROM {WAT_TABLE}
        WHERE PRODUCT_ID = :pid
          AND START_TIME >= :start
          AND START_TIME <  :end
        GROUP BY LOT_ID
        ORDER BY MAX(START_TIME)
    """
    return sql, {"pid": product_id, "start": start, "end": end}


def build_wat_detail_query(product_id: str, lot_id: str) -> tuple[str, dict]:
    """Every measurement of one lot. Aggregation happens in pandas."""
    if not product_id or not lot_id:
        return "", {}
    sql = f"""
        SELECT WAFER_ID   AS wafer_id,
               SITE_NO    AS site_no,
               ITEM_NAME  AS item_name,
               ITEM_UNIT  AS item_unit,
               SPEC_LOW   AS spec_low,
               SPEC_HIGH  AS spec_high,
               MEAS_DATA  AS meas_data,
               START_TIME AS start_time
        FROM {WAT_TABLE}
        WHERE PRODUCT_ID = :pid
          AND LOT_ID = :lot
        ORDER BY item_name, wafer_id, site_no
    """
    return sql, {"pid": product_id, "lot": lot_id}


def _run(sql: str, binds: dict, columns: list[str], what: str) -> pd.DataFrame:
    if not sql:
        return pd.DataFrame(columns=columns)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, binds)
        rows = cursor.fetchall()
        logger.info("WAT %s query returned %d rows", what, len(rows))
        return pd.DataFrame(rows, columns=columns)
    finally:
        release_connection(conn)


def query_wat_lots(product_id: str, start: date, end: date) -> pd.DataFrame:
    sql, binds = build_wat_lots_query(product_id, start, end)
    return _run(sql, binds, WAT_LOT_COLUMNS, "lots")


def query_wat_detail(product_id: str, lot_id: str) -> pd.DataFrame:
    sql, binds = build_wat_detail_query(product_id, lot_id)
    return _run(sql, binds, WAT_DETAIL_COLUMNS, "detail")
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd backend && uv run python -m pytest tests/test_wat_queries.py -v`
Expected: PASS（新規テストが全件 green）

- [ ] **Step 5: コミット**

```bash
git add backend/app/services/wat_queries.py backend/tests/test_wat_queries.py
git commit -m "feat(wat): WAT_MEASURE_DETAIL query layer"
```

---

### Task 4: 統計コア（Cpk・判定・規格解決）

**Files:**
- Create: `backend/app/services/wat_service.py`
- Test: `backend/tests/test_wat_stats.py`

**Interfaces:**
- Consumes: なし（純粋関数のみ。DB もモックもまだ触らない）
- Produces:
  - `CPK_RED = 1.00` / `CPK_YELLOW = 1.33`
  - `compute_cpk(mean, sigma, spec_low, spec_high, n, oos_count) -> tuple[float | None, str]`
  - `classify_status(cpk, cpk_state, oos_count) -> str` — `"red"` / `"yellow"` / `"gray"` / `"ok"`
  - `resolve_spec(series: pd.Series, item_name: str) -> float | None`
  - `count_out_of_spec(values: pd.Series, spec_low, spec_high) -> int`
  - `compute_item_stats(group: pd.DataFrame, item_name: str) -> dict` — 1 項目分の統計 dict

- [ ] **Step 1: 失敗するテストを書く**

`backend/tests/test_wat_stats.py` を新規作成:

```python
import math

import pandas as pd
import pytest

from app.services.wat_service import (
    classify_status, compute_cpk, compute_item_stats,
    count_out_of_spec, resolve_spec,
)


# --- compute_cpk -----------------------------------------------------------

def test_cpk_two_sided_uses_the_worse_side():
    # mean 0.45, sigma 0.02 → upper (0.52-0.45)/0.06 = 1.167
    #                         lower (0.45-0.38)/0.06 = 1.167
    cpk, state = compute_cpk(0.45, 0.02, 0.38, 0.52, n=100, oos_count=0)
    assert state == "value"
    assert cpk == pytest.approx(1.1667, rel=1e-3)


def test_cpk_two_sided_picks_the_nearer_limit():
    cpk, state = compute_cpk(0.50, 0.02, 0.38, 0.52, n=100, oos_count=0)
    assert state == "value"
    assert cpk == pytest.approx((0.52 - 0.50) / 0.06, rel=1e-6)


def test_cpk_upper_only():
    cpk, state = compute_cpk(10.0, 1.0, None, 16.0, n=100, oos_count=0)
    assert state == "value"
    assert cpk == pytest.approx(2.0)


def test_cpk_lower_only():
    cpk, state = compute_cpk(10.0, 1.0, 4.0, None, n=100, oos_count=0)
    assert state == "value"
    assert cpk == pytest.approx(2.0)


def test_cpk_no_spec_is_undefined():
    assert compute_cpk(1.0, 0.1, None, None, n=100, oos_count=0) == (None, "undefined")


def test_cpk_zero_sigma_in_spec_is_infinite():
    assert compute_cpk(0.45, 0.0, 0.38, 0.52, n=100, oos_count=0) == (None, "infinite")


def test_cpk_zero_sigma_out_of_spec_is_undefined():
    assert compute_cpk(0.90, 0.0, 0.38, 0.52, n=100, oos_count=5) == (None, "undefined")


def test_cpk_needs_at_least_two_samples():
    assert compute_cpk(0.45, 0.0, 0.38, 0.52, n=1, oos_count=0) == (None, "undefined")


def test_cpk_nan_sigma_is_undefined():
    assert compute_cpk(0.45, float("nan"), 0.38, 0.52, n=100, oos_count=0) == (None, "undefined")


# --- classify_status -------------------------------------------------------

def test_status_red_when_any_measurement_out_of_spec():
    assert classify_status(2.5, "value", oos_count=1) == "red"


def test_status_red_when_cpk_below_one():
    assert classify_status(0.99, "value", oos_count=0) == "red"


def test_status_boundary_cpk_exactly_one_is_yellow_not_red():
    assert classify_status(1.00, "value", oos_count=0) == "yellow"


def test_status_boundary_cpk_exactly_133_is_ok_not_yellow():
    assert classify_status(1.33, "value", oos_count=0) == "ok"


def test_status_yellow_between_thresholds():
    assert classify_status(1.32, "value", oos_count=0) == "yellow"


def test_status_gray_when_cpk_undefined():
    assert classify_status(None, "undefined", oos_count=0) == "gray"


def test_status_out_of_spec_beats_undefined_cpk():
    """n<2 with a failing measurement must read red, not gray."""
    assert classify_status(None, "undefined", oos_count=1) == "red"


def test_status_infinite_cpk_is_ok():
    assert classify_status(None, "infinite", oos_count=0) == "ok"


# --- count_out_of_spec -----------------------------------------------------

def test_out_of_spec_excludes_values_exactly_on_the_limit():
    s = pd.Series([0.38, 0.52, 0.45])
    assert count_out_of_spec(s, 0.38, 0.52) == 0


def test_out_of_spec_counts_both_tails():
    s = pd.Series([0.37, 0.45, 0.53])
    assert count_out_of_spec(s, 0.38, 0.52) == 2


def test_out_of_spec_one_sided_uses_only_the_present_limit():
    s = pd.Series([0.01, 0.45, 99.0])
    assert count_out_of_spec(s, None, 0.52) == 1
    assert count_out_of_spec(s, 0.38, None) == 1


def test_out_of_spec_without_spec_is_zero():
    assert count_out_of_spec(pd.Series([1.0, 2.0]), None, None) == 0


# --- resolve_spec ----------------------------------------------------------

def test_resolve_spec_returns_the_single_value():
    assert resolve_spec(pd.Series([0.38, 0.38, 0.38]), "VTH_N") == 0.38


def test_resolve_spec_ignores_nulls():
    assert resolve_spec(pd.Series([None, 0.38, None]), "VTH_N") == 0.38


def test_resolve_spec_all_null_is_none():
    assert resolve_spec(pd.Series([None, None]), "VTH_N") is None


def test_resolve_spec_takes_the_mode_and_warns_on_mixed(caplog):
    s = pd.Series([0.38, 0.38, 0.40])
    with caplog.at_level("WARNING"):
        assert resolve_spec(s, "VTH_N") == 0.38
    assert "VTH_N" in caplog.text


def test_resolve_spec_tie_breaks_on_ascending_sort():
    s = pd.Series([0.40, 0.38])
    assert resolve_spec(s, "VTH_N") == 0.38


# --- compute_item_stats ----------------------------------------------------

def _group(values, spec_low=0.38, spec_high=0.52, unit="V"):
    return pd.DataFrame({
        "wafer_id": [1] * len(values),
        "site_no": list(range(1, len(values) + 1)),
        "item_unit": [unit] * len(values),
        "spec_low": [spec_low] * len(values),
        "spec_high": [spec_high] * len(values),
        "meas_data": values,
    })


def test_item_stats_basic_fields():
    st = compute_item_stats(_group([0.44, 0.45, 0.46]), "VTH_N")
    assert st["item_name"] == "VTH_N"
    assert st["unit"] == "V"
    assert st["n"] == 3
    assert st["mean"] == pytest.approx(0.45)
    assert st["min"] == pytest.approx(0.44)
    assert st["max"] == pytest.approx(0.46)
    assert st["spec_low"] == pytest.approx(0.38)
    assert st["spec_high"] == pytest.approx(0.52)


def test_item_stats_uses_sample_stddev_ddof_1():
    st = compute_item_stats(_group([1.0, 2.0, 3.0], spec_low=None, spec_high=None), "X")
    assert st["sigma"] == pytest.approx(1.0)   # ddof=1, not 0.8165


def test_item_stats_drops_null_measurements_from_n():
    st = compute_item_stats(_group([0.44, None, 0.46]), "VTH_N")
    assert st["n"] == 2


def test_item_stats_all_null_yields_zero_n_and_gray():
    st = compute_item_stats(_group([None, None]), "VTH_N")
    assert st["n"] == 0
    assert st["mean"] is None
    assert st["cpk_state"] == "undefined"
    assert st["status"] == "gray"


def test_item_stats_reports_out_of_spec_count_and_pct():
    st = compute_item_stats(_group([0.30, 0.45, 0.45, 0.45]), "VTH_N")
    assert st["oos_count"] == 1
    assert st["oos_pct"] == pytest.approx(25.0)


def test_item_stats_wafer_series_is_ordered_and_sized():
    df = pd.DataFrame({
        "wafer_id": [2, 2, 1, 1],
        "site_no": [1, 2, 1, 2],
        "item_unit": ["V"] * 4,
        "spec_low": [0.38] * 4,
        "spec_high": [0.52] * 4,
        "meas_data": [0.46, 0.46, 0.44, 0.44],
    })
    st = compute_item_stats(df, "VTH_N")
    assert [w["wafer_id"] for w in st["wafer_series"]] == [1, 2]
    assert st["wafer_series"][0]["mean"] == pytest.approx(0.44)
    assert st["wafer_series"][0]["n"] == 2


def test_item_stats_wafer_sigma_is_none_when_single_site():
    df = pd.DataFrame({
        "wafer_id": [1],
        "site_no": [1],
        "item_unit": ["V"],
        "spec_low": [0.38],
        "spec_high": [0.52],
        "meas_data": [0.45],
    })
    st = compute_item_stats(df, "VTH_N")
    assert st["wafer_series"][0]["sigma"] is None


def test_item_stats_has_no_nan_in_json_facing_fields():
    """NaN is not valid JSON — every numeric field must be a float or None."""
    st = compute_item_stats(_group([None, None]), "VTH_N")
    for key in ("mean", "sigma", "min", "max", "cpk"):
        assert st[key] is None or not math.isnan(st[key])
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd backend && uv run python -m pytest tests/test_wat_stats.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.wat_service'`

- [ ] **Step 3: 統計コアを実装**

`backend/app/services/wat_service.py` を新規作成:

```python
"""PCM/WAT service: per-lot item statistics, judgement, and scatter pairing.

Everything here is scoped to a single lot — there is no cross-lot
aggregation. Statistics run on the raw site-level measurements, which is the
usual definition of Cpk in a fab.
"""

import logging
import math

import pandas as pd

logger = logging.getLogger(__name__)

# Process-capability thresholds. Comparisons are strictly "less than", so a
# Cpk of exactly 1.00 is yellow (not red) and exactly 1.33 is ok (not yellow).
CPK_RED = 1.00
CPK_YELLOW = 1.33


def _clean(value) -> float | None:
    """NaN and pandas NA collapse to None — NaN is not valid JSON."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def resolve_spec(series: pd.Series, item_name: str) -> float | None:
    """The spec limit for an item, assumed constant within a lot.

    When several distinct values appear, the most common one wins (ties break
    on ascending sort) and a WARNING is logged — silently picking one would
    hide a real data problem.
    """
    values = series.dropna()
    if values.empty:
        return None
    counts = values.value_counts()
    if len(counts) > 1:
        logger.warning(
            "WAT item %s has %d distinct spec values in one lot: %s — using the most common",
            item_name, len(counts), sorted(counts.index.tolist()),
        )
    top = counts.max()
    winners = sorted(v for v, c in counts.items() if c == top)
    return _clean(winners[0])


def count_out_of_spec(values: pd.Series, spec_low, spec_high) -> int:
    """Measurements strictly outside the limits. A value exactly on a limit is
    in spec."""
    clean = values.dropna()
    if clean.empty:
        return 0
    mask = pd.Series(False, index=clean.index)
    if spec_low is not None:
        mask |= clean < spec_low
    if spec_high is not None:
        mask |= clean > spec_high
    return int(mask.sum())


def compute_cpk(mean, sigma, spec_low, spec_high, n: int, oos_count: int
                ) -> tuple[float | None, str]:
    """Returns (cpk, cpk_state) where state is value / infinite / undefined.

    JSON cannot carry Infinity, so a zero-sigma in-spec item reports
    cpk=None with state="infinite" and the UI prints the symbol.
    """
    if spec_low is None and spec_high is None:
        return None, "undefined"
    if n < 2:
        return None, "undefined"
    s = _clean(sigma)
    m = _clean(mean)
    if s is None or m is None:
        return None, "undefined"
    if s == 0:
        # Every measurement identical: infinitely capable if it sits in spec,
        # meaningless if it does not.
        return (None, "undefined") if oos_count > 0 else (None, "infinite")

    candidates = []
    if spec_high is not None:
        candidates.append((spec_high - m) / (3 * s))
    if spec_low is not None:
        candidates.append((m - spec_low) / (3 * s))
    return min(candidates), "value"


def classify_status(cpk, cpk_state: str, oos_count: int) -> str:
    """Evaluated top-down; the first match wins.

    The order matters: an item with n<2 (undefined Cpk) that also has a
    failing measurement must read red, not gray.
    """
    if oos_count > 0 or (cpk_state == "value" and cpk < CPK_RED):
        return "red"
    if cpk_state == "value" and cpk < CPK_YELLOW:
        return "yellow"
    if cpk_state == "undefined":
        return "gray"
    return "ok"


def _wafer_series(group: pd.DataFrame) -> list[dict]:
    """Per-wafer mean and sigma, wafer number ascending.

    A wafer measured at a single site has no sample sigma; its error bar is
    omitted rather than drawn as zero.
    """
    out: list[dict] = []
    for wafer_id, g in group.groupby("wafer_id", sort=True):
        values = g["meas_data"].dropna()
        n = int(len(values))
        out.append({
            "wafer_id": int(wafer_id),
            "n": n,
            "mean": _clean(values.mean()) if n else None,
            "sigma": _clean(values.std(ddof=1)) if n >= 2 else None,
        })
    return out


def compute_item_stats(group: pd.DataFrame, item_name: str) -> dict:
    """Statistics for one ITEM_NAME across every wafer and site of one lot."""
    spec_low = resolve_spec(group["spec_low"], item_name)
    spec_high = resolve_spec(group["spec_high"], item_name)

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
        "wafer_series": _wafer_series(group),
    }
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd backend && uv run python -m pytest tests/test_wat_stats.py -v`
Expected: PASS（新規テストが全件 green）

- [ ] **Step 5: 全テストを実行**

Run: `cd backend && uv run python -m pytest tests/ -q`
Expected: 失敗 0

- [ ] **Step 6: コミット**

```bash
git add backend/app/services/wat_service.py backend/tests/test_wat_stats.py
git commit -m "feat(wat): item statistics, Cpk states, and status classification"
```

---

### Task 5: 散布図ペアリング

**Files:**
- Modify: `backend/app/services/wat_service.py`
- Test: `backend/tests/test_wat_scatter.py`

**Interfaces:**
- Consumes: Task 4 の `wat_service`、Task 1 の `resolve_wat_pairs` の戻り値の形
- Produces:
  - `SCATTER_KINDS: list[tuple[str, str, str]]` — `(kind, x_key, y_key)` を
    `("vth_np", "vth_n", "vth_p")`, `("idsat_np", "idsat_n", "idsat_p")`,
    `("ion_vt_n", "vth_n", "idsat_n")`, `("ion_vt_p", "vth_p", "idsat_p")` の順で保持
  - `build_scatter_pairs(df: pd.DataFrame, pairs: list[dict], stats_by_item: dict[str, dict]) -> list[dict]`

- [ ] **Step 1: 失敗するテストを書く**

`backend/tests/test_wat_scatter.py` を新規作成:

```python
import pandas as pd

from app.services.wat_service import SCATTER_KINDS, build_scatter_pairs

PAIR = {
    "label": "Core RVT",
    "vth_n": "VTHN", "vth_p": "VTHP",
    "idsat_n": "IDSATN", "idsat_p": "IDSATP",
}

STATS = {
    "VTHN": {"unit": "V", "spec_low": 0.38, "spec_high": 0.52},
    "VTHP": {"unit": "V", "spec_low": -0.52, "spec_high": -0.38},
    "IDSATN": {"unit": "uA/um", "spec_low": 500.0, "spec_high": 700.0},
    "IDSATP": {"unit": "uA/um", "spec_low": 220.0, "spec_high": 320.0},
}


def _df(rows):
    return pd.DataFrame(rows, columns=["wafer_id", "site_no", "item_name", "meas_data"])


def _full_df():
    rows = []
    for wafer in (1, 2):
        for site in (1, 2):
            rows.append([wafer, site, "VTHN", 0.45])
            rows.append([wafer, site, "VTHP", -0.45])
            rows.append([wafer, site, "IDSATN", 600.0])
            rows.append([wafer, site, "IDSATP", 270.0])
    return _df(rows)


def test_returns_four_plots_in_fixed_order():
    result = build_scatter_pairs(_full_df(), [PAIR], STATS)
    assert len(result) == 1
    assert result[0]["label"] == "Core RVT"
    assert [p["kind"] for p in result[0]["plots"]] == [k for k, _, _ in SCATTER_KINDS]
    assert [p["kind"] for p in result[0]["plots"]] == [
        "vth_np", "idsat_np", "ion_vt_n", "ion_vt_p",
    ]


def test_points_are_paired_per_wafer_and_site():
    plots = build_scatter_pairs(_full_df(), [PAIR], STATS)[0]["plots"]
    vth_np = plots[0]
    assert len(vth_np["points"]) == 4          # 2 wafers x 2 sites
    pt = vth_np["points"][0]
    assert set(pt) == {"wafer_id", "site_no", "x", "y"}
    assert pt["x"] == 0.45 and pt["y"] == -0.45


def test_site_with_one_side_missing_is_dropped():
    rows = [
        [1, 1, "VTHN", 0.45], [1, 1, "VTHP", -0.45],
        [1, 2, "VTHN", 0.46],                      # no VTHP at site 2
    ]
    plots = build_scatter_pairs(_df(rows), [PAIR], STATS)[0]["plots"]
    assert len(plots[0]["points"]) == 1
    assert plots[0]["points"][0]["site_no"] == 1


def test_plot_carries_item_names_units_and_spec_ranges():
    plots = build_scatter_pairs(_full_df(), [PAIR], STATS)[0]["plots"]
    ion_vt_n = plots[2]
    assert ion_vt_n["x_item"] == "VTHN" and ion_vt_n["y_item"] == "IDSATN"
    assert ion_vt_n["x_unit"] == "V" and ion_vt_n["y_unit"] == "uA/um"
    assert ion_vt_n["x_spec"] == [0.38, 0.52]
    assert ion_vt_n["y_spec"] == [500.0, 700.0]


def test_missing_item_yields_an_empty_plot_not_a_failure():
    rows = [[1, 1, "VTHN", 0.45], [1, 1, "IDSATN", 600.0]]
    plots = build_scatter_pairs(_df(rows), [PAIR], {"VTHN": STATS["VTHN"],
                                                    "IDSATN": STATS["IDSATN"]})[0]["plots"]
    by_kind = {p["kind"]: p for p in plots}
    assert by_kind["vth_np"]["points"] == []      # VTHP absent
    assert len(by_kind["ion_vt_n"]["points"]) == 1
    assert by_kind["vth_np"]["x_spec"] == [0.38, 0.52]
    assert by_kind["vth_np"]["y_spec"] == [None, None]


def test_no_pairs_configured_returns_empty_list():
    assert build_scatter_pairs(_full_df(), [], STATS) == []


def test_empty_dataframe_returns_pairs_with_empty_plots():
    empty = _df([])
    result = build_scatter_pairs(empty, [PAIR], STATS)
    assert len(result) == 1
    assert all(p["points"] == [] for p in result[0]["plots"])


def test_null_measurement_drops_the_point():
    rows = [
        [1, 1, "VTHN", 0.45], [1, 1, "VTHP", None],
        [1, 2, "VTHN", 0.46], [1, 2, "VTHP", -0.46],
    ]
    plots = build_scatter_pairs(_df(rows), [PAIR], STATS)[0]["plots"]
    assert len(plots[0]["points"]) == 1
    assert plots[0]["points"][0]["site_no"] == 2
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd backend && uv run python -m pytest tests/test_wat_scatter.py -v`
Expected: FAIL — `ImportError: cannot import name 'SCATTER_KINDS'`

- [ ] **Step 3: ペアリングを実装**

`backend/app/services/wat_service.py` の末尾に追加:

```python
# (kind, pair key for x, pair key for y) — the response always carries these
# four plots in this order so the UI can lay them out without sorting.
SCATTER_KINDS: list[tuple[str, str, str]] = [
    ("vth_np", "vth_n", "vth_p"),
    ("idsat_np", "idsat_n", "idsat_p"),
    ("ion_vt_n", "vth_n", "idsat_n"),
    ("ion_vt_p", "vth_p", "idsat_p"),
]


def _site_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Wide view indexed by (wafer_id, site_no) with one column per item.

    Pairing happens on this index: a point exists only where both items were
    measured at the same wafer and the same site.
    """
    if df.empty:
        return pd.DataFrame()
    return df.pivot_table(
        index=["wafer_id", "site_no"],
        columns="item_name",
        values="meas_data",
        aggfunc="mean",
    )


def _plot_points(matrix: pd.DataFrame, x_item: str, y_item: str) -> list[dict]:
    if matrix.empty or x_item not in matrix.columns or y_item not in matrix.columns:
        return []
    sub = matrix[[x_item, y_item]].dropna()
    return [
        {
            "wafer_id": int(wafer_id),
            "site_no": int(site_no),
            "x": float(row[x_item]),
            "y": float(row[y_item]),
        }
        for (wafer_id, site_no), row in sub.iterrows()
    ]


def build_scatter_pairs(df: pd.DataFrame, pairs: list[dict],
                        stats_by_item: dict[str, dict]) -> list[dict]:
    """Scatter data for every configured device flavor.

    A configured item that is absent from the data yields an empty plot rather
    than an error — the other three plots of that flavor still render.
    """
    if not pairs:
        return []

    matrix = _site_matrix(df)

    def spec_of(item: str) -> list:
        st = stats_by_item.get(item) or {}
        return [st.get("spec_low"), st.get("spec_high")]

    def unit_of(item: str) -> str:
        return (stats_by_item.get(item) or {}).get("unit", "")

    out: list[dict] = []
    for pair in pairs:
        plots = []
        for kind, x_key, y_key in SCATTER_KINDS:
            x_item = pair.get(x_key, "")
            y_item = pair.get(y_key, "")
            plots.append({
                "kind": kind,
                "x_item": x_item,
                "y_item": y_item,
                "x_unit": unit_of(x_item),
                "y_unit": unit_of(y_item),
                "x_spec": spec_of(x_item),
                "y_spec": spec_of(y_item),
                "points": _plot_points(matrix, x_item, y_item),
            })
        out.append({"label": pair.get("label", ""), "plots": plots})
    return out
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd backend && uv run python -m pytest tests/test_wat_scatter.py -v`
Expected: PASS（新規テストが全件 green）

- [ ] **Step 5: 全テストを実行**

Run: `cd backend && uv run python -m pytest tests/ -q`
Expected: 失敗 0

- [ ] **Step 6: コミット**

```bash
git add backend/app/services/wat_service.py backend/tests/test_wat_scatter.py
git commit -m "feat(wat): pair site-level measurements into scatter plot series"
```

---

### Task 6: レスポンススキーマとサービス統合

**Files:**
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/services/wat_service.py`
- Test: `backend/tests/test_wat_service_integration.py`

**Interfaces:**
- Consumes: Task 1 `resolve_wat_pairs` / Task 2 モック / Task 3 クエリ / Task 4・5 の集計関数
- Produces:
  - Pydantic: `WatLotInfo`, `WatLotsResponse`, `WatWaferPoint`, `WatItemStats`,
    `WatScatterPoint`, `WatScatterPlot`, `WatScatterPair`, `WatSummaryResponse`,
    `WatExportRequest`
  - `get_wat_lots(nickname: str, product_id: str, months: int) -> WatLotsResponse`（**新しい順**）
  - `get_wat_summary(nickname: str, product_id: str, lot_id: str) -> WatSummaryResponse`

- [ ] **Step 1: 失敗するテストを書く**

`backend/tests/test_wat_service_integration.py` を新規作成:

```python
from app.services.mock_data import mock_wat_lots
from app.services.wat_service import get_wat_lots, get_wat_summary


def _first_lot(product_id="P12345-A"):
    return mock_wat_lots(product_id, 3)["lot_id"].iloc[-1]


def test_lots_are_returned_newest_first():
    res = get_wat_lots("product_a", "P12345-A", 3)
    dates = [l.last_measured for l in res.lots]
    assert dates == sorted(dates, reverse=True)
    assert res.product_id == "P12345-A"


def test_summary_items_are_sorted_by_item_name():
    res = get_wat_summary("product_a", "P12345-A", _first_lot())
    names = [i.item_name for i in res.items]
    assert names == sorted(names)
    assert len(names) == 30      # 6 flavors x 4 + 6 misc


def test_summary_reports_lot_metadata():
    lot = _first_lot()
    res = get_wat_summary("product_a", "P12345-A", lot)
    assert res.lot_id == lot
    assert res.wafer_count == 25
    assert res.measured_date


def test_summary_every_item_carries_wafer_series():
    res = get_wat_summary("product_a", "P12345-A", _first_lot())
    for item in res.items:
        assert len(item.wafer_series) == 25


def test_mock_exercises_red_and_yellow_paths():
    res = get_wat_summary("product_a", "P12345-A", _first_lot())
    statuses = {i.status for i in res.items}
    assert "red" in statuses, "mock must produce at least one red item"
    assert "yellow" in statuses, "mock must produce at least one yellow item"


def test_unknown_lot_returns_empty_summary_not_an_error():
    res = get_wat_summary("product_a", "P12345-A", "__no_such_lot__")
    assert res.items == []
    assert res.scatter_pairs == []
    assert res.wafer_count == 0


def test_product_without_wat_config_has_no_scatter_pairs(monkeypatch):
    import app.services.wat_service as ws
    monkeypatch.setattr(ws, "resolve_wat_pairs", lambda nickname: [])
    res = get_wat_summary("product_a", "P12345-A", _first_lot())
    assert res.scatter_pairs == []
    assert res.items, "the table must still render without a wat: block"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd backend && uv run python -m pytest tests/test_wat_service_integration.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_wat_lots'`

- [ ] **Step 3: スキーマを追加**

`backend/app/models/schemas.py` の末尾に追加:

```python
class WatLotInfo(BaseModel):
    lot_id: str
    last_measured: str
    wafer_count: int


class WatLotsResponse(BaseModel):
    product_id: str
    lots: list[WatLotInfo]


class WatWaferPoint(BaseModel):
    wafer_id: int
    n: int
    mean: float | None = None
    sigma: float | None = None


class WatItemStats(BaseModel):
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
    cpk_state: str          # "value" | "infinite" | "undefined"
    oos_count: int
    oos_pct: float
    status: str             # "red" | "yellow" | "gray" | "ok"
    wafer_series: list[WatWaferPoint]


class WatScatterPoint(BaseModel):
    wafer_id: int
    site_no: int
    x: float
    y: float


class WatScatterPlot(BaseModel):
    kind: str               # vth_np | idsat_np | ion_vt_n | ion_vt_p
    x_item: str
    y_item: str
    x_unit: str = ""
    y_unit: str = ""
    x_spec: list[float | None]
    y_spec: list[float | None]
    points: list[WatScatterPoint]


class WatScatterPair(BaseModel):
    label: str
    plots: list[WatScatterPlot]


class WatSummaryResponse(BaseModel):
    product_id: str
    display_name: str
    lot_id: str
    measured_date: str = ""
    wafer_count: int
    items: list[WatItemStats]
    scatter_pairs: list[WatScatterPair]


class WatExportRequest(BaseModel):
    product_id: str
    lot_id: str
```

- [ ] **Step 4: サービス統合を実装**

`backend/app/services/wat_service.py` の import ブロックを次に差し替え:

```python
import logging
import math
from datetime import date, timedelta

import pandas as pd

from app.config import settings
from app.models.schemas import (
    WatItemStats, WatLotInfo, WatLotsResponse, WatSummaryResponse,
)
from app.services.mock_data import mock_wat_dataframe, mock_wat_lots
from app.services.product_config import (
    primary_product_id, resolve_display_name, resolve_wat_pairs,
)
from app.services.wat_queries import (
    WAT_DETAIL_COLUMNS, query_wat_detail, query_wat_lots,
)
```

ファイル末尾に追加:

```python
# ---------------------------------------------------------------------------
# Data loading (mock / real DB)
# ---------------------------------------------------------------------------

def _load_lots(product_id: str, months: int) -> pd.DataFrame:
    if settings.USE_MOCK_DATA:
        return mock_wat_lots(product_id, months)
    today = date.today()
    start = today - timedelta(days=months * 30)
    end = today + timedelta(days=1)   # exclusive upper bound keeps today's data
    return query_wat_lots(product_id, start, end)


def _load_detail(product_id: str, lot_id: str) -> pd.DataFrame:
    if settings.USE_MOCK_DATA:
        return mock_wat_dataframe(product_id, lot_id)
    return query_wat_detail(product_id, lot_id)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_wat_lots(nickname: str, product_id: str, months: int) -> WatLotsResponse:
    """WAT lots for a product, newest first."""
    df = _load_lots(product_id, months)
    lots: list[WatLotInfo] = []
    if not df.empty:
        ordered = df.sort_values("last_measured", ascending=False)
        lots = [
            WatLotInfo(
                lot_id=str(r.lot_id),
                last_measured=str(r.last_measured)[:10],
                wafer_count=int(r.wafer_count),
            )
            for r in ordered.itertuples()
        ]
    return WatLotsResponse(product_id=product_id, lots=lots)


def get_wat_summary(nickname: str, product_id: str, lot_id: str) -> WatSummaryResponse:
    """Item statistics and scatter series for one lot."""
    df = _load_detail(product_id, lot_id)
    if df.empty:
        df = pd.DataFrame(columns=WAT_DETAIL_COLUMNS)

    stats: list[dict] = []
    for item_name, group in df.groupby("item_name", sort=True):
        stats.append(compute_item_stats(group, str(item_name)))

    stats_by_item = {s["item_name"]: s for s in stats}
    scatter_pairs = build_scatter_pairs(df, resolve_wat_pairs(nickname), stats_by_item)

    measured_date = ""
    wafer_count = 0
    if not df.empty:
        wafer_count = int(df["wafer_id"].nunique())
        stamps = df["start_time"].dropna()
        if not stamps.empty:
            measured_date = str(stamps.max())[:10]

    return WatSummaryResponse(
        product_id=primary_product_id(nickname) or product_id,
        display_name=resolve_display_name(nickname),
        lot_id=lot_id,
        measured_date=measured_date,
        wafer_count=wafer_count,
        items=[WatItemStats(**s) for s in stats],
        scatter_pairs=scatter_pairs,
    )
```

- [ ] **Step 5: テストが通ることを確認**

Run: `cd backend && uv run python -m pytest tests/test_wat_service_integration.py -v`
Expected: PASS（新規テストが全件 green）

`test_mock_exercises_red_and_yellow_paths` が失敗する場合は Task 2 の `VTHN_ULVT` / `RS_NDIFF` の細工係数を調整する（テスト側を緩めない）。

- [ ] **Step 6: 全テストを実行**

Run: `cd backend && uv run python -m pytest tests/ -q`
Expected: 失敗 0

- [ ] **Step 7: コミット**

```bash
git add backend/app/models/schemas.py backend/app/services/wat_service.py backend/tests/test_wat_service_integration.py
git commit -m "feat(wat): summary/lots service API with pydantic schemas"
```

---

### Task 7: ルータ登録

**Files:**
- Create: `backend/app/routers/wat.py`
- Modify: `backend/app/main.py:26`（import 行）と `main.py:57` 付近（`include_router` 群）
- Test: `backend/tests/test_wat_api.py`

**Interfaces:**
- Consumes: Task 6 の `get_wat_lots` / `get_wat_summary`
- Produces: `GET /api/wat/lots`、`GET /api/wat/summary`（`POST /api/wat/export-pdf` は Task 9 で追加）

- [ ] **Step 1: 失敗するテストを書く**

`backend/tests/test_wat_api.py` を新規作成:

```python
from fastapi.testclient import TestClient

from app.main import app
from app.services.mock_data import mock_wat_lots

client = TestClient(app)


def test_lots_endpoint_returns_newest_first():
    res = client.get("/api/wat/lots", params={"product_id": "P12345-A", "months": 3})
    assert res.status_code == 200
    lots = res.json()["lots"]
    assert lots
    assert [l["last_measured"] for l in lots] == sorted(
        [l["last_measured"] for l in lots], reverse=True
    )


def test_lots_endpoint_rejects_out_of_range_months():
    res = client.get("/api/wat/lots", params={"product_id": "P12345-A", "months": 12})
    assert res.status_code == 422


def test_summary_endpoint_returns_items_and_scatter():
    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[-1]
    res = client.get("/api/wat/summary",
                     params={"product_id": "P12345-A", "lot_id": lot})
    assert res.status_code == 200
    body = res.json()
    assert body["lot_id"] == lot
    assert len(body["items"]) == 30
    assert body["items"] == sorted(body["items"], key=lambda i: i["item_name"])


def test_summary_endpoint_unknown_lot_is_empty_not_500():
    res = client.get("/api/wat/summary",
                     params={"product_id": "P12345-A", "lot_id": "nope"})
    assert res.status_code == 200
    assert res.json()["items"] == []


def test_summary_response_is_json_serialisable_without_nan():
    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[-1]
    res = client.get("/api/wat/summary",
                     params={"product_id": "P12345-A", "lot_id": lot})
    assert "NaN" not in res.text, "NaN is not valid JSON"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd backend && uv run python -m pytest tests/test_wat_api.py -v`
Expected: FAIL — 404（ルートが未登録）

- [ ] **Step 3: ルータを実装**

`backend/app/routers/wat.py` を新規作成:

```python
import logging

from fastapi import APIRouter, Query

from app.models.schemas import WatLotsResponse, WatSummaryResponse
from app.services.product_config import nickname_for_product_id
from app.services.wat_service import get_wat_lots, get_wat_summary

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/wat/lots", response_model=WatLotsResponse)
def wat_lots(
    product_id: str = Query(...),
    months: int = Query(3, ge=1, le=6),
) -> WatLotsResponse:
    nickname = nickname_for_product_id(product_id) or product_id
    return get_wat_lots(nickname, product_id, months)


@router.get("/wat/summary", response_model=WatSummaryResponse)
def wat_summary(
    product_id: str = Query(...),
    lot_id: str = Query(...),
) -> WatSummaryResponse:
    nickname = nickname_for_product_id(product_id) or product_id
    return get_wat_summary(nickname, product_id, lot_id)
```

`backend/app/main.py` の import 行を変更:

```python
from app.routers import anomaly_config, dashboard, explore, export, wafer_map, wat, yield_data
```

`app.include_router(wafer_map.router, prefix="/api")` の直後に追加:

```python
app.include_router(wat.router, prefix="/api")
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd backend && uv run python -m pytest tests/test_wat_api.py -v`
Expected: PASS（新規テストが全件 green）

- [ ] **Step 5: 全テストを実行**

Run: `cd backend && uv run python -m pytest tests/ -q`
Expected: 失敗 0

- [ ] **Step 6: コミット**

```bash
git add backend/app/routers/wat.py backend/app/main.py backend/tests/test_wat_api.py
git commit -m "feat(wat): expose /api/wat/lots and /api/wat/summary"
```

---

### Task 8: PDF 共通部品の切り出し

**Files:**
- Create: `backend/app/services/pdf_common.py`
- Modify: `backend/app/services/pdf_service.py:22-57`（ブランディング/レイアウト定数）と `:145-176`（`_draw_logo`）、`:246-280`（`_draw_footer`）
- Test: `backend/tests/test_pdf_common.py`

**Interfaces:**
- Consumes: なし
- Produces（`pdf_common` から export）:
  - `COMPANY_NAME: str`、`LOGO_PATH: str | None`、`CONFIDENTIAL: bool`
  - `TEXT_COLOR`、`SUBTEXT_COLOR`、`FONT_FAMILY`
  - `MARGIN`、`HEADER_H`、`HEADER_DIVIDER_OFFSET`、`FOOTER_H`
  - `draw_logo(c, x, y, h) -> None`
  - `draw_footer(c, page_width, current_page, total_pages) -> None`

**この Task の要点:** 既存の歩留り PDF の**描画結果を一切変えない**こと。移動のみで、ロジックは書き換えない。

- [ ] **Step 1: 移動前の出力を退避**

```bash
cd backend
mkdir -p .tmp-pdf-check
uv run python -c "
from app.services.pdf_service import generate_pdf
from app.models.schemas import ProcessData
d = {'CP': {'Product-A': ProcessData(lots=['2026W01','2026W02'], yield_avg=[95.0,94.0], fail_bins={'Leak':[2.0,3.0]})}}
open('.tmp-pdf-check/before.pdf','wb').write(generate_pdf(['Product-A'],'2026-01','2026-02',d))
print('ok')
"
```

- [ ] **Step 2: 失敗するテストを書く**

`backend/tests/test_pdf_common.py` を新規作成:

```python
from pathlib import Path

from app.services import pdf_common, pdf_service


def test_branding_constants_live_in_pdf_common():
    assert pdf_common.COMPANY_NAME == "Socionext"
    assert pdf_common.CONFIDENTIAL is True
    assert pdf_common.LOGO_PATH is None or Path(pdf_common.LOGO_PATH).name == "logo.png"


def test_layout_constants_are_unchanged():
    from reportlab.lib.units import mm
    assert pdf_common.MARGIN == 15 * mm
    assert pdf_common.HEADER_H == 48 * mm
    assert pdf_common.HEADER_DIVIDER_OFFSET == 4 * mm
    assert pdf_common.FOOTER_H == 10 * mm


def test_pdf_service_reuses_the_shared_constants():
    """The yield PDF must not keep a private copy that can drift."""
    assert pdf_service.MARGIN is pdf_common.MARGIN
    assert pdf_service.COMPANY_NAME is pdf_common.COMPANY_NAME
    assert pdf_service.FOOTER_H is pdf_common.FOOTER_H


def test_shared_drawing_helpers_are_callable():
    assert callable(pdf_common.draw_logo)
    assert callable(pdf_common.draw_footer)


def test_yield_pdf_still_generates():
    from app.models.schemas import ProcessData
    data = {"CP": {"Product-A": ProcessData(
        lots=["2026W01", "2026W02"], yield_avg=[95.0, 94.0],
        fail_bins={"Leak": [2.0, 3.0]},
    )}}
    out = pdf_service.generate_pdf(["Product-A"], "2026-01", "2026-02", data)
    assert out[:4] == b"%PDF"
    assert len(out) > 1000
```

- [ ] **Step 3: テストが失敗することを確認**

Run: `cd backend && uv run python -m pytest tests/test_pdf_common.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.pdf_common'`

- [ ] **Step 4: `pdf_common.py` を作成**

`backend/app/services/pdf_common.py` を新規作成し、`pdf_service.py` から以下を**そのまま移動**する:

```python
"""Branding and page furniture shared by every PDF this app generates.

Both the landscape yield report (pdf_service) and the portrait PCM/WAT
report (wat_pdf_service) draw the same logo, footer, and margins. Keeping
one copy here means a branding change lands on both.

Swap these out for production:
  COMPANY_NAME  : displayed in the header logo area
  LOGO_PATH     : absolute path to a PNG/JPG logo file, or None to use mock
  CONFIDENTIAL  : set False to suppress the confidential mark
"""

from datetime import date
from pathlib import Path

from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------
COMPANY_NAME: str = "Socionext"
LOGO_PATH: str | None = str(Path(__file__).resolve().parents[3] / "assets" / "logo.png")
CONFIDENTIAL: bool = True

# ---------------------------------------------------------------------------
# Shared type tokens
# ---------------------------------------------------------------------------
TEXT_COLOR = "#37352f"
SUBTEXT_COLOR = "#615d59"
FONT_FAMILY = "Inter, -apple-system, Segoe UI, Helvetica, Arial, sans-serif"

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
MARGIN = 15 * mm
HEADER_H = 48 * mm              # header band (title + rule + padding)
HEADER_DIVIDER_OFFSET = 4 * mm  # header base → divider distance
FOOTER_H = 10 * mm
```

続けて `_draw_logo` の本体を `draw_logo` として、`_draw_footer` の本体を `draw_footer` として、**中身を一字一句変えずに**移す（`pdf_service.py:145-176` と `:246-280` を参照）。関数シグネチャは:

```python
def draw_logo(c: canvas.Canvas, x: float, y: float, h: float) -> None:
    ...  # pdf_service._draw_logo の本体をそのまま


def draw_footer(c: canvas.Canvas, page_width: float,
                current_page: int, total_pages: int) -> None:
    ...  # pdf_service._draw_footer の本体をそのまま
```

- [ ] **Step 5: `pdf_service.py` を共通部品の利用側に書き換える**

`pdf_service.py` から移動した定数定義と 2 つの関数定義を**削除**し、代わりに import する:

```python
from app.services.pdf_common import (
    COMPANY_NAME, CONFIDENTIAL, FONT_FAMILY, FOOTER_H, HEADER_DIVIDER_OFFSET,
    HEADER_H, LOGO_PATH, MARGIN, SUBTEXT_COLOR, TEXT_COLOR,
    draw_footer, draw_logo,
)
```

`pdf_service.py` 内の `_draw_logo(` 呼び出しを `draw_logo(`、`_draw_footer(` 呼び出しを `draw_footer(` に置換する。`BIN_COLORS` と `YIELD_LINE_COLOR` は歩留り専用なので `pdf_service.py` に残す。

不要になった import（`from pathlib import Path`、`from reportlab.lib.utils import ImageReader` など）が残っていないか確認する。

- [ ] **Step 6: テストが通ることを確認**

Run: `cd backend && uv run python -m pytest tests/test_pdf_common.py -v`
Expected: PASS（新規テストが全件 green）

- [ ] **Step 7: 出力が変わっていないことを目視確認**

```bash
cd backend
mkdir -p .tmp-pdf-check
uv run python -c "
from app.services.pdf_service import generate_pdf
from app.models.schemas import ProcessData
d = {'CP': {'Product-A': ProcessData(lots=['2026W01','2026W02'], yield_avg=[95.0,94.0], fail_bins={'Leak':[2.0,3.0]})}}
open('.tmp-pdf-check/after.pdf','wb').write(generate_pdf(['Product-A'],'2026-01','2026-02',d))
print('ok')
"
uv run python -c "
import sys
a=open('.tmp-pdf-check/before.pdf','rb').read(); b=open('.tmp-pdf-check/after.pdf','rb').read()
print('size before/after:', len(a), len(b))
print('SIZE DELTA:', abs(len(a)-len(b)))
"
```

Expected: サイズ差が 200 バイト以内（PDF はタイムスタンプと ID を埋め込むため完全一致にはならない）。これを超える場合は移動時に何か書き換えている — diff を見直すこと。

- [ ] **Step 8: 全テストを実行**

Run: `cd backend && uv run python -m pytest tests/ -q`
Expected: 失敗 0

- [ ] **Step 9: コミット**

```bash
rm -rf backend/.tmp-pdf-check
git add backend/app/services/pdf_common.py backend/app/services/pdf_service.py backend/tests/test_pdf_common.py
git commit -m "refactor(pdf): extract shared branding and page furniture to pdf_common"
```

---

### Task 9: WAT の PDF 生成とエクスポート API

**Files:**
- Create: `backend/app/services/wat_pdf_service.py`
- Modify: `backend/app/routers/wat.py`
- Test: `backend/tests/test_wat_pdf.py`

**Interfaces:**
- Consumes: Task 6 の `WatSummaryResponse`、Task 8 の `pdf_common`
- Produces:
  - `STATUS_MARK: dict[str, str]` — `{"red": "●", "yellow": "▲", "gray": "–", "ok": ""}`
  - `fmt_value(v: float | None) -> str` — 有効数字 4 桁（`%.4g`）、`None` は `"—"`
  - `fmt_cpk(cpk, cpk_state) -> str` — `value`→小数 2 桁、`infinite`→`"∞"`、`undefined`→`"—"`
  - `generate_wat_pdf(summary: WatSummaryResponse) -> bytes`

- [ ] **Step 1: 失敗するテストを書く**

`backend/tests/test_wat_pdf.py` を新規作成:

```python
import time

from app.services.mock_data import mock_wat_lots
from app.services.wat_pdf_service import (
    STATUS_MARK, fmt_cpk, fmt_value, generate_wat_pdf,
)
from app.services.wat_service import get_wat_summary


def test_status_marks_cover_every_status():
    assert set(STATUS_MARK) == {"red", "yellow", "gray", "ok"}
    assert STATUS_MARK["red"] == "●"
    assert STATUS_MARK["yellow"] == "▲"
    assert STATUS_MARK["ok"] == ""


def test_fmt_value_uses_four_significant_digits():
    assert fmt_value(0.4021456) == "0.4021"
    assert fmt_value(1042.637) == "1043"
    assert fmt_value(None) == "—"


def test_fmt_cpk_renders_each_state():
    assert fmt_cpk(1.234, "value") == "1.23"
    assert fmt_cpk(None, "infinite") == "∞"
    assert fmt_cpk(None, "undefined") == "—"


def test_generate_wat_pdf_produces_a_portrait_pdf():
    from pypdf import PdfReader
    import io

    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[-1]
    summary = get_wat_summary("product_a", "P12345-A", lot)

    started = time.monotonic()
    out = generate_wat_pdf(summary)
    elapsed = time.monotonic() - started

    assert out[:4] == b"%PDF"
    reader = PdfReader(io.BytesIO(out))
    assert len(reader.pages) >= 2
    box = reader.pages[0].mediabox
    assert box.height > box.width, "WAT report must be A4 portrait"
    print(f"\nWAT PDF: {len(reader.pages)} pages in {elapsed:.1f}s")


def test_generate_wat_pdf_handles_empty_summary():
    summary = get_wat_summary("product_a", "P12345-A", "__no_such_lot__")
    out = generate_wat_pdf(summary)
    assert out[:4] == b"%PDF"
```

`pypdf` が未導入なら追加する: `cd backend && uv add --dev pypdf`

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd backend && uv run python -m pytest tests/test_wat_pdf.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.wat_pdf_service'`

- [ ] **Step 3: PDF 生成を実装**

`backend/app/services/wat_pdf_service.py` を新規作成:

```python
"""PCM/WAT lot report PDF (A4 portrait).

Layout: lot header + summary, then the full item table across as many pages
as it needs, then the scatter plots 2x2 per page, then a wafer-trend chart
for every item judged red or yellow.
"""

import io
import logging

import plotly.graph_objects as go
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.models.schemas import WatItemStats, WatScatterPlot, WatSummaryResponse
from app.services.pdf_common import (
    FONT_FAMILY, FOOTER_H, MARGIN, SUBTEXT_COLOR, TEXT_COLOR,
    draw_footer, draw_logo,
)

logger = logging.getLogger(__name__)

STATUS_MARK: dict[str, str] = {"red": "●", "yellow": "▲",
                               "gray": "–", "ok": ""}

STATUS_RGB: dict[str, tuple[float, float, float]] = {
    "red": (0.776, 0.271, 0.271),
    "yellow": (0.831, 0.627, 0.090),
    "gray": (0.557, 0.545, 0.510),
    "ok": (0.216, 0.208, 0.184),
}

# Single-hue ramp for wafer number: light -> dark. A rainbow would imply an
# order the eye reads wrongly, and 25 discrete legend entries are unreadable.
WAFER_COLORSCALE = [[0.0, "#f0d9cf"], [0.5, "#cc785c"], [1.0, "#5c2f1e"]]

PLOT_TITLES = {
    "vth_np": "Vth  n/p",
    "idsat_np": "Idsat  n/p",
    "ion_vt_n": "Ion-Vt  (N)",
    "ion_vt_p": "Ion-Vt  (P)",
}

# 12 columns: mark, item, unit, low, high, N, mean, sigma, min, max, cpk, oos.
# Widths sum to the printable width of A4 portrait (210mm - 2 * 15mm).
COL_WIDTHS = [6, 40, 15, 16, 16, 12, 17, 15, 16, 16, 12, 11]
COL_HEADERS = ["", "Item", "Unit", "Low", "High", "N",
               "Mean", "Sigma", "Min", "Max", "Cpk", "OOS"]

ROW_H = 4.4 * mm
TABLE_FONT = 6.6


def fmt_value(v) -> str:
    """Four significant digits, so 0.4021 and 1043 read at the same width."""
    if v is None:
        return "—"
    return f"{v:.4g}"


def fmt_cpk(cpk, cpk_state: str) -> str:
    if cpk_state == "infinite":
        return "∞"
    if cpk_state == "value" and cpk is not None:
        return f"{cpk:.2f}"
    return "—"


# ---------------------------------------------------------------------------
# Chart images
# ---------------------------------------------------------------------------

def _base_layout(width: int, height: int, title: str) -> dict:
    return dict(
        title=dict(text=title, font=dict(size=13, color=TEXT_COLOR, family=FONT_FAMILY)),
        font=dict(family=FONT_FAMILY, size=10, color=TEXT_COLOR),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        showlegend=False,
        width=width,
        height=height,
        margin=dict(l=62, r=24, t=42, b=48),
    )


def _axis(title: str) -> dict:
    return dict(
        title=dict(text=title, font=dict(size=10, color=SUBTEXT_COLOR)),
        tickfont=dict(size=9, color=SUBTEXT_COLOR),
        gridcolor="rgba(0,0,0,0.05)",
        linecolor="rgba(0,0,0,0.12)",
        zeroline=False,
    )


def _scatter_image(plot: WatScatterPlot, width: int = 620, height: int = 460) -> bytes:
    title = PLOT_TITLES.get(plot.kind, plot.kind)
    fig = go.Figure()

    if plot.points:
        fig.add_trace(go.Scatter(
            x=[p.x for p in plot.points],
            y=[p.y for p in plot.points],
            mode="markers",
            marker=dict(
                size=8,
                color=[p.wafer_id for p in plot.points],
                colorscale=WAFER_COLORSCALE,
                colorbar=dict(title=dict(text="Wafer", font=dict(size=9)),
                              thickness=10, len=0.8),
                line=dict(width=1, color="#ffffff"),   # ring separates overlaps
            ),
        ))
        # Spec box: a rectangle is read instantly, four lines are not.
        x_lo, x_hi = plot.x_spec
        y_lo, y_hi = plot.y_spec
        if None not in (x_lo, x_hi, y_lo, y_hi):
            fig.add_shape(type="rect", x0=x_lo, x1=x_hi, y0=y_lo, y1=y_hi,
                          line=dict(color="rgba(198,69,69,0.45)", width=1, dash="dash"),
                          fillcolor="rgba(198,69,69,0.05)", layer="below")
    else:
        fig.add_annotation(text="No data", showarrow=False,
                           font=dict(size=12, color=SUBTEXT_COLOR))

    x_label = f"{plot.x_item} [{plot.x_unit}]" if plot.x_unit else plot.x_item
    y_label = f"{plot.y_item} [{plot.y_unit}]" if plot.y_unit else plot.y_item
    fig.update_layout(**_base_layout(width, height, title),
                      xaxis=_axis(x_label), yaxis=_axis(y_label))
    return fig.to_image(format="png", scale=2)


def _trend_image(item: WatItemStats, width: int = 1000, height: int = 380) -> bytes:
    series = item.wafer_series
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[w.wafer_id for w in series],
        y=[w.mean for w in series],
        mode="lines+markers",
        line=dict(color="#141413", width=2),
        marker=dict(size=8, color="#141413"),
        error_y=dict(
            type="data",
            array=[(w.sigma * 3 if w.sigma is not None else 0) for w in series],
            visible=True, color="rgba(20,20,19,0.35)", thickness=1.2, width=3,
        ),
    ))
    for limit, label in ((item.spec_low, "LSL"), (item.spec_high, "USL")):
        if limit is not None:
            fig.add_hline(y=limit, line=dict(color="#c64545", width=1, dash="dash"),
                          annotation_text=label,
                          annotation_font=dict(size=9, color="#c64545"))

    unit = f" [{item.unit}]" if item.unit else ""
    fig.update_layout(**_base_layout(width, height, f"{item.item_name}{unit}"),
                      xaxis=_axis("Wafer #"), yaxis=_axis(""))
    return fig.to_image(format="png", scale=2)


# ---------------------------------------------------------------------------
# Page furniture
# ---------------------------------------------------------------------------

def _draw_header(c: canvas.Canvas, page_width: float, page_height: float,
                 summary: WatSummaryResponse) -> float:
    """Draws the header band; returns the y coordinate where content starts."""
    top = page_height - MARGIN
    logo_h = 10 * mm
    draw_logo(c, MARGIN, top - logo_h, logo_h)

    c.saveState()
    c.setFillColorRGB(0.216, 0.208, 0.184)
    c.setFont("Helvetica-Bold", 13)
    title = f"PCM / WAT  —  {summary.product_id}"
    if summary.display_name and summary.display_name != summary.product_id:
        title += f"  ({summary.display_name})"
    c.drawString(MARGIN, top - logo_h - 7 * mm, title)

    c.setFont("Helvetica", 8.5)
    c.setFillColorRGB(0.38, 0.36, 0.35)
    meta = (f"Lot {summary.lot_id}    Measured {summary.measured_date or '—'}    "
            f"{summary.wafer_count} wafers    {len(summary.items)} items")
    c.drawString(MARGIN, top - logo_h - 12 * mm, meta)

    reds = sum(1 for i in summary.items if i.status == "red")
    yellows = sum(1 for i in summary.items if i.status == "yellow")
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


def _draw_table_header(c: canvas.Canvas, y: float) -> float:
    c.saveState()
    c.setFont("Helvetica-Bold", TABLE_FONT)
    c.setFillColorRGB(0.38, 0.36, 0.35)
    x = MARGIN
    for header, width in zip(COL_HEADERS, COL_WIDTHS):
        c.drawString(x, y, header)
        x += width * mm
    c.setStrokeColorRGB(0, 0, 0, alpha=0.12)
    c.setLineWidth(0.5)
    c.line(MARGIN, y - 1.5 * mm, MARGIN + sum(COL_WIDTHS) * mm, y - 1.5 * mm)
    c.restoreState()
    return y - ROW_H


def _draw_item_row(c: canvas.Canvas, y: float, item: WatItemStats) -> float:
    cells = [
        STATUS_MARK.get(item.status, ""),
        item.item_name,
        item.unit,
        fmt_value(item.spec_low),
        fmt_value(item.spec_high),
        str(item.n),
        fmt_value(item.mean),
        fmt_value(item.sigma),
        fmt_value(item.min),
        fmt_value(item.max),
        fmt_cpk(item.cpk, item.cpk_state),
        str(item.oos_count),
    ]
    c.saveState()
    c.setFont("Helvetica", TABLE_FONT)
    x = MARGIN
    for i, (text, width) in enumerate(zip(cells, COL_WIDTHS)):
        # The mark column carries the status color; every other cell stays ink
        # so a colored value never has to be read as a judgement.
        c.setFillColorRGB(*(STATUS_RGB.get(item.status, STATUS_RGB["ok"])
                            if i == 0 else STATUS_RGB["ok"]))
        avail = width * mm - 1.2 * mm
        while text and c.stringWidth(text, "Helvetica", TABLE_FONT) > avail:
            text = text[:-1]
        c.drawString(x, y, text)
        x += width * mm
    c.restoreState()
    return y - ROW_H


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _rows_per_page(content_top: float) -> int:
    """How many item rows fit between the header rule and the footer."""
    usable = content_top - (FOOTER_H + 12 * mm) - ROW_H   # minus the column header
    return max(1, int(usable // ROW_H))


def count_pages(summary: WatSummaryResponse, content_top: float) -> int:
    """Total page count, known before drawing.

    ReportLab cannot revisit a finished page, so "Page n of N" needs N up
    front. Every section's length is a pure function of the summary, so the
    count is computed rather than guessed.
    """
    per_page = _rows_per_page(content_top)
    table_pages = max(1, math.ceil(len(summary.items) / per_page))
    scatter = sum(len(pair.plots) for pair in summary.scatter_pairs)
    scatter_pages = math.ceil(scatter / 4)
    flagged = sum(1 for i in summary.items if i.status in ("red", "yellow"))
    trend_pages = math.ceil(flagged / 2)
    return table_pages + scatter_pages + trend_pages


def generate_wat_pdf(summary: WatSummaryResponse) -> bytes:
    """A4 portrait PCM/WAT lot report."""
    buf = io.BytesIO()
    page_width, page_height = A4
    c = canvas.Canvas(buf, pagesize=A4)

    flagged = [i for i in summary.items if i.status in ("red", "yellow")]
    scatter_plots = [p for pair in summary.scatter_pairs for p in pair.plots]

    # Draw one header to learn where content starts, then discard the canvas
    # state — the value only depends on constants, so it is stable.
    probe_top = _draw_header(c, page_width, page_height, summary)
    total_pages = count_pages(summary, probe_top)
    logger.info(
        "WAT PDF: lot=%s items=%d flagged=%d scatter=%d pages=%d",
        summary.lot_id, len(summary.items), len(flagged),
        len(scatter_plots), total_pages,
    )

    page_no = 1

    def end_page() -> float:
        """Footer the current page, start the next, return its content top."""
        nonlocal page_no
        draw_footer(c, page_width, page_no, total_pages)
        c.showPage()
        page_no += 1
        return _draw_header(c, page_width, page_height, summary)

    # --- Item table ---------------------------------------------------------
    y = _draw_table_header(c, probe_top)
    if not summary.items:
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(*STATUS_RGB["gray"])
        c.drawString(MARGIN, y, "No WAT data for this lot.")
    for item in summary.items:
        if y < FOOTER_H + 12 * mm:
            y = _draw_table_header(c, end_page())
        y = _draw_item_row(c, y, item)

    # --- Scatter plots, 2x2 per page ----------------------------------------
    for i in range(0, len(scatter_plots), 4):
        top = end_page()
        chunk = scatter_plots[i:i + 4]
        cell_w = (page_width - 2 * MARGIN) / 2
        cell_h = (top - FOOTER_H - 4 * mm) / 2
        for j, plot in enumerate(chunk):
            col, row = j % 2, j // 2
            img = ImageReader(io.BytesIO(_scatter_image(plot)))
            c.drawImage(
                img,
                MARGIN + col * cell_w,
                top - (row + 1) * cell_h,
                width=cell_w - 2 * mm, height=cell_h - 2 * mm,
                preserveAspectRatio=True, anchor="n", mask="auto",
            )

    # --- Trend charts for flagged items -------------------------------------
    for i in range(0, len(flagged), 2):
        top = end_page()
        chunk = flagged[i:i + 2]
        cell_h = (top - FOOTER_H - 4 * mm) / 2
        for j, item in enumerate(chunk):
            img = ImageReader(io.BytesIO(_trend_image(item)))
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

`import math` を冒頭の import に加えること。

- [ ] **Step 4: ページ数が計算どおりであることを確認**

`backend/tests/test_wat_pdf.py` に追加:

```python
def test_page_count_matches_the_precomputed_total():
    """Page n of N is written before drawing, so the prediction must hold."""
    from pypdf import PdfReader
    import io as _io
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as _canvas
    from app.services.wat_pdf_service import _draw_header, count_pages

    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[-1]
    summary = get_wat_summary("product_a", "P12345-A", lot)

    probe = _canvas.Canvas(_io.BytesIO(), pagesize=A4)
    top = _draw_header(probe, A4[0], A4[1], summary)
    predicted = count_pages(summary, top)

    actual = len(PdfReader(_io.BytesIO(generate_wat_pdf(summary))).pages)
    assert actual == predicted
```

Run: `cd backend && uv run python -m pytest tests/test_wat_pdf.py -v`
Expected: PASS（全件）

- [ ] **Step 5: エクスポート API を追加**

`backend/app/routers/wat.py` に追加:

```python
import traceback

from fastapi import HTTPException
from fastapi.responses import Response

from app.models.schemas import WatExportRequest
from app.services.wat_pdf_service import generate_wat_pdf


@router.post("/wat/export-pdf")
def wat_export_pdf(req: WatExportRequest) -> Response:
    nickname = nickname_for_product_id(req.product_id) or req.product_id
    summary = get_wat_summary(nickname, req.product_id, req.lot_id)
    try:
        pdf_bytes = generate_wat_pdf(summary)
    except Exception as e:
        logger.error("generate_wat_pdf failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    filename = f"WAT_{req.product_id}_{req.lot_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 6: テストが通ることを確認**

Run: `cd backend && uv run python -m pytest tests/test_wat_pdf.py -v -s`
Expected: PASS（新規テストが全件 green）。`-s` により `WAT PDF: N pages in X.Xs` が表示される。

- [ ] **Step 7: 生成時間を記録**

Step 6 の出力に表示された秒数を、この plan ファイルの本 Task の末尾に追記する:

```
実測: <N> ページ / <X.X> 秒（mock, 24 散布図 + <M> トレンド）
```

30 秒を超える場合は報告する（仕様で「実測してから必要なら手を打つ」と合意済み。実装者の判断で図を減らさないこと）。

- [ ] **Step 8: 全テストを実行**

Run: `cd backend && uv run python -m pytest tests/ -q`
Expected: 失敗 0

- [ ] **Step 9: コミット**

```bash
git add backend/app/services/wat_pdf_service.py backend/app/routers/wat.py backend/tests/test_wat_pdf.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(wat): A4 portrait lot report PDF with scatter and trend charts"
```

---

### Task 10: フロントエンドの型・API クライアント・タブ切替

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/theme.ts`
- Modify: `frontend/src/pages/ReportPage.tsx`
- Create: `frontend/src/components/wat/WatSummaryTab.tsx`

**Interfaces:**
- Consumes: Task 7・9 のエンドポイント
- Produces:
  - 型: `WatLotInfo`, `WatLotsResponse`, `WatWaferPoint`, `WatItemStats`,
    `WatScatterPoint`, `WatScatterPlot`, `WatScatterPair`, `WatSummaryResponse`
  - `fetchWatLots(productId, months)`, `fetchWatSummary(productId, lotId)`, `exportWatPdf(productId, lotId)`
  - `WAFER_COLORSCALE`, `STATUS_COLOR`, `STATUS_MARK`（`theme.ts`）
  - `<WatSummaryTab productId={...} />`

- [ ] **Step 1: 型を追加**

`frontend/src/types.ts` の末尾に追加:

```typescript
export interface WatLotInfo {
  lot_id: string;
  last_measured: string;
  wafer_count: number;
}

export interface WatLotsResponse {
  product_id: string;
  lots: WatLotInfo[];
}

export interface WatWaferPoint {
  wafer_id: number;
  n: number;
  mean: number | null;
  sigma: number | null;
}

export type WatStatus = "red" | "yellow" | "gray" | "ok";
export type WatCpkState = "value" | "infinite" | "undefined";

export interface WatItemStats {
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
  wafer_series: WatWaferPoint[];
}

export interface WatScatterPoint {
  wafer_id: number;
  site_no: number;
  x: number;
  y: number;
}

export interface WatScatterPlot {
  kind: "vth_np" | "idsat_np" | "ion_vt_n" | "ion_vt_p";
  x_item: string;
  y_item: string;
  x_unit: string;
  y_unit: string;
  x_spec: (number | null)[];
  y_spec: (number | null)[];
  points: WatScatterPoint[];
}

export interface WatScatterPair {
  label: string;
  plots: WatScatterPlot[];
}

export interface WatSummaryResponse {
  product_id: string;
  display_name: string;
  lot_id: string;
  measured_date: string;
  wafer_count: number;
  items: WatItemStats[];
  scatter_pairs: WatScatterPair[];
}
```

- [ ] **Step 2: API クライアントを追加**

`frontend/src/api/client.ts` の import に型を足し、末尾に追加:

```typescript
export async function fetchWatLots(
  productId: string, months: number
): Promise<WatLotsResponse> {
  const res = await api.get<WatLotsResponse>("/wat/lots", {
    params: { product_id: productId, months },
  });
  return res.data;
}

export async function fetchWatSummary(
  productId: string, lotId: string
): Promise<WatSummaryResponse> {
  const res = await api.get<WatSummaryResponse>("/wat/summary", {
    params: { product_id: productId, lot_id: lotId },
  });
  return res.data;
}

export async function exportWatPdf(productId: string, lotId: string): Promise<void> {
  const res = await api.post(
    "/wat/export-pdf",
    { product_id: productId, lot_id: lotId },
    { responseType: "blob" },
  );
  const blob = new Blob([res.data], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `WAT_${productId}_${lotId}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}
```

- [ ] **Step 3: テーマにトークンを追加**

`frontend/src/theme.ts` の末尾に追加:

```typescript
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
```

- [ ] **Step 4: `WatSummaryTab` の骨格を作る**

`frontend/src/components/wat/WatSummaryTab.tsx` を新規作成:

```tsx
import { useCallback, useEffect, useState } from "react";
import { exportWatPdf, fetchWatLots, fetchWatSummary } from "../../api/client";
import type { WatLotInfo, WatSummaryResponse } from "../../types";
import Button from "../../ui/Button";
import Select from "../../ui/Select";
import { STATUS_MARK } from "../../theme";

interface Props {
  productId: string;
}

export default function WatSummaryTab({ productId }: Props) {
  const [months, setMonths] = useState(3);
  const [lots, setLots] = useState<WatLotInfo[]>([]);
  const [lotId, setLotId] = useState("");
  const [summary, setSummary] = useState<WatSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Lot list follows product + period. Reset the selection when it reloads so
  // a stale lot_id from a previous product is never queried.
  useEffect(() => {
    if (!productId) {
      setLots([]);
      setLotId("");
      return;
    }
    let cancelled = false;
    fetchWatLots(productId, months)
      .then((res) => {
        if (cancelled) return;
        setLots(res.lots);
        setLotId(res.lots.length > 0 ? res.lots[0].lot_id : "");
      })
      .catch(() => {
        if (cancelled) return;
        setLots([]);
        setLotId("");
        setError("Failed to load WAT lots.");
      });
    return () => { cancelled = true; };
  }, [productId, months]);

  const loadSummary = useCallback(async () => {
    if (!productId || !lotId) return;
    setLoading(true);
    setError(null);
    try {
      setSummary(await fetchWatSummary(productId, lotId));
    } catch (e) {
      console.error("Failed to load WAT summary:", e);
      setError("Failed to load WAT summary.");
      setSummary(null);
    } finally {
      setLoading(false);
    }
  }, [productId, lotId]);

  useEffect(() => { void loadSummary(); }, [loadSummary]);

  const handleExport = async () => {
    if (!productId || !lotId) return;
    setExporting(true);
    try {
      await exportWatPdf(productId, lotId);
    } catch (e) {
      console.error("WAT PDF export failed:", e);
      setError("PDF export failed.");
    } finally {
      setExporting(false);
    }
  };

  const reds = summary?.items.filter((i) => i.status === "red").length ?? 0;
  const yellows = summary?.items.filter((i) => i.status === "yellow").length ?? 0;

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

        <label style={styles.field}>
          <span style={styles.fieldLabel}>Lot</span>
          <Select value={lotId} onChange={(e) => setLotId(e.target.value)}>
            {lots.length === 0 && <option value="">No lots</option>}
            {lots.map((l) => (
              <option key={l.lot_id} value={l.lot_id}>
                {l.lot_id} — {l.last_measured}
              </option>
            ))}
          </Select>
        </label>

        <Button onClick={handleExport} disabled={!lotId || loading || exporting}>
          {exporting ? "Generating…" : "Export PDF"}
        </Button>
        {exporting && <span style={styles.hint}>24 charts — this takes a while</span>}
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {loading && <div style={styles.hint}>Loading…</div>}

      {!loading && summary && summary.items.length === 0 && (
        <div style={styles.empty}>No WAT data for this lot.</div>
      )}

      {!loading && summary && summary.items.length > 0 && (
        <>
          <div style={styles.lotHeader}>
            <strong style={styles.lotId}>{summary.lot_id}</strong>
            <span>{summary.measured_date || "—"}</span>
            <span>{summary.wafer_count} wafers</span>
            <span>{summary.items.length} items</span>
            <span style={styles.counts}>
              <span style={styles.red}>{STATUS_MARK.red} {reds}</span>
              <span style={styles.yellow}>{STATUS_MARK.yellow} {yellows}</span>
            </span>
          </div>
          {/* Task 11 adds WatSummaryTable, Task 12 adds WatScatterGrid */}
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
  lotHeader: {
    display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap",
    padding: "12px 16px", marginBottom: 16,
    background: "var(--surface-card)", border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    fontSize: 13, color: "var(--muted)",
  },
  lotId: { color: "var(--ink)", fontSize: 14 },
  counts: { display: "inline-flex", gap: 14, marginLeft: "auto" },
  red: { color: "var(--error)", fontWeight: 600 },
  yellow: { color: "var(--warning)", fontWeight: 600 },
};
```

- [ ] **Step 5: `ReportPage.tsx` にタブを足す**

`ReportPage.tsx` の import に追加:

```typescript
import WatSummaryTab from "../components/wat/WatSummaryTab";
```

state に追加（`const [products, ...]` の直後）:

```typescript
  const [tab, setTab] = useState<"yield" | "wat">("yield");
```

`<PageTitle .../>` の直後、`<div style={styles.toolbar}>` の直前に挿入:

```tsx
        <div style={styles.tabs}>
          {([["yield", "Yield Trend"], ["wat", "PCM / WAT"]] as const).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              style={{ ...styles.tab, ...(tab === key ? styles.tabActive : {}) }}
            >
              {label}
            </button>
          ))}
        </div>
```

既存のツールバーのうち Process チップ・Generate・Export PDF は Yield タブ専用にする。`<div style={styles.toolbar}>` の中身を次のように囲む — **Product セレクトと mock インジケータは両タブ共通なので外に残す**:

```tsx
          {tab === "yield" && (
            <>
              <div style={styles.field}>
                <span style={styles.fieldLabel}>Process</span>
                {/* 既存の chipGroup をそのまま */}
              </div>
              <Button variant="primary" onClick={handleGenerate} disabled={disabled}>
                {loading ? "Loading…" : "Generate Report"}
              </Button>
              <Button onClick={() => exportPdf(buildRequest())} disabled={data === null || disabled}>
                Export PDF
              </Button>
            </>
          )}
```

`<ReportView data={data} request={request} />` を次に差し替え:

```tsx
        {tab === "yield"
          ? <ReportView data={data} request={request} />
          : <WatSummaryTab productId={productId} />}
```

`styles` に追加:

```typescript
  tabs: { display: "flex", gap: 4, marginBottom: 20 },
  tab: {
    padding: "8px 16px",
    borderRadius: "var(--radius-control)",
    border: "none",
    background: "transparent",
    color: "var(--muted)",
    fontSize: 14,
    fontWeight: 500,
    cursor: "pointer",
  },
  tabActive: { background: "var(--surface-soft)", color: "var(--ink)" },
```

- [ ] **Step 6: ビルドと lint**

```bash
cd frontend && npm run build && npm run lint
```
Expected: どちらも exit 0、警告なし

- [ ] **Step 7: 画面で確認**

```bash
# ターミナル1
cd backend && USE_MOCK_DATA=true uv run python -m uvicorn app.main:app --port 8000
# ターミナル2
cd frontend && npm run dev
```

`http://localhost:5173/report` を開き、以下を確認する:
- タブが 2 つ表示され、切り替わる
- Yield Trend タブが**従来どおり**動く（Process チップ、Generate、Export PDF）
- PCM / WAT タブで Period と Lot が選べ、ロットヘッダに件数が出る

- [ ] **Step 8: コミット**

```bash
git add frontend/src/types.ts frontend/src/api/client.ts frontend/src/theme.ts frontend/src/pages/ReportPage.tsx frontend/src/components/wat/WatSummaryTab.tsx
git commit -m "feat(wat): Report page tabs and PCM/WAT lot selection"
```

---

### Task 11: サマリーテーブルとウェハ別トレンド

**Files:**
- Create: `frontend/src/components/wat/WatSummaryTable.tsx`
- Create: `frontend/src/components/wat/WatItemTrendChart.tsx`
- Modify: `frontend/src/components/wat/WatSummaryTab.tsx`

**Interfaces:**
- Consumes: Task 10 の型と `theme.ts` のトークン、既存 `ui/tableStyles.ts`
- Produces: `<WatSummaryTable items={...} />`、`<WatItemTrendChart item={...} />`

- [ ] **Step 1: 数値整形ヘルパとテーブルを作る**

`frontend/src/components/wat/WatSummaryTable.tsx` を新規作成:

```tsx
import { useState } from "react";
import type { WatItemStats } from "../../types";
import { STATUS_COLOR, STATUS_MARK } from "../../theme";
import WatItemTrendChart from "./WatItemTrendChart";
import { tableStyles } from "../../ui/tableStyles";

/** Four significant digits, so 0.4021 and 1042.6 read at the same width. */
export function fmtValue(v: number | null): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const abs = Math.abs(v);
  if (abs !== 0 && (abs < 1e-3 || abs >= 1e6)) return v.toExponential(3);
  return String(Number(v.toPrecision(4)));
}

export function fmtCpk(cpk: number | null, state: string): string {
  if (state === "infinite") return "∞";
  if (state === "value" && cpk !== null) return cpk.toFixed(2);
  return "—";
}

interface Props {
  items: WatItemStats[];
}

export default function WatSummaryTable({ items }: Props) {
  const [openItem, setOpenItem] = useState<string | null>(null);

  return (
    <div style={styles.card}>
      <table style={tableStyles.table}>
        <thead>
          <tr>
            <th style={{ ...tableStyles.th, ...styles.markCol }} />
            <th style={tableStyles.th}>Item</th>
            <th style={tableStyles.th}>Unit</th>
            <th style={tableStyles.thNum}>Low</th>
            <th style={tableStyles.thNum}>High</th>
            <th style={tableStyles.thNum}>N</th>
            <th style={tableStyles.thNum}>Mean</th>
            <th style={tableStyles.thNum}>σ</th>
            <th style={tableStyles.thNum}>Min</th>
            <th style={tableStyles.thNum}>Max</th>
            <th style={tableStyles.thNum}>Cpk</th>
            <th style={tableStyles.thNum}>OOS</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const open = openItem === item.item_name;
            return [
              <tr
                key={item.item_name}
                onClick={() => setOpenItem(open ? null : item.item_name)}
                style={{
                  ...styles.row,
                  ...(item.status === "red" ? styles.rowRed : {}),
                  ...(item.status === "yellow" ? styles.rowYellow : {}),
                  ...(open ? styles.rowOpen : {}),
                }}
              >
                <td style={{ ...tableStyles.td, color: STATUS_COLOR[item.status] }}>
                  {STATUS_MARK[item.status]}
                </td>
                <td style={tableStyles.td}>{item.item_name}</td>
                <td style={tableStyles.td}>{item.unit}</td>
                <td style={tableStyles.tdNum}>{fmtValue(item.spec_low)}</td>
                <td style={tableStyles.tdNum}>{fmtValue(item.spec_high)}</td>
                <td style={tableStyles.tdNum}>{item.n}</td>
                <td style={tableStyles.tdNum}>{fmtValue(item.mean)}</td>
                <td style={tableStyles.tdNum}>{fmtValue(item.sigma)}</td>
                <td style={tableStyles.tdNum}>{fmtValue(item.min)}</td>
                <td style={tableStyles.tdNum}>{fmtValue(item.max)}</td>
                <td style={tableStyles.tdNum}>{fmtCpk(item.cpk, item.cpk_state)}</td>
                <td
                  style={tableStyles.tdNum}
                  title={item.oos_count > 0 ? `${item.oos_pct.toFixed(3)} % of measurements` : undefined}
                >
                  {item.oos_count}
                </td>
              </tr>,
              open ? (
                <tr key={`${item.item_name}-chart`}>
                  <td colSpan={12} style={styles.chartCell}>
                    <WatItemTrendChart item={item} />
                  </td>
                </tr>
              ) : null,
            ];
          })}
        </tbody>
      </table>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: "var(--surface-card)",
    border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    padding: 8,
    marginBottom: 20,
    overflowX: "auto",
  },
  markCol: { width: 24 },
  row: { cursor: "pointer" },
  rowRed: { background: "rgba(198, 69, 69, 0.06)" },
  rowYellow: { background: "rgba(212, 160, 23, 0.08)" },
  rowOpen: { background: "var(--surface-soft)" },
  chartCell: { padding: "8px 4px 16px" },
};
```

`tableStyles` に `th` / `thNum` / `td` / `tdNum` が無い場合は、既存の export 名に合わせて読み替える（`frontend/src/ui/tableStyles.ts` を確認すること）。

- [ ] **Step 2: トレンドチャートを作る**

`frontend/src/components/wat/WatItemTrendChart.tsx` を新規作成:

```tsx
import Plot from "react-plotly.js";
import type { WatItemStats } from "../../types";
import { INK, MUTED_SOFT, SPEC_LINE_COLOR, plotlyBaseLayout } from "../../theme";

interface Props {
  item: WatItemStats;
}

/** Wafer means with ±3σ whiskers and the spec limits. One series, so no
 *  legend — the title names it. */
export default function WatItemTrendChart({ item }: Props) {
  const series = item.wafer_series;
  const shapes = [];
  const annotations = [];
  for (const [limit, label] of [[item.spec_low, "LSL"], [item.spec_high, "USL"]] as const) {
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

  const unit = item.unit ? ` [${item.unit}]` : "";

  return (
    <Plot
      data={[{
        x: series.map((w) => w.wafer_id),
        y: series.map((w) => w.mean),
        type: "scatter",
        mode: "lines+markers",
        line: { color: INK, width: 2 },
        marker: { size: 8, color: INK },
        error_y: {
          type: "data",
          array: series.map((w) => (w.sigma === null ? 0 : w.sigma * 3)),
          visible: true,
          color: "rgba(20,20,19,0.35)",
          thickness: 1.2,
          width: 3,
        },
        hovertemplate: "Wafer %{x}<br>%{y:.4g}<extra></extra>",
      }]}
      layout={{
        ...plotlyBaseLayout(),
        title: { text: `${item.item_name}${unit}`, font: { size: 13 } },
        height: 300,
        margin: { l: 64, r: 56, t: 40, b: 44 },
        showlegend: false,
        xaxis: {
          title: { text: "Wafer #", font: { size: 11, color: MUTED_SOFT } },
          gridcolor: "rgba(0,0,0,0.05)",
          zeroline: false,
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

- [ ] **Step 3: タブに組み込む**

`WatSummaryTab.tsx` の import に追加:

```typescript
import WatSummaryTable from "./WatSummaryTable";
```

`{/* Task 11 adds WatSummaryTable, Task 12 adds WatScatterGrid */}` を次に置換:

```tsx
          <WatSummaryTable items={summary.items} />
```

- [ ] **Step 4: ビルドと lint**

```bash
cd frontend && npm run build && npm run lint
```
Expected: どちらも exit 0

- [ ] **Step 5: 画面で確認**

モックサーバと dev サーバを立て、`http://localhost:5173/report` の PCM / WAT タブで:
- 30 項目が `ITEM_NAME` 昇順で並ぶ
- 赤（`VTHN_ULVT`）と黄（`RS_NDIFF`）の行に色と記号が付く
- 行をクリックするとトレンドチャートが直下に開き、もう一度クリックで閉じる
- チャートに規格線 LSL / USL と誤差棒が出る

- [ ] **Step 6: コミット**

```bash
git add frontend/src/components/wat/
git commit -m "feat(wat): item summary table with wafer trend drill-down"
```

---

### Task 12: 散布図グリッドと最終確認

**Files:**
- Create: `frontend/src/components/wat/WatScatterGrid.tsx`
- Modify: `frontend/src/components/wat/WatSummaryTab.tsx`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: Task 10 の型とトークン
- Produces: `<WatScatterGrid pairs={...} />`

- [ ] **Step 1: 散布図グリッドを作る**

`frontend/src/components/wat/WatScatterGrid.tsx` を新規作成:

```tsx
import { useState } from "react";
import Plot from "react-plotly.js";
import type { WatScatterPair, WatScatterPlot } from "../../types";
import { MUTED_SOFT, SPEC_LINE_COLOR, WAFER_COLORSCALE, plotlyBaseLayout } from "../../theme";

const PLOT_TITLES: Record<WatScatterPlot["kind"], string> = {
  vth_np: "Vth  n/p",
  idsat_np: "Idsat  n/p",
  ion_vt_n: "Ion-Vt  (N)",
  ion_vt_p: "Ion-Vt  (P)",
};

function axisLabel(item: string, unit: string): string {
  return unit ? `${item} [${unit}]` : item;
}

function ScatterPlot({ plot }: { plot: WatScatterPlot }) {
  if (plot.points.length === 0) {
    return (
      <div style={styles.empty}>
        <div style={styles.emptyTitle}>{PLOT_TITLES[plot.kind]}</div>
        <div>No data</div>
      </div>
    );
  }

  const [xLo, xHi] = plot.x_spec;
  const [yLo, yHi] = plot.y_spec;
  const shapes =
    xLo !== null && xHi !== null && yLo !== null && yHi !== null
      ? [{
          type: "rect" as const,
          x0: xLo, x1: xHi, y0: yLo, y1: yHi,
          line: { color: "rgba(198,69,69,0.45)", width: 1, dash: "dash" as const },
          fillcolor: "rgba(198,69,69,0.05)",
          layer: "below" as const,
        }]
      : [];

  return (
    <Plot
      data={[{
        x: plot.points.map((p) => p.x),
        y: plot.points.map((p) => p.y),
        type: "scatter",
        mode: "markers",
        marker: {
          size: 8,
          color: plot.points.map((p) => p.wafer_id),
          colorscale: WAFER_COLORSCALE,
          colorbar: { title: { text: "Wafer", font: { size: 10 } }, thickness: 10, len: 0.8 },
          line: { width: 1, color: "#ffffff" },
        },
        customdata: plot.points.map((p) => [p.wafer_id, p.site_no]),
        hovertemplate:
          "W%{customdata[0]} · site %{customdata[1]}<br>%{x:.4g}, %{y:.4g}<extra></extra>",
      }]}
      layout={{
        ...plotlyBaseLayout(),
        title: { text: PLOT_TITLES[plot.kind], font: { size: 13 } },
        height: 340,
        margin: { l: 62, r: 24, t: 40, b: 48 },
        showlegend: false,
        xaxis: {
          title: { text: axisLabel(plot.x_item, plot.x_unit), font: { size: 11, color: MUTED_SOFT } },
          gridcolor: "rgba(0,0,0,0.05)", zeroline: false,
        },
        yaxis: {
          title: { text: axisLabel(plot.y_item, plot.y_unit), font: { size: 11, color: MUTED_SOFT } },
          gridcolor: "rgba(0,0,0,0.05)", zeroline: false,
        },
        shapes,
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: "100%" }}
    />
  );
}

interface Props {
  pairs: WatScatterPair[];
}

/** One flavor at a time. Showing all 6 x 4 plots at once shrinks each below
 *  the size where 225 points and the wafer ramp can be read. */
export default function WatScatterGrid({ pairs }: Props) {
  const [active, setActive] = useState(0);
  if (pairs.length === 0) return null;

  const pair = pairs[Math.min(active, pairs.length - 1)];

  return (
    <div style={styles.card}>
      <div style={styles.chips}>
        {pairs.map((p, i) => (
          <button
            key={p.label}
            type="button"
            onClick={() => setActive(i)}
            style={{ ...styles.chip, ...(i === active ? styles.chipActive : {}) }}
          >
            {p.label}
          </button>
        ))}
        <span style={styles.legendHint}>colour = wafer number</span>
      </div>
      <div style={styles.grid}>
        {pair.plots.map((plot) => (
          <div key={plot.kind} style={styles.cell}>
            <ScatterPlot plot={plot} />
          </div>
        ))}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: "var(--surface-card)",
    border: "var(--hairline)",
    borderRadius: "var(--radius-card)",
    padding: 16,
    marginBottom: 20,
  },
  chips: { display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", marginBottom: 12 },
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
  legendHint: { marginLeft: "auto", fontSize: 12, color: "var(--muted-soft)" },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
    gap: 12,
  },
  cell: { minWidth: 0 },
  empty: {
    height: 340,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    color: "var(--muted-soft)",
    fontSize: 13,
    border: "1px dashed var(--hairline-color)",
    borderRadius: "var(--radius-control)",
  },
  emptyTitle: { color: "var(--muted)", fontWeight: 600 },
};
```

- [ ] **Step 2: タブに組み込む**

`WatSummaryTab.tsx` の import に追加:

```typescript
import WatScatterGrid from "./WatScatterGrid";
```

`<WatSummaryTable items={summary.items} />` の直後に追加:

```tsx
          <WatScatterGrid pairs={summary.scatter_pairs} />
```

- [ ] **Step 3: モック製品に `wat:` を設定**

`backend/product_config.yaml` のモック製品（`P12345-A` に対応する nickname）に追加し、散布図の経路をモックで確認できるようにする:

```yaml
    wat:
      pairs:
        - label: Core RVT
          vth:   {n: VTHN_RVT,   p: VTHP_RVT}
          idsat: {n: IDSATN_RVT, p: IDSATP_RVT}
        - label: Core LVT
          vth:   {n: VTHN_LVT,   p: VTHP_LVT}
          idsat: {n: IDSATN_LVT, p: IDSATP_LVT}
        - label: Core HVT
          vth:   {n: VTHN_HVT,   p: VTHP_HVT}
          idsat: {n: IDSATN_HVT, p: IDSATP_HVT}
        - label: Core ULVT
          vth:   {n: VTHN_ULVT,   p: VTHP_ULVT}
          idsat: {n: IDSATN_ULVT, p: IDSATP_ULVT}
        - label: IO 2.5V
          vth:   {n: VTHN_IO25,   p: VTHP_IO25}
          idsat: {n: IDSATN_IO25, p: IDSATP_IO25}
        - label: IO 1.8V
          vth:   {n: VTHN_IO18,   p: VTHP_IO18}
          idsat: {n: IDSATN_IO18, p: IDSATP_IO18}
```

`product_config.yaml` が git 管理外の場合は `product_config.yaml.example` にのみ追記し、その旨を報告する。

- [ ] **Step 4: ビルドと lint**

```bash
cd frontend && npm run build && npm run lint
```
Expected: どちらも exit 0

- [ ] **Step 5: バックエンド全テスト**

```bash
cd backend && uv run python -m pytest tests/ -q
```
Expected: 失敗 0

- [ ] **Step 6: 画面で通し確認**

モックサーバと dev サーバを立て、`http://localhost:5173/report` で:
- PCM / WAT タブに 6 つのフレーバーチップが出て切り替わる
- 各フレーバーで 4 図が出る（Vth n/p、Idsat n/p、Ion-Vt N、Ion-Vt P）
- 点がウェハ番号で薄→濃のグラデーションになり、カラーバーが出る
- 規格範囲の矩形が描かれる
- Export PDF が動き、A4 縦の PDF がダウンロードされる
- **Yield Trend タブが従来どおり動く**

- [ ] **Step 7: `CLAUDE.md` を更新**

`## Oracle DB Schema` セクションの末尾に追加:

```markdown
### PCM/WAT (`WAT_MEASURE_DETAIL`)
Report ページの PCM / WAT タブが読む単一テーブル。粒度は製品 × ロット × ウェハ ×
サイト × 測定項目で、規格値 (`SPEC_LOW`/`SPEC_HIGH`) と単位 (`ITEM_UNIT`) を
自身が持つ。`PRODUCT_ID` は `product_config.yaml` の `product_id` と同値。

**この工程は rework 運用がないため `REWORK_NEW` / `DEL_FLAG` でフィルタしない。**
SEMI_CP_* 系の `REWORK_NEW = 0` 必須ルールをここに持ち込むと、有効な行を落とす。

散布図 (Vth n/p, Idsat n/p, Ion-Vt) に使う項目名は製品ごとに違うため、
`product_config.yaml` の `wat: pairs:` で対応付ける。未設定なら散布図セクションは
非表示になり、サマリーテーブルだけが出る。
```

`### Key Backend Files` に追加:

```markdown
- `backend/app/services/wat_service.py` — PCM/WAT のロット単位統計・Cpk 判定・散布図ペアリング
- `backend/app/services/wat_pdf_service.py` — PCM/WAT の A4 縦 PDF
- `backend/app/services/pdf_common.py` — 両 PDF 共通のブランディング/フッタ
```

- [ ] **Step 8: コミット**

```bash
git add frontend/src/components/wat/ backend/product_config.yaml.example CLAUDE.md
git commit -m "feat(wat): scatter plot grid with per-flavor switching"
```

---

## 完了条件

- `cd backend && uv run python -m pytest tests/ -q` が **失敗 0**（着手前は 76 passed。新規テストが加わるので総数は増える）
- `cd frontend && npm run build && npm run lint` がどちらも exit 0
- モックモードで Report ページの両タブが動作し、Yield Trend の挙動が従来どおり
- PCM / WAT タブで PDF が A4 縦で出力される
- PDF 生成時間が Task 9 Step 7 に記録されている
