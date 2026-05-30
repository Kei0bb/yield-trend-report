# Yield Dashboard 設計書

- **日付**: 2026-05-28
- **対象**: 既存 Yield レポート Web ツールを、半導体エンジニアリング向け Yield Dashboard へ拡張する
- **ステータス**: 設計確定(実装前)

## 1. 背景と目的

現状のツールは「Sidebar で条件選択 → 製品×プロセス毎のチャートを並べる → PDF 出力」というレポート生成寄りの単一画面である。これを以下の用途へ拡張する:

- **日々の歩留り監視**(全製品を俯瞰)
- **異常検知**(歩留り低下・Fail Bin 急増の「要注意」抽出)
- **探索/ドリルダウン分析**(ロット個別の深掘り)

既存の月次 PDF レポート機能は別フローとして温存する。

## 2. 最重要の不変条件(壊さないもの)

1. `pdf_service.py` および `POST /api/export-pdf` のコードは **一切変更しない**
2. `POST /api/yield-data` の I/F は変更しない(Report タブが使用)
3. `yield_queries.py` / `yield_service.py` / `yield_aggregator.py` は変更しない(ロット個別粒度は新ファイルに分離)
4. `product_config.csv` / `bin_mappings/` の構造は維持(読み取り再利用のみ、列追加は可)
5. Report タブの挙動(チャート描画・PDF 出力)は移植後も完全に同一

## 3. 全体アーキテクチャ

### 3タブ構成(React Router で URL 切替)

```
TopNav: [Dashboard]  [Report]  [Explore]
```

| タブ | URL | 責務 | 既存資産 |
|------|-----|------|---------|
| Dashboard | `/` → `/dashboard` | 全製品×プロセスを表で俯瞰、行クリックで Explore へ | 新規 |
| Report | `/report` | 条件選択 → チャート群 → PDF 出力(**既存画面そのまま**) | App.tsx 現状ロジックを移植 |
| Explore | `/explore/:nickname/:process` | 単一製品の深掘り(ロット一覧 + Fail Bin 内訳) | 新規 |

### Dashboard 画面骨格

```
[期間: 過去6ヶ月 ▼] [プロセス: All / CP / FT ▼] [🔄 更新]   最終更新: 12:34
─────────────────────────────────────────────────────────────
製品/Proc | 直近歩留 | 6m平均 | 差分 | トレンド(spark) | ⚠ 要注意
PROD-A/FT |  87.5%   | 91.6% | ▼4.1 |  〰️             | Bin5急増(3.2x)
...
（要注意行は背景色でハイライト、行クリック → /explore/PROD-A/FT へ）
```

- レイアウトはテーブルビュー(密度重視)。KPI タイルと「要注意のみ表示」トグルは **不要**(行ハイライトで十分)。
- デフォルト表示期間 6ヶ月、手動更新のみ(自動リフレッシュなし)。

### Explore 画面骨格

```
< Dashboard に戻る             PROD-A / FT (過去6ヶ月)   [lot_id表示: 実番号/日付/年週 ▼]
─────────────────────────────────────────────────────────────
[ロット個別の歩留り推移チャート(要注意ロットはマーカー強調)]
─────────────────────────────────────────────────────────────
ロット一覧 (テーブル, ソート可)
Lot ID | 日付 | Wafer数 | 歩留 | Bin別内訳 ... | ⚠
```

ドリルダウン階層は「ロット一覧 + Fail Bin 内訳」まで(ウェーハマップ・Bin別時系列はスコープ外)。

## 4. バックエンド設計

### 4.1 新規エンドポイント

#### `GET /api/dashboard/summary`

- Query: `months=6`(既定6), `process=all|CP|FT`(既定 all)
- Response:

```json
{
  "generated_at": "2026-05-28T12:34:56+09:00",
  "period": { "months": 6, "start": "2025-12", "end": "2026-05" },
  "rows": [
    {
      "nickname": "PROD-A",
      "display_name": "Product A",
      "process": "FT",
      "latest_yield": 87.5,
      "latest_lot_id": "LOT-2026-0525-A",
      "latest_lot_date": "2026-05-25",
      "avg_yield_6m": 91.6,
      "delta": -4.1,
      "sparkline": [ { "lot_id": "...", "lot_date": "...", "yield": 92.1 } ],
      "warnings": [
        { "type": "yield_drop", "message": "前期比 -4.1% (閾値 -3.0%)", "severity": "warn" },
        { "type": "bin_surge",  "message": "Bin5 が過去平均の 3.2倍", "severity": "warn", "bin_code": 5 }
      ]
    }
  ]
}
```

#### `GET /api/explore/lots`

- Query: `nickname=<X>`, `process=CP|FT`, `months=6`
- Response:

```json
{
  "nickname": "PROD-A",
  "process": "FT",
  "period": { "months": 6, "start": "2025-12", "end": "2026-05" },
  "lots": [
    {
      "lot_id": "LOT-2026-0525-A",
      "lot_date": "2026-05-25",
      "wafer_count": 25,
      "yield": 87.5,
      "bin_breakdown": [
        { "bin_name": "Pass", "bin_codes": [1], "count": 540, "percent": 86.4 },
        { "bin_name": "Fail-Functional", "bin_codes": [5,6], "count": 60, "percent": 9.6 }
      ],
      "warnings": [ ... ]
    }
  ],
  "available_bins": ["Pass", "Fail-Functional", "Fail-Leak"]
}
```

#### `GET /api/anomaly/config`

- `anomaly_config.yaml` をパースして JSON で返す(UI 表示用)。

### 4.2 既存エンドポイント(変更なし)

| Method | Path | 用途 |
|--------|------|------|
| POST | `/api/yield-data` | Report タブ(既存) |
| POST | `/api/export-pdf` | PDF 生成(既存・不変) |
| GET | `/api/debug/config` | 既存デバッグ |
| GET | `/api/debug/probe` | 既存デバッグ |

### 4.3 ファイル構成(backend)

```
backend/app/
├── routers/
│   ├── yield_data.py        # 既存
│   ├── dashboard.py         # NEW: GET /api/dashboard/summary
│   ├── explore.py           # NEW: GET /api/explore/lots
│   └── anomaly_config.py    # NEW: GET /api/anomaly/config
├── services/
│   ├── yield_service.py     # 既存・不変
│   ├── yield_queries.py     # 既存・不変
│   ├── yield_aggregator.py  # 既存・不変
│   ├── pdf_service.py       # 既存・不変
│   ├── lot_queries.py       # NEW: ロット個別粒度の SQL
│   ├── lot_service.py       # NEW: ロット集計
│   ├── summary_service.py   # NEW: dashboard summary 構築
│   └── anomaly_service.py   # NEW: YAML 読込 + 判定
└── anomaly_config.yaml      # NEW: 異常判定設定
```

## 5. データ層(ロット個別粒度)

### 5.1 実ロット ID 列

現状の `yield_queries.py` は `TO_CHAR(MODIFIED_DATE, 'IYYY"W"IW')` で **週に丸めている**ため、同一週の複数ロットが合算される。Explore/Dashboard では実ロット列を使う:

| プロセス | 実ロット ID 列 | 集計単位 |
|---------|---------------|---------|
| CP | `SUBSTRATE_ID` | 基板(ロット)単位 |
| FT/SLT | `ASSY_LOT_ID` | 組立ロット単位 |

既存の `_PROCESS_SPEC`(テーブル名・JOIN キー・日付列・fail-bin フィルタ)は再利用し、`lot_id` の導出のみ実ロット列へ変更する。`lot_date` には `MIN(h.MODIFIED_DATE)` を持たせ、表示・ソートに使う。

### 5.2 集計フロー

```
lot_service.get_lots(nickname, process, months)
  → product_config から PRODUCT_ID 解決(既存ロジック流用)
  → lot_queries で実ロット粒度の wafer 行を取得
  → bin_mappings/<bin_group>.csv で bin_code → group 名マッピング(既存流用)
  → ロット単位に集計: yield=ロット内 wafer 平均, wafer_count, bin_breakdown(group別 count/percent)
  → date 昇順のロット配列を返す

summary_service.get_summary(months, process)
  → product_config 全エントリ × 対象プロセスをループ
  → 各々 lot_service で6ヶ月のロット列を取得
  → sparkline=各ロットの yield 時系列, latest=最新ロット, avg=期間平均, delta=latest-avg
  → anomaly_service.evaluate(lots) で warnings 算出
  → 1行に組み立て
```

### 5.3 Mock モード

`mock_data.py` を実ロット個別を返せるよう拡張(1週内に複数ロット生成)。mock でも Dashboard/Explore が動作確認できる状態を維持する。

### 5.4 パフォーマンス

`summary` は全製品ループの素朴実装からスタート。遅ければ「1クエリ全製品 GROUP BY」最適化を後追い(YAGNI)。

## 6. 異常検知

### 6.1 ルール(B + C のみ)

- **B: 前期比較** — 最新ロットの歩留りが期間内の過去平均より閾値以上低い
- **C: Fail Bin 急増** — 最新ロットのある Fail Bin 比率が過去平均の倍率以上

### 6.2 `anomaly_config.yaml`(backend ルート直下)

```yaml
defaults:
  yield_drop:
    threshold_pct: 3.0          # 過去平均 - 最新 >= 3.0% で警告
    min_lots: 3                 # 過去ロットが3未満なら判定しない
  bin_surge:
    multiplier: 2.0             # 最新Bin% >= 過去平均Bin% × 2.0 で警告
    min_percent: 1.0            # 過去平均が1.0%未満のノイズは無視

overrides:
  PROD-A:
    yield_drop:
      threshold_pct: 5.0
```

### 6.3 判定関数 `evaluate(lots, config) -> list[warning]`

- 入力 = ロット時系列(最新が末尾)。`latest`=末尾、`past`=それ以外。
- **yield_drop**: `len(past) >= min_lots` のとき `mean(past.yield) - latest.yield >= threshold_pct` → warning
- **bin_surge**: 各 bin group で `latest% >= past_avg% × multiplier` かつ `past_avg% >= min_percent` → warning(bin 名・倍率を message に)
- warning 構造: `{ type, message, severity: "warn", bin_code? }`
- 設定解決順: `overrides[product]` → `defaults`(ディープマージ)

## 7. フロントエンド設計

### 7.1 依存追加

- `react-router-dom`
- Plotly は既存流用

### 7.2 ディレクトリ構成

```
frontend/src/
├── App.tsx                      # → BrowserRouter + TopNav + Routes のみ
├── components/
│   ├── TopNav.tsx               # NEW
│   ├── Sidebar.tsx              # 既存(Report ページ内へ移動)
│   ├── ReportView.tsx           # 既存・不変
│   ├── YieldChart.tsx           # 既存・不変(Explore でも再利用)
│   ├── PlotlyChart.tsx          # 既存・不変
│   ├── ErrorBanner.tsx          # 既存・不変
│   ├── dashboard/
│   │   ├── SummaryTable.tsx     # NEW: ソート可・警告ハイライト・行クリック→Explore
│   │   └── Sparkline.tsx        # NEW: インラインSVG
│   └── explore/
│       ├── LotTrendChart.tsx    # NEW: ロット個別推移(警告ロット強調)
│       └── LotTable.tsx         # NEW: ロット一覧 + Fail Bin 内訳
├── pages/
│   ├── DashboardPage.tsx        # NEW
│   ├── ReportPage.tsx           # NEW(既存 Sidebar+ReportView ロジックを内包)
│   └── ExplorePage.tsx          # NEW
├── api/client.ts                # 既存 + 新API関数
├── utils/formatLotId.ts         # NEW
└── types/                       # 既存 + 新レスポンス型
```

### 7.3 ルーティング

| パス | ページ |
|------|--------|
| `/` | `/dashboard` へリダイレクト |
| `/dashboard` | DashboardPage |
| `/report` | ReportPage(既存機能) |
| `/explore/:nickname/:process` | ExplorePage |

### 7.4 App.tsx の変更

現状の `data`/`loading`/`error` state ロジックは **ReportPage.tsx にそのまま移植**。App.tsx は `<BrowserRouter>` + `<TopNav>` + `<Routes>` の薄い殻となる。Report 機能の挙動は一切変えない(PDF 出力含む)。

### 7.5 lot_id 表示フォーマット(localStorage)

API は生の `lot_id`(実ロット番号文字列)+ `lot_date`(ISO 日付)を返す。表示切替はフロントの `utils/formatLotId.ts` の `formatLotId(lotId, lotDate, mode)` で行う。mode は localStorage キー `dashboard.lotIdFormat`(`raw|date|yearweek`)。Explore のトグルで変更。

## 8. テスト戦略(TDD)

| 層 | テスト対象 | 方法 |
|----|-----------|------|
| `anomaly_service` | 閾値境界・min_lots/min_percent・override マージ | pytest(純粋関数、DB不要) |
| `lot_service` | wafer→lot 集計・bin breakdown | pytest + mock |
| `summary_service` | delta・sparkline・warning 統合 | pytest + mock |
| API ルーター | 3新エンドポイントのレスポンス形 | pytest + FastAPI TestClient(mock) |
| フロント | `formatLotId` | 軽量ユニット(任意) |

各 service はテストファースト(失敗するテスト → 実装 → green)で実装する。

## 9. スコープ外(YAGNI / 今回やらない)

- 自動リフレッシュ(手動更新のみ)
- ウェーハマップ / Bin コード別時系列
- 異常検知のシグマ判定・絶対閾値(B+C のみ)
- summary の単一クエリ最適化
- 認証・通知
