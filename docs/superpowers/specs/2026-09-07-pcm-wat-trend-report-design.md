# PCM/WAT トレンドレポート — 設計仕様

**日付:** 2026-09-07
**対象:** PCM/WAT を「ロット単体レポート」と「トレンドレポート（既定 3 ヶ月）」の 2 本に分ける

## 1. 目的とスコープ

**目的:** 期間内の全ロットを横断して、各測定項目のロット間ドリフトと通算の工程能力を確認し、報告用 PDF を出力する。

既存の PCM/WAT は 2026-07-28 の仕様どおり **単一ロットに閉じている**（`wat_service.py` 冒頭「Everything here is scoped to a single lot」）。本仕様はその単ロットレポートを一切変更せず、その隣に**ロット横断のトレンドレポートを新設**する。

**スコープ内**

- 製品 → 期間（1 / 3 / 6 ヶ月、既定 3）を選び、期間内の全ロットを 1 度に集計
- 期間通算の項目別統計サマリーテーブル（全項目）
- 項目行クリックで、その項目の**ロット別トレンド**（ロット平均 ±3σ + 規格線）を展開
- 上記一式の PDF 出力（A4 縦、全項目のロットトレンドチャートを収録）

**スコープ外**

- 既存の単ロットレポート（`/wat/lots`, `/wat/summary`, `/wat/export-pdf`）の挙動変更
- トレンド側の散布図（Vth n/p、Idsat n/p、Ion-Vt）— 単ロットレポート専用のまま
- 歩留り側（Yield Trend タブ）の挙動変更
- ウェハ別の粒度でのトレンド（X 軸はロットであり、ウェハではない）

**用語:** 以下「単ロットレポート」= 既存機能、「トレンドレポート」= 本仕様で追加する機能。

## 2. データソース

単ロットレポートと同じ `WAT_MEASURE_DETAIL` 単一テーブル。粒度は製品 × ロット × ウェハ × サイト × 測定項目で、規格値（`SPEC_LOW` / `SPEC_HIGH`）と単位（`ITEM_UNIT`）を自身が持つ。

**この工程は rework 運用がないため `REWORK_NEW` / `DEL_FLAG` でフィルタしない。** SEMI_CP_* 系の `REWORK_NEW = 0` 必須ルールをここに持ち込むと有効な行を落とす（CLAUDE.md）。

**データ量の見積り:** 25 ウェハ × 9 サイト × 30 項目 = 6,750 行/ロット。3 ヶ月で 10 ロット前後なら約 7 万行。pandas で一括処理して問題ない規模であり、ロットごとに N 回クエリを投げる必要はない。

## 3. クエリ

### 3.1 トレンド明細（新規）

期間内の全ロットの明細を **1 クエリ**で取得する。

```sql
SELECT LOT_ID     AS lot_id,
       WAFER_ID   AS wafer_id,
       SITE_NO    AS site_no,
       ITEM_NAME  AS item_name,
       ITEM_UNIT  AS item_unit,
       SPEC_LOW   AS spec_low,
       SPEC_HIGH  AS spec_high,
       MEAS_DATA  AS meas_data,
       START_TIME AS start_time
FROM WAT_MEASURE_DETAIL
WHERE <PRODUCT_ID = :pid | PRODUCT_ID LIKE :pid>
  AND START_TIME >= :start_dt
  AND START_TIME <  :end_dt
ORDER BY item_name, start_time, lot_id, wafer_id, site_no
```

- 上限は**排他**。呼び出し側が翌日を渡すことで当日測定分まで含む（`build_wat_lots_query` と同じ約束）。
- バインド名の `_dt` サフィックスは必須。裸の `START` / `END` は Oracle の予約語で、ドライバが実行時に ORA-01745 を返す（実 DB に当たらないテストでは検出できない）。`tests/test_query_bind_names.py` に追加する。
- `PRODUCT_ID` の等値／`LIKE` の切り替えは既存 `_product_id_clause()` をそのまま使う。

### 3.2 正規化の共通化

`query_wat_detail()` が持つ境界での正規化を `_normalize_detail(df)` に括り出し、単ロット用とトレンド用の両方から呼ぶ。

- `ITEM_NAME` / `ITEM_UNIT` は Oracle CHAR 由来で空白パディングされるため `str.strip()`（未処理だと `wat: pairs` の項目名が一致しない）
- `MEAS_DATA` / `SPEC_LOW` / `SPEC_HIGH` は `decimal.Decimal` で返り得るため `pd.to_numeric(errors="coerce")`（object dtype のままだと下流の `Series.std(ddof=1)` が TypeError）

片方だけ直る事故を防ぐことがこの抽出の目的であり、挙動は現状と同一にする。

## 4. 統計の定義

### 4.1 期間通算統計（テーブルの各行）

**期間内の全ロットの生サイト測定値をプールして**算出する。ロット平均の平均ではない。

- `n` / `mean` / `sigma` / `min` / `max` / `oos_count` / `oos_pct` / `cpk` / `cpk_state` / `status` は単ロットと同じ関数で計算する
- したがってロット間ばらつきが σ に載り、単ロット Cpk より厳しい値になる。これは意図した挙動であり、期間を通した工程能力の定義として正しい

Cpk の境界条件（n < 2、σ = 0、片側規格、JSON が Infinity を運べないための `cpk_state`）と判定色（red / yellow / gray / ok、`CPK_RED = 1.00`、`CPK_YELLOW = 1.33`、strict less-than）は単ロットと**完全に同一の関数**を使う。分岐を増やさない。

### 4.2 ロット別統計（`lot_series` の各点）

各ロット内の生サイト測定値から `n` / `mean` / `sigma` / `cpk` / `cpk_state` / `status` を算出する。規格値は 4.3 で決まった期間内の代表値を全ロットに適用する（ロットごとに規格を引き直すと、チャートの規格線と点の判定がずれる）。

- `sigma` は n ≥ 2 のときのみ。1 サイトしか測っていないロットはエラーバーを描かない（0 として描かない）
- 並び順は `measured_date`（そのロットの `START_TIME` の最大値）の**昇順＝古い順**。`get_wat_lots()` が新しい順で返すのとは逆であることに注意

### 4.3 規格値の一意性

期間内に複数の異なる規格値が現れた場合、既存 `resolve_spec()` と同じく**最頻値を採用し WARNING をログする**（同数の場合は昇順ソートの先頭）。ロットをまたぐと規格改訂が現実に起こり得るため、黙って片方を選ぶのではなくログに残すことが重要。

### 4.4 統計コアの抽出

`compute_item_stats()` から系列生成部分を除いた統計コアを `_item_core(group, item_name)` として抽出する。

- 単ロット: `_item_core()` + `wafer_series`（現行と**バイト単位で同一の出力**）
- トレンド: `_item_core()` + `lot_series`

Cpk 計算・OOS カウント・判定は 1 箇所にとどめる。

## 5. API

### `GET /api/wat/trend`

| パラメータ | 型 | 既定 | 説明 |
|---|---|---|---|
| `product_id` | str | 必須 | UI が選択している DB の PRODUCT_ID |
| `months` | int | 3 | 1〜6。`today - months*30` から `today + 1 日` まで |

レスポンス `WatTrendResponse`:

```jsonc
{
  "product_id": "...",
  "display_name": "...",
  "months": 3,
  "start_date": "2026-06-09",   // 含む
  "end_date": "2026-09-08",     // 含まない（排他上限）
  "lots": [ { "lot_id": "...", "last_measured": "2026-09-01", "wafer_count": 25 } ],
  "items": [
    {
      "item_name": "VTHN_ULVT", "unit": "V",
      "spec_low": -0.1, "spec_high": 0.1,
      "n": 6750, "mean": 0.02, "sigma": 0.018,
      "min": -0.05, "max": 0.09,
      "cpk": 1.21, "cpk_state": "value",
      "oos_count": 3, "oos_pct": 0.0444,
      "status": "red",
      "lot_series": [
        { "lot_id": "...", "measured_date": "2026-06-14", "n": 675,
          "mean": 0.019, "sigma": 0.017,
          "cpk": 1.30, "cpk_state": "value", "status": "yellow" }
      ]
    }
  ]
}
```

- `lots` は**新しい順**（画面のヘッダ帯で「最新ロット」を出すため）、`lot_series` は**古い順**（チャートの X 軸順）。両者の順序が違うことを明記する
- `items` は `item_name` の昇順（単ロットと同じ）
- 期間内にデータがない場合は `items: []`, `lots: []` を 200 で返す（404 にしない）

### `POST /api/wat/export-trend-pdf`

```jsonc
{ "product_id": "...", "months": 3 }
```

`WatTrendResponse` を組み立て直してから PDF を生成する（`/wat/export-pdf` が `get_wat_summary()` を呼び直すのと同じ作法）。ファイル名は `WAT_TREND_<product_id>_<months>M`。

### 既存エンドポイント

`GET /api/wat/lots`、`GET /api/wat/summary`、`POST /api/wat/export-pdf` は**変更しない**。

## 6. 画面

### 6.1 タブ構成

Report ページ上部のタブを 2 つから 3 つにする。

```
┌─────────────┬───────────────┬─────────────────┐
│ Yield Trend │ PCM/WAT (Lot) │ PCM/WAT (Trend) │
└─────────────┴───────────────┴─────────────────┘
```

`ReportPage.tsx` の `tab` の型を `"yield" | "wat" | "watTrend"` に拡張する。Product セレクタはページ共通のまま 3 タブが共有し、Process チップ・Generate・Export は従来どおり `yield` タブのときだけ出す。

### 6.2 トレンドタブのツールバー

`Period`（Last 1 / 3 / 6 months、既定 3）と `Export PDF` のみ。**Lot セレクタは持たない** — これが単ロットタブとの一番の見分けになる。

### 6.3 レイアウト

1. ヘッダ帯: 期間（`start_date` 〜 最新ロットの測定日）／ロット数／項目数／red・yellow 件数
2. サマリーテーブル（全項目）
3. （散布図セクションなし）

### 6.4 サマリーテーブルとチャート展開

既存 `WatSummaryTable` を**そのまま再利用**する。列構成・判定色・行クリックでの展開という操作感を単ロット側と揃えるため。

- 展開時に描画するチャートだけがロット別トレンドに替わる
- 全項目のチャートを同時に並べない。30 項目ぶんの Plotly インスタンスを一度に生成する負荷を避け、かつ単ロット側と同じ操作で読めるようにする
- `WatSummaryTable` の props を具体的に次の形にする。系列の種類をテーブルが知らずに済み、展開チャートの差し替えが呼び出し側の責務になる

```ts
type WatTableRow = Omit<WatItemStats, "wafer_series">;   // スカラー列のみ
interface Props {
  items: WatTableRow[];
  renderChart: (item: WatTableRow) => React.ReactNode;   // 展開行の中身
}
```

単ロットタブは `renderChart` にウェハトレンドを、トレンドタブはロットトレンドを渡す。行を開閉する状態管理はテーブル側に残す

### 6.5 チャートの共通化

`WatItemTrendChart` を X 軸ラベルと系列を受け取る汎用形に一般化し、2 用途で共有する。

| 用途 | X 軸 | 点 | エラーバー |
|---|---|---|---|
| 単ロット | Wafer #（数値） | ウェハ平均 | ±3σ（n ≥ 2 のみ） |
| トレンド | Lot（カテゴリ、古い順） | ロット平均 | ±3σ（n ≥ 2 のみ） |

規格線（LSL / USL の破線 + 右端ラベル）、タイトル `項目名 [単位]`、`displayModeBar: false` は共通。Plotly レイアウトを 2 箇所にコピーしない。

トレンド側のマーカーは、そのロットの `status` が red / yellow のときだけ色を変える（それ以外は既存の `INK`）。どのロットが外れたかを一目で追えるようにするため。

## 7. PDF（A4 縦）

```
1 ページ目〜: ヘッダ（製品名 / 期間 / ロット数 / 項目数）
              全項目サマリーテーブル
続き        : 全項目のロットトレンドチャート 2 段/ページ
```

30 項目なら概ね 16 ページ。単ロット PDF と違い**全項目のチャートを収録する**（単ロット PDF は red / yellow のみ）。報告書として期間の全項目を残すことがトレンドレポートの目的だから。

`count_pages()` と同様に、総ページ数は描画前に純関数として算出する（ReportLab は完成したページに戻れないため「Page n of N」の N が先に必要）。

図はすべて描画前に確定するので、`_render_batch()` で kaleido を 1 回だけ呼ぶ（図ごとに呼ばない）。

### 7.1 PDF 部品の共通化

既存 `wat_pdf_service.py`（404 行）から、両 PDF が共有する部品を `wat_pdf_common.py` に括り出す。

- `STATUS_MARK` / `STATUS_RGB`
- `COL_WIDTHS` / `COL_HEADERS` / `ROW_H` / `TABLE_FONT` / `PAGE_BREAK_MARGIN`
- `fmt_value()` / `fmt_cpk()`
- `_base_layout()` / `_axis()` / `_render_batch()`
- テーブルヘッダ描画・項目行描画・`rows_per_page()`

`wat_pdf_service.py` には単ロット固有のレイアウト（散布図 2×2、ウェハトレンド、ロットヘッダ）だけを残す。テーブル描画が 2 ファイルにコピーされ片方だけ直る状態を作らないことが目的。

## 8. ファイル構成

### バックエンド（新規）

- `app/services/wat_trend_service.py` — `get_wat_trend(nickname, product_id, months)`
- `app/services/wat_trend_pdf_service.py` — `generate_wat_trend_pdf(trend)`
- `app/services/wat_pdf_common.py` — 両 PDF 共通の部品（7.1）

### バックエンド（変更）

- `app/services/wat_queries.py` — `WAT_TREND_COLUMNS`、`build_wat_trend_query()`、`query_wat_trend()`、`_normalize_detail()` 抽出
- `app/services/wat_service.py` — `_item_core()` 抽出（公開 API と出力は不変）
- `app/services/wat_pdf_service.py` — 共通部品を `wat_pdf_common` から import する形に整理
- `app/services/mock_data.py` — `mock_wat_trend_dataframe(product_id, months)`
- `app/models/schemas.py` — `WatLotPoint`、`WatTrendItemStats`、`WatTrendResponse`、`WatTrendExportRequest`
- `app/routers/wat.py` — `GET /wat/trend`、`POST /wat/export-trend-pdf`

### フロントエンド（新規）

- `components/wat/WatTrendTab.tsx`

新しいチャートコンポーネントは作らない。ロットトレンドは汎用化した `WatItemTrendChart` に系列を渡して描く（6.5）。

### フロントエンド（変更）

- `pages/ReportPage.tsx` — 3 タブ化
- `components/wat/WatItemTrendChart.tsx` — 汎用化（6.5）
- `components/wat/WatSummaryTable.tsx` — props を緩め、展開チャートを差し替え可能に
- `api/client.ts` — `fetchWatTrend()`、`exportWatTrendPdf()`
- `types/index.ts` — `WatLotPoint`、`WatTrendItemStats`、`WatTrendResponse`

## 9. モックデータ

`mock_wat_trend_dataframe(product_id, months)` は既存の `mock_wat_lots(product_id, months)` が返す各ロットについて `mock_wat_dataframe(product_id, lot_id)` を呼び、`lot_id` 列を付けて連結する。

- 既存のシード方式をそのまま使うので決定論的
- 意図的に劣化させてある VTHN_ULVT（red）と RS_NDIFF（yellow）がトレンド側でも赤/黄で出るため、mock モードで判定パスが確認できる

## 10. エラー処理

- クエリ失敗は `503 WAT data source unavailable`（既存の `/wat/lots` と同じ）
- PDF 生成失敗は `500 PDF generation failed: <理由>`（既存の `/wat/export-pdf` と同じ）
- 期間内にデータなしは 200 + 空配列。画面は "No WAT data for this period." を出す
- 展開したチャートの `lot_series` が 1 点しかない場合もそのまま描く（線は引けないがマーカーと規格線には意味がある）

## 11. テスト

TDD で先に書く。

**`tests/test_wat_trend_queries.py`**
- `build_wat_trend_query()` が `%` 付き product_id で `LIKE`、なしで `=` を出す
- 上限が排他（`<`）であること
- バインド名が `pid` / `start_dt` / `end_dt` であること
- 空の product_id で空 SQL を返す

**`tests/test_query_bind_names.py`**（追記）
- トレンドクエリのバインド名に Oracle 予約語が含まれないこと

**`tests/test_wat_trend_stats.py`**
- 期間通算統計が全ロットの生サイト値をプールした結果と一致する（ロット平均の平均と**異なる**ことも明示的に確認）
- `lot_series` が測定日の昇順
- ロット跨ぎで規格値が食い違う場合、最頻値が採用され WARNING が出る
- n < 2 のロットは `sigma = None`
- `_item_core()` 抽出後も `get_wat_summary()` の出力が変わらない（回帰）

**`tests/test_wat_trend_api.py`**
- mock モードで `GET /api/wat/trend` が 200 と期待するキーを返す
- `months` のバリデーション（0 や 7 は 422）
- データのない product_id で 200 + 空配列

**`tests/test_wat_trend_pdf.py`**
- ページ数 = テーブルのページ数 + `ceil(項目数 / 2)`
- 項目 0 件でも例外を出さず PDF バイト列を返す

## 12. 決定事項の要約

| 論点 | 決定 | 理由 |
|---|---|---|
| トレンドの X 軸 | ロット（測定日昇順） | 報告単位がロット。ウェハ粒度は 3 ヶ月では点が多すぎる |
| 掲載項目 | 全項目（テーブル + チャート） | 期間の全項目を報告書に残すため |
| 画面のチャート | 行クリックで展開 | 単ロット側と同じ操作感。30 個同時描画を避ける |
| PDF のチャート | 全項目を収録 | 単ロット PDF（red/yellow のみ）との役割の違い |
| 通算統計 | 生サイト値をプール | 既存の Cpk 定義の素直な延長。ロット間ばらつきを含める |
| 散布図 | トレンド側は持たない | 3 ヶ月分のサイト点は数万点で描画・PDF が重い。後から追加は容易 |
| UI 分割 | 上部タブ 3 つ | 平ら。Product セレクタはページ共通のまま |
| 期間 | 1 / 3 / 6 ヶ月、既定 3 | 既存 `/wat/lots` の `months` と同じ range |
