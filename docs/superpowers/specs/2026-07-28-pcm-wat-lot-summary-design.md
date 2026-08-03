# PCM/WAT ロットサマリー — 設計仕様

**日付:** 2026-07-28
**対象:** Report ページに 2 つ目の機能として PCM/WAT サマリー表示と PDF 出力を追加する

## 1. 目的とスコープ

**目的:** 選択した 1 ロットの WAT（パラメトリック測定）の出来栄えを確認し、報告用 PDF を出力する。

用途は「ロット単位の出来栄え確認」であり、期間横断のトレンド分析ではない。したがって表示・集計・PDF のすべてが**単一ロットに閉じる**。

**スコープ内**

- 製品 → 期間 → ロットを選び、そのロットの項目別統計サマリーを表示
- 項目行クリックで、その項目のウェハ別トレンドを展開
- Vth / Idsat の n/p 散布図と Ion-Vt 散布図
- 上記一式の PDF 出力（A4 縦）

**スコープ外**

- 複数ロットの比較・期間集計
- 歩留り側（Yield Trend タブ）の挙動変更
- Id-Vg / Id-Vd の掃引カーブ（データソースが持たない）
- ウェハ面内マップ表示（既存の Wafer Map ページが担当）

## 2. データソース

Oracle テーブル `WAT_MEASURE_DETAIL`（既存の歩留りテーブルと同一 DB）。

粒度は **1 行 = 製品 × ロット × ウェハ × サイト × 測定項目**。

使用する列:

| 列 | 用途 |
| --- | --- |
| `PRODUCT_ID` | 製品の絞り込み。`product_config.yaml` の `product_id` と**同じ値**が入る |
| `LOT_ID` | ロット識別。`NOT NULL` のためロット軸に使う |
| `WAFER_ID` | ウェハ番号（`NUMBER(3,0)`） |
| `SITE_NO` | 測定サイト番号 |
| `ITEM_NAME` | 測定項目名 |
| `ITEM_UNIT` | 単位（表示用） |
| `SPEC_LOW` / `SPEC_HIGH` | 規格下限 / 上限。NULL あり |
| `MEAS_DATA` | 測定値 |
| `START_TIME` | 測定日時。期間絞り込みとロット日付の表示に使う |

**使用しない列と理由**

- `DEL_FLAG`, `REWORK_NEW`, `REWORK_CNT` — この工程では rework 運用がないため、フィルタしない
- `SUBSTRATE_ID` — nullable であり、`LOT_ID` があれば足りる
- `FAB_PRODUCT_ID`, `TSTR_NAME`, `X`, `Y`, `REGIST_DATE` — 本機能では参照しない

> 注: 既存の `SEMI_CP_*` 系では `REWORK_NEW = 0` を**両テーブルに**掛けることが必須（CLAUDE.md 参照）。本テーブルは単表参照かつ rework 運用がないため、この制約は適用しない。

## 3. クエリ

### 3.1 ロット一覧

```sql
SELECT LOT_ID,
       MAX(START_TIME)          AS last_measured,
       COUNT(DISTINCT WAFER_ID) AS wafer_count
FROM WAT_MEASURE_DETAIL
WHERE PRODUCT_ID = :pid
  AND START_TIME >= :start
  AND START_TIME <  :end
GROUP BY LOT_ID
ORDER BY MAX(START_TIME) DESC
```

期間は直近 1 / 3 / 6 ヶ月から選択。新しいロットが先頭に並ぶ。

境界の定義: `:start` = 今日から N ヶ月前の 00:00、`:end` = **翌日の 00:00**（当日測定分を取りこぼさないため上限は排他）。

### 3.2 ロット明細

```sql
SELECT WAFER_ID, SITE_NO, ITEM_NAME, ITEM_UNIT,
       SPEC_LOW, SPEC_HIGH, MEAS_DATA
FROM WAT_MEASURE_DETAIL
WHERE PRODUCT_ID = :pid
  AND LOT_ID = :lot
```

1 ロット分（60 項目 × 25 ウェハ × 9 サイト ≒ 13,500 行）を一括取得し、以降の集計はすべてバックエンドの pandas で行う。

## 4. 統計の定義

### 4.1 項目別統計

母集団は**そのロットの生の測定値全件**（ウェハ × サイト）。`MEAS_DATA IS NULL` の行は N から除外する。

| 指標 | 定義 |
| --- | --- |
| `n` | 有効測定値の件数 |
| `mean` | 平均 |
| `sigma` | 標本標準偏差（ddof=1） |
| `min` / `max` | 最小 / 最大 |
| `cpk` | 下表参照 |
| `oos_count` / `oos_pct` | 規格外の件数と率 |

### 4.2 Cpk と境界条件

JSON は `Infinity` を表現できないため、Cpk は**数値**と**状態**の 2 フィールドで返す。

- `cpk`: `number | null`
- `cpk_state`: `"value"` | `"infinite"` | `"undefined"`

| 状況 | `cpk` | `cpk_state` | 表示 |
| --- | --- | --- | --- |
| 両側規格あり | `min((USL − μ) / 3σ, (μ − LSL) / 3σ)` | `value` | 小数 2 桁 |
| 片側規格のみ | その片側だけで算出（Cpu または Cpl） | `value` | 小数 2 桁 |
| 規格が両方 NULL | `null` | `undefined` | `—` |
| σ = 0 かつ全数規格内 | `null` | `infinite` | `∞` |
| σ = 0 かつ規格外あり | `null` | `undefined` | `—`（判定は規格外により赤） |
| n < 2 | `null` | `undefined` | `—` |

### 4.3 規格値の一意性

同一ロット・同一 `ITEM_NAME` 内では `SPEC_LOW` / `SPEC_HIGH` は一定であることを前提とする。複数の値が混在した場合:

- 非 NULL 値の**最頻値**を採用する（同数の場合は昇順ソートで先頭）
- **WARNING ログを出力する**（データ異常の検知のため。黙って片方を選ばない）

### 4.4 判定

**上から順に評価し、最初に該当したものを採用する。**

| 順 | 判定 | 条件 | 記号 |
| --- | --- | --- | --- |
| 1 | 赤 | 規格外が 1 件以上、または（`cpk_state == "value"` かつ `cpk < 1.00`） | `●` |
| 2 | 黄 | `cpk_state == "value"` かつ `1.00 <= cpk < 1.33` | `▲` |
| 3 | グレー | `cpk_state == "undefined"` | `–` |
| 4 | 正常 | 上記以外（`cpk_state == "infinite"` を含む） | （無印） |

評価順を固定するのは、`n < 2` かつ規格外があるようなケースで「Cpk 算出不可（グレー）」が「規格外あり（赤）」を隠さないようにするため。規格外の存在は常に赤を優先する。

境界値は**未満**で判定する。`cpk == 1.00` は赤ではなく黄、`cpk == 1.33` は黄ではなく正常。

判定は**色と記号の両方**で表す。PDF を白黒印刷したとき色だけでは判定が失われるため、記号の併記は必須要件とする。

## 5. 散布図

### 5.1 4 種のプロット

1 つの「デバイスフレーバー」（Vt 種別）につき 4 図:

| プロット | `kind` | 横軸 | 縦軸 |
| --- | --- | --- | --- |
| Vth n/p | `vth_np` | Vth_n | Vth_p |
| Idsat n/p | `idsat_np` | Idsat_n | Idsat_p |
| Ion-Vt (N) | `ion_vt_n` | Vth_n | Idsat_n |
| Ion-Vt (P) | `ion_vt_p` | Vth_p | Idsat_p |

`plots` はこの 4 種をこの順で返す。

フレーバーは 6 種を想定するため、合計 24 図。

### 5.2 点の粒度とペアリング

1 点 = **1 ウェハ × 1 サイト**。同一 `WAFER_ID` かつ同一 `SITE_NO` の 2 項目の測定値を組にする。

- どちらか一方が欠損しているサイトは**その点を除外**する（片側だけをプロットしない）
- 点数は 25 ウェハ × 9 サイト ≒ 225 点

### 5.3 項目名の対応付け

`ITEM_NAME` の命名は製品ごとに異なるため、`product_config.yaml` に対応表を持つ。

```yaml
product_a:
  display_name: Product-A
  product_id: P12345-A
  # …既存の bin_group / processes / report ブロック…
  wat:
    pairs:
      - label: Core RVT
        vth:   { n: VTHN_RVT,   p: VTHP_RVT }
        idsat: { n: IDSATN_RVT, p: IDSATP_RVT }
      - label: Core LVT
        vth:   { n: VTHN_LVT,   p: VTHP_LVT }
        idsat: { n: IDSATN_LVT, p: IDSATP_LVT }
```

`pairs` は宣言順に表示する。

> 実際の `ITEM_NAME` の命名規則は後日ユーザーが補正する。実装は上記のスキーマに従い、値そのものには依存しない。

**未設定・不整合時の扱い**

| 状況 | 挙動 |
| --- | --- |
| `wat:` ブロックが無い | 散布図セクションを丸ごと非表示。サマリーテーブルは通常どおり表示 |
| `pairs` が空 | 同上 |
| 設定された `ITEM_NAME` が実データに無い | その図のみ「データなし」を表示し、他の図は描画する |
| ペア可能な点が 0 件 | その図のみ「データなし」 |

いずれの場合も画面全体・PDF 全体は失敗させない。

## 6. API

すべて `backend/app/routers/wat.py` に置く。

### `GET /api/wat/lots`

| パラメータ | 説明 |
| --- | --- |
| `product_id` | 必須 |
| `months` | `1` / `3` / `6`。既定 `3` |

レスポンス: `{ product_id, lots: [{ lot_id, last_measured, wafer_count }] }`（新しい順）

### `GET /api/wat/summary`

| パラメータ | 説明 |
| --- | --- |
| `product_id` | 必須 |
| `lot_id` | 必須 |

レスポンス:

```jsonc
{
  "product_id": "P12345-A",
  "display_name": "Product-A",
  "lot_id": "LOT-2607-0142",
  "measured_date": "2026-07-14",
  "wafer_count": 25,
  "items": [
    {
      "item_name": "VTH_N", "unit": "V",
      "spec_low": 0.38, "spec_high": 0.52,
      "n": 5625, "mean": 0.4021, "sigma": 0.0284,
      "min": 0.3106, "max": 0.5340,
      "cpk": 0.92, "cpk_state": "value",
      "oos_count": 12, "oos_pct": 0.213,
      "status": "red",
      "wafer_series": [ { "wafer_id": 1, "mean": 0.401, "sigma": 0.027, "n": 9 } ]
    }
  ],
  "scatter_pairs": [
    {
      "label": "Core RVT",
      "plots": [
        {
          "kind": "vth_np",
          "x_item": "VTHN_RVT", "y_item": "VTHP_RVT",
          "x_unit": "V", "y_unit": "V",
          "x_spec": [0.38, 0.52], "y_spec": [-0.54, -0.40],
          "points": [ { "wafer_id": 1, "site_no": 1, "x": 0.401, "y": -0.472 } ]
        }
      ]
    }
  ]
}
```

補足:

- `measured_date` はそのロットの `MAX(START_TIME)` の日付部分
- `wafer_series` はウェハ番号の昇順。あるウェハの有効測定値が 2 件未満なら `sigma` は `null` とし、チャート側はそのウェハの誤差棒を描かない
- `oos_count` / `oos_pct` は判定の根拠として返す。`oos_pct` はテーブル列にはしない（§7.3）

**ウェハ別系列と散布図の点をこのレスポンスに同梱する。** 別エンドポイントに分けると (a) ドリルダウンのたびに往復が発生し、(b) PDF 側でも同じ系列が必要になるため計算経路が 2 本に分岐する。同梱すれば経路が 1 本に保たれ、画面と PDF の数値一致が構造的に保証される。データ量は 60 項目 × 25 ウェハ + 24 図 × 225 点 ≒ 数百 KB で許容範囲。

### `POST /api/wat/export-pdf`

ボディ: `{ product_id, lot_id }`

レスポンス: `application/pdf`。ファイル名は `WAT_<product_id>_<lot_id>.pdf`。

## 7. 画面

### 7.1 タブ構成

Report ページ内にタブを追加する。

```
Reports · Yield Trend
Report
[ Yield Trend ] [ PCM / WAT ]

Product [P12345-A ▾]  Period [Last 3 months ▾]  Lot [LOT-2607-0142 ▾]  [Export PDF]
```

- 製品セレクトは両タブ共通
- Period / Lot セレクトは PCM/WAT タブでのみ表示
- Yield Trend タブは**現状のまま**（Process チップ、固定 3 ヶ月、既存の Export PDF）。既存ロジックは変更しない

### 7.2 レイアウト

上から順に:

1. **ロットヘッダ** — ロット ID / 測定日 / ウェハ枚数 / 項目数 / 赤・黄の件数
2. **サマリーテーブル**（上部）
3. **散布図セクション**（下部）

### 7.3 サマリーテーブル

列（12 列）: 判定記号 / 項目 / 単位 / 下限 / 上限 / N / 平均 / σ / Min / Max / Cpk / 規格外

- 「規格外」列は `oos_count`（件数）を出す。赤判定の根拠が表の上で確認できないと、判定記号だけでは深刻度が分からないため。`oos_pct` は列にせず、画面ではツールチップで補い、PDF では省略する
- 並びは **`ITEM_NAME` 昇順の固定順**。ロットが変わっても行位置が変わらず、ロット間の見比べと PDF の見た目が安定する
- 数値は**有効数字 4 桁**で整形する（Python の `%.4g` 相当）。桁数の大きく異なる項目が同じ列幅で読めるようにするため。`n` と `oos_count` は整数表示、`cpk` は小数 2 桁固定
- 行クリックでその項目のウェハ別トレンドチャートを**直下にインライン展開**

### 7.4 散布図セクション

- フレーバー切替チップ（`pairs` の `label`）を上部に置き、**選択中の 1 フレーバーの 4 図のみ**を大きく表示する
- 24 図を同時に並べると 1 図あたりが小さくなり、225 点の分布とウェハ色分けが読めなくなるため
- 既定は `pairs` の先頭

## 8. チャート仕様

| | ウェハ別トレンド | 散布図 |
| --- | --- | --- |
| 点 | ウェハ平均（25 点） | サイト単位（約 225 点） |
| 補助 | ±3σ の誤差棒 | ウェハ番号 = 単一色相の濃淡グラデーション + カラーバー |
| 規格 | 上下限を破線 + ラベル | 規格範囲を薄い矩形で重ねる |
| 凡例 | なし（単一系列。タイトルが系列名を兼ねる） | カラーバーのみ |

**配色の決定**

- ウェハ番号は順序を持つ量なので**単一色相の light → dark ランプ**を使う。25 個の離散凡例は破綻し、虹色配色は順序が誤読されるため使わない
- 判定の赤・黄は既存のステータス色（`--error` / `--warning`）を使い、系列色には転用しない
- 文字は ink 系トークンを使い、系列色を文字色に使わない

**マーク仕様**

- マーカーは 8px 以上、重なり対策に背景色の細いリングを付ける
- 二軸（左右で異なるスケール）は使わない
- 数値ラベルは全点には振らず、規格外の点のみ

既存の `frontend/src/theme.ts` の `plotlyBaseLayout()` を土台にし、既存チャートとトーンを揃える。

## 9. PDF（A4 縦）

構成:

1. ヘッダ（ロゴ / 製品 / ロット ID / 測定日）＋ 要約（`● 2 / ▲ 5`）
2. サマリーテーブル（全項目、複数ページ）
3. 散布図 24 図（2 × 2 で 6 ページ）
4. 赤・黄と判定された項目のウェハ別トレンドチャート

赤・黄項目のトレンドは、テーブルと同じ `ITEM_NAME` 昇順で並べる。

**向きは A4 縦**（既存の歩留り PDF は横）。本文幅は約 180mm となり、12 列を配置すると 1 列あたり約 15mm。フォント 7pt 前後で収める。項目名列だけは他より広く取り、長い `ITEM_NAME` は省略記号で切る。

ロゴ・フッタ・CONFIDENTIAL 表記・余白定数は既存の歩留り PDF と共通化する（§10 参照）。

**生成時間の扱い**

24 図 + トレンド数枚 ≒ 30 枚を kaleido で画像化するため、既存の歩留り PDF より明確に重い（1 枚 0.3〜1 秒として 10〜30 秒の見込み）。

方針: **全 24 図を収録する前提で実装し、実測してから必要に応じて手を打つ**。画面には生成中であることを表示する。実測値は実装時に記録する。

## 10. ファイル構成

### バックエンド（新規）

| ファイル | 責務 |
| --- | --- |
| `services/wat_queries.py` | SQL 組み立てと実行 → DataFrame（`map_queries.py` と同型） |
| `services/wat_service.py` | 統計集計・判定・散布図ペアリング・モック分岐 |
| `services/wat_pdf_service.py` | WAT の PDF 生成（A4 縦） |
| `services/pdf_common.py` | ロゴ / フッタ / 余白定数 / ブランディング定数の共有 |
| `routers/wat.py` | エンドポイント 3 本 |
| `tests/test_wat_service.py` | 統計・判定・ペアリングのテスト |
| `tests/test_wat_pdf.py` | PDF 生成のスモークテスト |

### バックエンド（変更）

| ファイル | 変更内容 |
| --- | --- |
| `services/pdf_service.py` | ブランディング定数と `_draw_logo` / `_draw_footer` を `pdf_common.py` へ移し、そこから import する。**描画結果は変えない** |
| `services/mock_data.py` | `mock_wat_dataframe()` を追加 |
| `services/product_config.py` | `wat:` ブロックの読み出しヘルパを追加 |
| `models/schemas.py` | WAT 関連のレスポンス型を追加 |
| `app/main.py` | `wat` ルータの登録 |
| `product_config.yaml.example` | `wat:` ブロックの記述例を追加 |

`pdf_service.py` は現状 384 行。ここに WAT の PDF 生成を足すと 700 行超になり、歩留りと WAT の責務が混ざる。別モジュールに分け、共通部分だけを `pdf_common.py` に切り出す。

### フロントエンド（新規）

| ファイル | 責務 |
| --- | --- |
| `components/wat/WatSummaryTab.tsx` | PCM/WAT タブ全体（ロット選択・取得・レイアウト） |
| `components/wat/WatSummaryTable.tsx` | 項目別テーブルと行展開 |
| `components/wat/WatItemTrendChart.tsx` | ウェハ別トレンド |
| `components/wat/WatScatterGrid.tsx` | フレーバー切替 + 散布図 4 図 |

### フロントエンド（変更）

| ファイル | 変更内容 |
| --- | --- |
| `pages/ReportPage.tsx` | タブ切替の追加のみ。既存の歩留り表示ロジックは触らない |
| `api/client.ts` | WAT の 3 関数を追加 |
| `types.ts` | WAT の型を追加 |

## 11. モックデータ

`USE_MOCK_DATA=true`（既定）で Oracle なしに動作すること。既存のモック方針に合わせ、決定論的に生成する。

- 6 フレーバー分の Vth_n / Vth_p / Idsat_n / Idsat_p ＋ その他の項目で計 40 項目程度
- 25 ウェハ × 9 サイト
- **規格外の測定値と低 Cpk の項目を意図的に混ぜる**。赤・黄の描画、判定記号、PDF のチャート抽出を実 DB なしで検証できるようにするため
- 同じ入力に対して常に同じ出力（シード固定）

`product_config.yaml` のモック用エントリにも `wat:` ブロックを用意し、散布図の経路をモードで検証できるようにする。

## 12. エラー処理

| 状況 | 挙動 |
| --- | --- |
| ロットに WAT データが無い | 「No WAT data for this lot」を表示。画面は落とさない |
| ロット一覧が空 | Lot セレクトを空にし、その旨を表示 |
| `wat:` 未設定 | 散布図セクションを非表示。テーブルは表示 |
| 設定項目が実データに無い | その図だけ「データなし」 |
| 規格値が混在 | 最頻値を採用し WARNING ログ |
| API 失敗 | 既存の `ErrorBanner` を使う |
| PDF 生成失敗 | 500 とエラーメッセージ。既存 `export.py` と同じ形 |

## 13. テスト

`backend/tests/` に pytest で置く。既存の 76 件に追加する。

**統計**

- Cpk: 両側規格 / 片側規格（上限のみ・下限のみ）/ 規格なし / σ = 0 かつ規格内（`infinite`）/ σ = 0 かつ規格外 / n < 2
- 判定の**境界値**: `cpk == 1.00` は黄（赤ではない）、`cpk == 1.33` は正常（黄ではない）
- 判定の**評価順**: `n < 2`（`cpk_state == "undefined"`）かつ規格外ありの項目が、グレーではなく**赤**になる
- `cpk_state == "infinite"` の項目が正常判定になる
- `MEAS_DATA` が NULL の行が N から除外される
- 規格値混在時に最頻値が採られ、WARNING が出る

**散布図**

- 同一ウェハ × 同一サイトのみが組になる
- 片側欠損のサイトが除外される
- `wat:` 未設定の製品で `scatter_pairs` が空になる
- 設定項目が存在しない場合にその図だけ空になり、他は残る

**その他**

- ロット一覧が `START_TIME` の降順で返る
- モックが決定論的（同じ入力で同じ出力）
- PDF がバイト列を返し、ページ数が想定範囲に入る（スモーク）

フロントエンドは `npm run build` と `npm run lint` が通ることを最低条件とする。

## 14. 決定事項の要約

| 項目 | 決定 |
| --- | --- |
| データソース | `WAT_MEASURE_DETAIL`、`PRODUCT_ID` は既存 `product_id` と同値 |
| フィルタ | `DEL_FLAG` / `REWORK_NEW` は使わない（rework 運用なし） |
| 単位 | 1 ロットに閉じる（横断集計なし） |
| 統計母集団 | 生の測定値全件（ウェハ × サイト） |
| 判定 | 規格外あり or Cpk<1.00 → 赤、Cpk<1.33 → 黄。色 + 記号 |
| テーブル並び | `ITEM_NAME` 固定順 |
| 行展開チャート | そのロット内のウェハ別推移（平均 ± 3σ） |
| 散布図 | Vth n/p、Idsat n/p、Ion-Vt (N)、Ion-Vt (P) の 4 種 × 6 フレーバー |
| 散布図の点 | サイト単位（ウェハ × SITE_NO でペア）、ウェハ番号で単一色相の濃淡 |
| 画面の散布図 | フレーバー切替チップ + 4 図を大きく |
| PDF | A4 縦。テーブル全項目 + 散布図 24 図 + 赤黄項目のトレンド |
| 実装方式 | 既存三層パターン踏襲 + `pdf_common.py` 切り出し |
