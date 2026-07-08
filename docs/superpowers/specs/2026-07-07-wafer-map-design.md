# Wafer Map タブ — 設計

**日付**: 2026-07-07
**ステータス**: 承認待ち
**関連**: `SEMI_CP_BIN_DETAIL`（新規利用テーブル）, Explore（遷移元）, `lot_service._load_dataframe`（lot一覧の再利用）

## 目的

複数lotのwaferマップを俯瞰し、位置依存の不良（エッジ・リング・クラスタ）を発見する。
bin選択でそのbinの発生分布だけを追える。ExploreのロットからワンクリックでMapへ飛べる。

## 要件（確定済み）

1. 新タブ **Wafer Map**（nav: Dashboard / Report / Explore / Wafer Map）
2. 製品・process・期間 → **lot複数選択** → wafer毎の**小マップをlotグループで並べる**（俯瞰）
3. **bin凡例チップをクリック → 全小マップがそのbinのみ着色**（他die淡灰）。再クリックで解除
4. Explore の LotTable の Lot ID クリック → 該当lotが選択済みの Wafer Map へ遷移
5. 規模感: 約200 die/wafer。10lot選択時 最大250マップ・5万die程度

## データ源

**`SEMI_CP_BIN_DETAIL`** — die単位の結果テーブル。
カラムは `SEMI_CP_BIN_SUM` と同様（**BIN_QUALITY/BIN_NAME/BIN_COUNTは無い**）＋ **X, Y**（die座標）。
bin情報は **`BIN_CODE`のみ**。

- 1行 = 1 die（pass die も bin_code の行として存在する前提。pass/fail 判定は
  DETAIL単体では行えないため、別途 `SEMI_CP_BIN_SUM` を参照する）
- die クエリは **headerとjoinしない単テーブル**:

```sql
SELECT SUBSTRATE_ID, WAFER_ID, X, Y, BIN_CODE
FROM SEMI_CP_BIN_DETAIL
WHERE SUBSTRATE_ID IN (:lot_ids...)
  AND PROCESS IN (:process_values...)
  AND REWORK_NEW = 0
```

- 製品・期間の絞り込みは lot 選択段階（既存ロットDFキャッシュ）で完了しているため不要
- `REWORK_NEW = 0` は単テーブルなので片側のみで正しい（CLAUDE.mdの両側ルールはjoin時の話）

### bin メタデータ（pass/fail・表示名）の解決

DETAILにBIN_QUALITY/BIN_NAMEが無いため、選択lot群に対して **`SEMI_CP_BIN_SUM`** から
DISTINCTで bin メタデータを別クエリで取得する（lot単位キャッシュ、dieクエリと同じ
`_die_cache` を共用）:

```sql
SELECT DISTINCT BIN_CODE, BIN_NAME, BIN_QUALITY
FROM SEMI_CP_BIN_SUM
WHERE SUBSTRATE_ID IN (:lot_ids...)
  AND PROCESS IN (:process_values...)
  AND REWORK_NEW = 0
```

- pass/fail 判定: `UPPER(TRIM(COALESCE(BIN_QUALITY,''))) = 'PASS'` → pass（既存 lot_queries と同じ正規化）。
  die側の fail 判定は `bin_code` が pass 判定された code 集合に含まれるか否かで行う
  （`~df["bin_code"].isin(pass_codes)`）
- bin 表示名の優先順:
  1. **`bin_mappings/<bin_group>.csv`**（Reportと同じCSV）で bin_code → グループ名
  2. `SEMI_CP_BIN_SUM` メタルックアップの `bin_name`（DB由来の生名称）
  3. どちらにも無ければコード番号のみ表示

表示形式は Explore と同様 `"<code>_<name>"`。

## バックエンド

### 新規 `app/services/map_queries.py`
- `build_die_map_query(lot_ids, process_values) -> (sql, binds)` — 上記SQL生成
- `query_die_map(lot_ids, process_values) -> DataFrame[lot_id, wafer_id, x, y, bin_code]`
- `build_bin_meta_query(lot_ids, process_values) -> (sql, binds)` — BIN_SUM向けメタSQL生成
- `query_bin_meta(lot_ids, process_values) -> DataFrame[bin_code, bin_name, bin_quality]`
- 単体テストは build のSQL文字列検証 + fetchallモックの列整合検証（lot_queries と同型）、
  die/meta 両方に対して用意する

### 新規 `app/services/map_service.py`
- `build_wafer_maps(nickname, process, lot_ids, process_values) -> WaferMapResponse`
- wafer毎に `{lot_id, wafer_id, x: int[], y: int[], bin: int[]}` のコンパクト並列配列
  （bin は凡例indexではなく生bin_code。pass die は bin_code をそのまま持ち、
  凡例側で pass 扱いを示す）
- 凡例: 選択lot群に出現する fail bin の一覧 `{bin_code, label, count}`（count降順）
  + pass bin 情報
- **キャッシュ**: `TTLCache`（3h・maxsize 128）を **lot単位キー**
  `mapdf:{nickname}:{process}:{lot_id}:{process_values}` で保持。
  複数lot要求はキー毎に取得し結合（部分ヒットが効く）。die結果は不変なので安全
- **モックモード**: 決定論的パターン生成（lot_id/waferシードでエッジリング・
  クラスタ・ランダムの混合、直径約16dieの円形配置 ≈200die）。
  bin_mappings CSV の適用経路もモックで通す（既存方針と同じ）

### 新規 `app/routers/wafer_map.py`
- `GET /api/wafermap/lots?product_id&process&months=6` →
  `{lots: [{lot_id, lot_date, wafer_count, test_program_rev}]}`
  既存 `_load_dataframe`（キャッシュ済み）から distinct lot を返すだけ。追加DB負荷なし
- `POST /api/wafermap` `{product_id, process, lot_ids: string[]}` → `WaferMapResponse`
- product_id → nickname の逆引きは既存ルータと同じ `nickname_for_product_id`
- `lot_ids` は上限 **12 lot**（バリデーション）。超過は 422

### スキーマ（`app/models/schemas.py` 追記）
- `WaferMapDie`は作らない（並列配列のため）。`WaferMapWafer`, `WaferMapLegendItem`,
  `WaferMapResponse` を追加

## フロントエンド

### 新規ページ `src/pages/WaferMapPage.tsx`（route `/wafermap`）
- 上部コントロール: 製品select・processセグメント・期間select（既存Exploreの部品流用）
  → lot一覧をチェックリスト表示（lot_id + 日付 + 枚数）→「表示」ボタンでPOST
- URLクエリ `?product_id=&process=&lots=a,b` を初期値として解釈し、
  揃っていれば自動ロード（Explore遷移用）

### 新規 `src/components/wafermap/WaferMapGrid.tsx`
- lot毎の見出し + その配下に wafer 小マップを flex-wrap で並べる

### 新規 `src/components/wafermap/WaferMapCanvas.tsx`
- **1 wafer = 1 canvas**（約120×120px、devicePixelRatio対応）
- 200 die を fillRect 描画。pass=淡灰、fail=binごとのカテゴリ色
  （色は凡例indexベースのパレット。dataviz skill のパレットに従う）
- **binフィルタ選択時**: 選択bin die のみ着色、他は淡色
- hover: マウス座標→die逆引きで `(x, y) bin_label` のツールチップ
- SVGでなくCanvasの理由: 最大5万dieでDOMノード化すると重い。
  canvasなら1マップ200 fillRectで軽量

### 凡例 `src/components/wafermap/BinLegend.tsx`
- fail bin チップ（色 + label + count）。クリックでフィルタトグル（単一選択）

### Explore からの遷移
- `LotTable.tsx` の Lot ID セルをリンク化 →
  `/wafermap?product_id=..&process=..&lots=<lot_id>`
  （sub選択中は process にその値を引き継ぐ）

### API クライアント
- `src/api/client.ts` に `fetchWaferMapLots`, `fetchWaferMaps` を追加
- `src/types.ts` に対応する型を追加

## やらないこと（YAGNI）
- 積算ヒートマップ（bin頻度の重ね合わせ1枚絵）— 今回は不採用と確認済み
- PDF出力への組み込み
- 座標の反転・回転設定（まず素直に(X,Y)描画。実データで向きが逆なら後続対応）
- wafer単位の拡大モーダル

## 検証
- backend: pytest（クエリbuild・列整合・serviceの凡例/配列構造・lot上限422・
  モック生成の決定論性）
- frontend: `npm run build` + `npm run lint`
- 実表示: mockモードで headless Chrome スクリーンショット確認（本セッション確立済みの手順）
- 実DB: `SEMI_CP_BIN_DETAIL` は本番でのみ検証可能 → ユーザー側で確認
  （`/api/debug/probe` 相当のdebugエンドポイントは今回追加しない。
  問題があれば `POST /api/wafermap` のWARNINGログで追う）
  → 実DB検証の結果、テーブル名が `SEMI_CP_BIN_DETAL`（誤り）ではなく
  `SEMI_CP_BIN_DETAIL`（正）であること、および BIN_QUALITY/BIN_NAME/BIN_COUNT
  カラムが存在しないことが判明し、上記の通り設計を修正済み

## リスク
- ~~**BIN_DETALの実カラム名が想定と違う**（X/Y以外の細部）: map_queries.py に
  カラム名定数を集約し、差異はこの1ファイル修正で吸収~~ → 実DB検証で顕在化・対応済み
  （テーブル名修正 + bin メタデータをSEMI_CP_BIN_SUM参照に変更）
- **pass die が行として存在しない**運用だった場合: マップがfail dieのみの疎表示に
  なる。その場合は wafer外形（円）を背景描画しているため見た目は破綻しない。
  完全対応（gross座標の補完）は実データ確認後の後続対応
