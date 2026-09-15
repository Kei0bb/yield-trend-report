# Yield Trend Report Generator

半導体プロダクトエンジニア向けの Yield Trend レポート作成 Web ツール。  
Oracle DB から Wafer 単位データを取得し、Lot 毎に集計。CP / FT / SLT の複合チャート（Yield 折れ線 + 不良 Bin Stacked Bar）を Web 表示・PDF 出力します。

---

## スクリーンショット

### Web UI
![Web UI — フィルター & チャート](docs/screenshots/web_ui.png)

### 出力 PDF（1 ページ目）
![PDF サンプル](docs/screenshots/pdf_sample.png)

---

## 主な機能

| 機能 | 詳細 |
|------|------|
| 4 ページ構成 | Dashboard（製品×工程の集計表）/ Report（単一製品の Yield トレンド + PCM/WAT + PDF）/ Explore（Lot 単位ドリルダウン）/ Wafer Map（ロットのウェハ Bin マップ） |
| 製品 / 工程選択 | 上部ツールバーで `product_id` を選択（製品名は副表示）。Report の期間は今月末までの固定 3 ヶ月ウィンドウ。工程チップは製品ごとに `product_config.yaml` の設定に応じて動的表示（下記参照） |
| 製品ごとの出力工程設定 | `product_config.yaml` の `report:` で、製品別に大工程/小工程（CP, CP1, cFT1 など）の出力単位を任意の順序で定義可能。大工程なし（小工程のみ）の構成も可。`report:` の無い製品は Report に表示されない |
| 複合チャート | Lot 平均 Yield 折れ線（右 Y 軸）+ 不良 Bin Stacked Bar（左 Y 軸）。週単位で必ず最新 12 ISO 週分を表示 |
| Web プレビュー | Plotly でインタラクティブ表示（ズーム / ホバー / 凡例トグル） |
| PDF エクスポート | "Generate Report" でチャート表示後、"Export PDF" ボタンでサーバー生成（ReportLab + Plotly→kaleido）。A4 横向き、ロゴ / CONFIDENTIAL バッジ / ページ番号付き |
| Dashboard | 製品×工程の集計表。大工程＋小工程（major/sub）を親子行で表示し、CP→FT の順序を固定 |
| Explore | Lot 単位ドリルダウン。TP rev（テストプログラム改版、末尾 8 文字で識別）ごとに行を分割し、Bin は `BinNo_BinName` 表記で表示 |
| Wafer Map | 選択したロットのウェハ Bin マップをグリッド表示。ロット一覧・工程サブ選択は `/api/wafermap/lots` / `/api/wafermap/process-subs`、マップ本体は `POST /api/wafermap` から取得 |
| PCM/WAT（単ロット） | Report ページのタブ「PCM / WAT (Lot)」。1 ロットの WAT_MEASURE_DETAIL をサマリーテーブル（Isat/Vtl/Rc/Con/Others セクション、Cpk/OOS 判定）と散布図（Vth n/p・Idsat n/p・Ion-Vt、`product_config.yaml` の `wat: pairs:` で製品ごとに設定）で表示し、A4 縦 PDF を出力。"Generate" 実行時のみ集計 |
| PCM/WAT（トレンド） | Report ページのタブ「PCM / WAT (Trend)」。既定 3 ヶ月分の全ロットを対象に生サイト測定値をプールした通算統計 + ロット別系列を表示し、PDF を出力。詳細は [docs/pcm-wat-summary.md](docs/pcm-wat-summary.md) 参照 |
| 異常検知 | Yield 低下や Bin 急増を検知して警告バッジを表示（しきい値は `anomaly_config.yaml`） |
| キャッシュ | Dashboard / Explore の集計結果をインメモリで 3 時間 TTL キャッシュ（バックエンド再起動でクリア） |
| モックモード | Oracle 不要でモックデータで即起動 (`USE_MOCK_DATA=true`) |
| 接続状態表示 | 上部ツールバーに "Mock data" / "Live DB" をリアルタイム表示 |

---

## 技術スタック

### Frontend
- React 19 + TypeScript (Vite)
- react-router-dom（ページルーティング）
- react-plotly.js + plotly.js
- Claude 風デザイントークン（自己ホスト Web フォント / warm-white 基調。仕様: `docs/superpowers/specs/2026-07-19-design-refresh-claude-style-design.md`）

### Backend
- Python 3.13 + FastAPI + uvicorn
- oracledb（Oracle DB 公式 Python ドライバ、Thin モード — Instant Client 不要）
- pandas（Wafer → Lot 集計）
- pydantic-settings（型付き設定管理 + 起動時バリデーション）
- ReportLab + Plotly (kaleido) — サーバーサイド PDF 生成

---

## ディレクトリ構成

```
Report_gen/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI アプリ本体・CORS 設定・ルーター登録
│   │   ├── config.py             # pydantic-settings（環境変数 + .env 読み込み）
│   │   ├── database.py           # Oracle 接続プール管理
│   │   ├── logging_config.py     # LOG_LEVEL env で制御する統一ログ設定
│   │   ├── models/
│   │   │   └── schemas.py        # Pydantic スキーマ
│   │   ├── routers/
│   │   │   ├── yield_data.py     # GET /api/products, /api/report-products, /api/process-units, POST /api/yield-data, debug endpoints
│   │   │   ├── dashboard.py      # GET /api/dashboard/summary
│   │   │   ├── explore.py        # GET /api/explore/lots
│   │   │   ├── export.py         # POST /api/export-pdf
│   │   │   ├── anomaly_config.py # GET /api/anomaly/config
│   │   │   ├── wafer_map.py      # GET /api/wafermap/lots, /api/wafermap/process-subs, POST /api/wafermap
│   │   │   └── wat.py            # GET /api/wat/lots, /api/wat/summary, /api/wat/trend, POST /api/wat/export-pdf, /api/wat/export-trend-pdf
│   │   ├── services/
│   │   │   ├── yield_service.py    # Report 用オーケストレータ（薄いエントリポイント）
│   │   │   ├── yield_queries.py    # Report 向け Oracle SQL ビルダ + 実行（CP/FT は SEMI_CP_*、SLT は SEMI_FT_*）
│   │   │   ├── yield_aggregator.py # DataFrame → ProcessData 集計（最新 12 週パディング）
│   │   │   ├── lot_queries.py      # Explore 向け Lot 単位 Oracle SQL ビルダ + 実行（SLT は未対応・空返却）
│   │   │   ├── lot_service.py      # Explore 用オーケストレータ（TP rev 分割・Bin 集計）
│   │   │   ├── summary_service.py  # Dashboard 集計（製品×工程、major/sub 行構成）
│   │   │   ├── explore_service.py  # Explore レスポンス整形
│   │   │   ├── anomaly_service.py  # 異常検知（Yield 低下 / Bin 急増の判定）
│   │   │   ├── map_queries.py      # Wafer Map 向け Oracle SQL（ダイ単位 Bin 取得）
│   │   │   ├── map_service.py      # Wafer Map service（ロット単位キャッシュ + 凡例整形）
│   │   │   ├── wat_queries.py      # PCM/WAT 向け Oracle SQL（WAT_MEASURE_DETAIL 単一テーブル）
│   │   │   ├── wat_service.py      # PCM/WAT 単ロット service（項目統計・Cpk/OOS 判定・散布図ペアリング）
│   │   │   ├── wat_pdf_service.py  # PCM/WAT 単ロット PDF（A4 縦）
│   │   │   ├── wat_trend_service.py     # PCM/WAT トレンド service（期間プール統計 + lot_series）
│   │   │   ├── wat_trend_pdf_service.py # PCM/WAT トレンド PDF（A4 縦）
│   │   │   ├── product_config.py   # product_config.yaml 読み込み・nickname/report units 解決（lru_cache）
│   │   │   ├── bin_mapping.py      # bin_mappings/*.csv 読み込み・Bin コード変換（lru_cache）
│   │   │   ├── pdf_service.py      # ReportLab + Plotly→PNG で Yield PDF 生成
│   │   │   ├── pdf_common.py       # Yield/WAT 両 PDF 共通のブランディング・フッタ（COMPANY_NAME/LOGO_PATH/CONFIDENTIAL）
│   │   │   ├── wat_pdf_common.py   # PCM/WAT 2 種の PDF 共通部品（テーブル列定義・行描画・チャートグリッド）
│   │   │   ├── mock_data.py        # モックデータ生成
│   │   │   └── ttl_cache.py        # Dashboard/Explore 用インメモリ TTL キャッシュ
│   │   └── utils/
│   │       └── csv_loader.py     # CSV 読み込み共通ヘルパー・パス定数
│   ├── bin_mappings/             # 製品別 Bin マッピング CSV（書式は bin_mappings/README.md）
│   ├── product_config.yaml       # 製品設定（*.yaml.example を参照）
│   ├── anomaly_config.yaml       # 異常検知しきい値設定
│   ├── scripts/
│   │   └── slt_probe.py          # Report 経路を 1 段ずつ再現する診断 CLI（下記デバッグ参照）
│   ├── tests/                    # pytest（モックモード、Oracle 不要）
│   ├── pyproject.toml
│   └── .env                      # ← gitignore 済み（下記テンプレート参照）
├── assets/
│   └── logo.png                  # PDF + フロント左上で共有（未配置時はそれぞれ placeholder / "Y" マークへフォールバック）
├── deploy/
│   ├── nginx.conf                # 社内デプロイ用リバースプロキシ設定（下記デプロイ参照）
│   └── windows/
│       └── run-backend.bat       # Windows サービス化用起動スクリプト
├── frontend/
│   ├── public/
│   │   └── favicon.svg
│   └── src/
│       ├── App.tsx               # ルーティング（Dashboard/Report/Explore/Wafer Map）
│       ├── theme.ts              # BIN_COLORS / PRODUCT_COLORS / FONT_FAMILY（共通定数）
│       ├── index.css             # Claude 風デザイントークン（CSS 変数、自己ホストフォント）
│       ├── api/client.ts         # axios API クライアント
│       ├── pages/
│       │   ├── DashboardPage.tsx # Dashboard ページ
│       │   ├── ExplorePage.tsx   # Explore ページ
│       │   ├── ReportPage.tsx    # Report ページ（上部ツールバー制御、Yield/PCM-WAT タブ切替）
│       │   └── WaferMapPage.tsx  # Wafer Map ページ
│       ├── components/
│       │   ├── TopNav.tsx        # 上部ナビゲーション・フィルター
│       │   ├── ReportView.tsx    # レポートメイン表示
│       │   ├── YieldChart.tsx    # 複合チャートカード
│       │   ├── PlotlyChart.tsx   # react-plotly.js CJS 互換ラッパー
│       │   ├── ErrorBanner.tsx   # インラインエラー表示
│       │   ├── dashboard/
│       │   │   ├── SummaryTable.tsx # Dashboard 集計テーブル
│       │   │   └── Sparkline.tsx    # テーブル内の小型トレンド表示
│       │   ├── explore/
│       │   │   └── LotTable.tsx     # Explore の Lot 単位テーブル
│       │   ├── wafermap/
│       │   │   ├── WaferMapCanvas.tsx # ウェハ Bin マップの描画
│       │   │   ├── WaferMapGrid.tsx   # ロット内の複数ウェハをグリッド表示
│       │   │   └── copyGrid.ts        # グリッドを画像としてクリップボードへコピー
│       │   └── wat/
│       │       ├── WatSummaryTab.tsx    # PCM/WAT 単ロットタブ本体
│       │       ├── WatSummaryTable.tsx  # 項目サマリーテーブル（Isat/Vtl/Rc/Con/Others）
│       │       ├── WatScatterGrid.tsx   # Vth/Idsat 散布図グリッド
│       │       ├── WatTrendTab.tsx      # PCM/WAT トレンドタブ本体
│       │       └── WatItemTrendChart.tsx # 項目別ロット推移チャート
│       ├── ui/                   # 共通 UI 部品（Button / Select / Badge / PageTitle 等）
│       ├── utils/
│       │   └── tpRev.ts          # TP rev（テストプログラム改版）の末尾 8 文字抽出
│       └── types/index.ts        # TypeScript 型定義
└── docs/
    ├── deploy-windows.md         # Windows（nginx リバースプロキシ）デプロイ手順書
    ├── pcm-wat-summary.md        # PCM/WAT 機能の実装サマリー
    ├── roadmap.md                # 今後の開発ロードマップ
    ├── screenshots/              # README 掲載スクリーンショット
    └── superpowers/
        ├── specs/                # 設計仕様書
        └── plans/                # 実装計画書
```

---

## クイックスタート

### 前提条件
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Node.js 18+

> **Oracle Instant Client は不要です。**  
> `oracledb` は Thin モード（Pure Python）がデフォルトのため、クライアントライブラリのインストールなしで Oracle DB に接続できます。

### 推奨: 1 サーバー構成（FastAPI がフロントも配信）

```bash
# 1. フロントエンドを 1 回ビルド（フロント変更時のみ再ビルド）
cd frontend
npm install
npm run build

# 2. バックエンド起動（これだけで UI + API + /docs が立ち上がる）
cd ../backend
uv sync
uv run uvicorn app.main:app --port 8000
```

ブラウザで http://localhost:8000 を開きます。

- UI: http://localhost:8000
- API ドキュメント: http://localhost:8000/docs
- ヘルスチェック: http://localhost:8000/health

実 Oracle DB を使う場合:
```bash
USE_MOCK_DATA=false uv run uvicorn app.main:app --port 8000
```

### 開発者向け: 2 サーバー構成（フロント HMR を有効化）

フロントエンドのコードを編集しながら即座にブラウザへ反映させたい場合のみ使用します。
HMR (Hot Module Replacement) = ファイル保存と同時にブラウザの該当箇所だけ差し替えて再表示する Vite の機能。
ブラウザの再読み込み・状態リセット不要で、UI 開発を高速化するためのものです。

```bash
# Terminal 1
cd backend && uv run uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend && npm run dev    # → http://localhost:5173
```

`npm run dev` 側で開くと、Vite が `/api` を自動で `localhost:8000` にプロキシします。

---

## 環境変数

`backend/.env` を作成して設定します（`.env.example` を参照）：

```env
# モックデータ切り替え（true = Oracle 不要）
USE_MOCK_DATA=true

# Oracle DB 接続（USE_MOCK_DATA=false のときのみ使用）
ORACLE_DSN=hostname:1521/SERVICE_NAME
ORACLE_USER=your_user
ORACLE_PASSWORD=your_password
ORACLE_MIN_CONNECTIONS=2
ORACLE_MAX_CONNECTIONS=10

# ログレベル（DEBUG / INFO / WARNING / ERROR）
LOG_LEVEL=INFO

# CORS 許可オリジン（JSON 配列形式）
# 1 サーバー構成では同一オリジンのため不要。2 サーバー構成（npm run dev）で使う場合のみ設定
CORS_ORIGINS=["http://localhost:5173"]
```

> **注意**: `USE_MOCK_DATA=false` のとき `ORACLE_USER` / `ORACLE_PASSWORD` が未設定だと起動時にエラーになります。

`frontend/.env`（任意）:

```env
# バックエンドの API URL を上書きしたい場合のみ設定（通常は不要）
# デフォルトは "/api"（同一オリジン相対パス）
# VITE_API_BASE_URL=http://other-server:8000/api
```

---

## 製品設定 (product_config.yaml)

製品ごとの DB 解決・Bin マッピング・Report 出力単位は `backend/product_config.yaml` で設定します。詳細・記法は `product_config.yaml.example` を参照してください。

- **`processes:`** — 論理工程（`cp` / `ft` / `slt`）→ DB の `PROCESS` 列の値を対応付けます。`scalar`（単一値）/ `list`（先頭が major、残りが sub）/ `dict`（`{major, subs}` で明示指定、major 無しの subs-only も可）の 3 形式に対応。
- **`report:`** — Report 画面 / PDF が出力する工程単位を明示的に指定します。`{family, label, values}` のオブジェクトのリストで、画面のチップ・PDF のページが定義順に並びます。**製品が Report ページに表示されるにはこのキーが必須**です（`GET /api/report-products` は `report:` を持たない製品を除外します。`Dashboard`/`Explore` は `processes:` だけで表示可）。`product_config.yaml` 自体が無い場合（モック/レガシー）のみ CP/FT/SLT の従来動作にフォールバックします。
- **`bin_group`** — `bin_mappings/<bin_group>.csv` を参照し、Bin コード→グループ名の変換に使用します（工程ごとの上書きは `bin_groups`）。
- **`wat:`** — 任意設定。PCM/WAT の散布図（Vth n/p・Idsat n/p・Ion-Vt）に使う `WAT_MEASURE_DETAIL.ITEM_NAME` を `pairs:` で製品ごとに対応付けます。未設定でもサマリーテーブルは表示され、散布図セクションのみ非表示になります。

---

## API エンドポイント

| メソッド | パス | 説明 |
|----------|------|------|
| `GET` | `/health` | ヘルスチェック（`mock: true/false` 付き） |
| `GET` | `/api/products` | 製品一覧取得（`{product_id, display_name}` の配列） |
| `GET` | `/api/report-products` | Report ページで選択可能な製品一覧（`report:` を持つ製品のみ） |
| `POST` | `/api/yield-data` | Yield + Bin データ取得（`products` は `product_id`） |
| `GET` | `/api/process-units` | 製品ごとの選択可能な工程単位を取得（Report チップの動的表示用） |
| `POST` | `/api/export-pdf` | Yield PDF 生成（ReportLab + Plotly→kaleido） |
| `GET` | `/api/dashboard/summary` | ダッシュボード集計（製品×工程） |
| `GET` | `/api/explore/lots` | Lot 単位ドリルダウン（`product_id` + `process`） |
| `GET` | `/api/anomaly/config` | 異常検知のしきい値設定を取得 |
| `GET` | `/api/wafermap/lots` | Wafer Map 用のロット一覧（`product_id` + `process`、期間・サブ工程は任意） |
| `GET` | `/api/wafermap/process-subs` | 製品の major 工程ごとに選択可能なサブ工程 PROCESS 値を取得 |
| `POST` | `/api/wafermap` | 指定ロットのウェハ Bin マップを取得 |
| `GET` | `/api/wat/lots` | PCM/WAT 単ロット選択用のロット一覧（既定 3 ヶ月） |
| `GET` | `/api/wat/summary` | PCM/WAT 単ロットのサマリー（項目統計・Cpk/OOS 判定・散布図データ） |
| `GET` | `/api/wat/trend` | PCM/WAT トレンド（期間プール統計 + ロット別系列、既定 3 ヶ月） |
| `POST` | `/api/wat/export-pdf` | PCM/WAT 単ロット PDF 生成（A4 縦） |
| `POST` | `/api/wat/export-trend-pdf` | PCM/WAT トレンド PDF 生成（A4 縦） |
| `GET` | `/api/debug/config` | 設定ファイル読み込み状況の確認 |
| `GET` | `/api/debug/probe` | 実 DB クエリの診断（行数・エラー確認） |

コマンドラインの診断ツールとして `backend/scripts/slt_probe.py` もあります（[デバッグ](#デバッグ) 参照）。

### `POST /api/yield-data` リクエスト例

```json
{
  "products": ["P12345-A"],
  "start_month": "2026-01",
  "end_month": "2026-03",
  "processes": ["CP", "FT"]
}
```

> `products` には DB の `product_id` を渡します（バックエンドが内部で nickname に解決）。

---

## PDF エクスポート

サーバーサイドで生成します（ReportLab + Plotly→PNG via kaleido）。

1. "Generate Report" でチャートを表示
2. "Export PDF" ボタンをクリック → ブラウザに PDF がダウンロードされる

A4 横向き、Report の出力単位（`report:` の各 `label`。未設定時は工程）ごとに 1 ページ。ロゴはリポジトリ直下の `assets/logo.png` を参照（未配置時はプレースホルダ）。
CONFIDENTIAL バッジは各ページのフッター右下に表示されます。
社名・ロゴ・透かしの ON/OFF は `backend/app/services/pdf_common.py` の `COMPANY_NAME` / `LOGO_PATH` / `CONFIDENTIAL` で切り替えられます（Yield PDF・PCM/WAT PDF 共通）。

---

## Oracle DB テーブル仕様

工程によって参照するテーブルペアが異なります（`backend/app/services/yield_queries.py` の `_PROCESS_SPEC`）。

```sql
-- CP / FT
SEMI_CP_HEADER   -- ヘッダ（SUBSTRATE_ID / WAFER_ID / PRODUCT_ID / PROCESS / MODIFIED_DATE / EFFECTIVE_NUM / PASS_CHIP 等）
SEMI_CP_BIN_SUM  -- Bin 集計（BIN_CODE / BIN_NAME / BIN_COUNT）

-- SLT
SEMI_FT_HEADER   -- ヘッダ（ASSY_LOT_ID / PRODUCT_ID / PROCESS / MODIFIED_DATE / EFFECTIVE_NUM / PASS_CHIP 等）
SEMI_FT_BIN_SUM  -- Bin 集計（BIN_CODE / BIN_NAME / BIN_COUNT）
```

**CP と FT** は同一テーブル（`SEMI_CP_*`）・同一 `PRODUCT_ID` を共有し、`PROCESS` 列の値（例: `CP` / `cFT1`）で区別します。
JOIN キーは `SUBSTRATE_ID` + `WAFER_ID` + `PROCESS`（内部 `JOIN`）、Lot 識別列は `SUBSTRATE_ID`。

**SLT** はこのスキーマにデータが無いため `SEMI_FT_*` を読みます。JOIN キーは `ASSY_LOT_ID` + `PRODUCT_ID` + `PROCESS`、Lot 識別列は `ASSY_LOT_ID`（`AS substrate_id` として選択し、`yield_aggregator` が物理ユニット単位で重複排除できるようにしています）。
この JOIN は **`LEFT OUTER JOIN`** です。fail bin が 0 件のロットでも週バケットの Yield に反映させるためで、`b` 側（`SEMI_FT_BIN_SUM`）の条件はすべて `ON` 句に置いています（`WHERE` 句に置くと、未マッチ行の NULL が `= 0` を満たさず外部結合が事実上の内部結合に潰れ、fail bin 0 件のロットが消えてしまうため）。

**SLT は Report / PDF 専用です。** Dashboard / Explore（`lot_queries.py` の `_LOT_COLUMN`）は SLT 用の Lot 列定義を持たず、SLT に対して空データを返します（`SEMI_CP_*` 前提の SQL を `SEMI_FT_*` に当てると存在しない列で ORA-00904 になるため）。

論理工程（CP/FT/SLT）→ 実 PROCESS 値の対応は `product_config.yaml` の `processes:`（`cp` / `ft` / `slt`）で設定します。

データは Wafer 単位（bin_code ごとに複数行）。アプリ側で Lot 毎に集計します。  
Report の `lot_id` は `MODIFIED_DATE` から ISO 年週形式（`IYYY"W"IW`）で生成、Explore は実 `SUBSTRATE_ID` 単位で表示します。

Bin 不良率 = `Σ BIN_COUNT / Lot の総 Gross Die 数 × 100`。
分母は Lot に属する物理 Wafer の `EFFECTIVE_NUM`（Gross Die 数）を **Wafer ごとに 1 回だけ** 数えた合計です。
Report では `lot_id` が ISO 週ロールアップのため、`WAFER_ID` 単独では週内の別 Wafer（別 `SUBSTRATE_ID`）と衝突する点に注意し、`SUBSTRATE_ID` + `WAFER_ID` で重複排除してから合計します（単純に bin 行ごとに合計すると Wafer の Gross Die 数を bin の数だけ重複加算してしまい、分母が膨れて bin% が異常に低くなる）。

> **`REWORK_NEW = 0` は両テーブルペア（`SEMI_CP_HEADER`/`SEMI_CP_BIN_SUM` と `SEMI_FT_HEADER`/`SEMI_FT_BIN_SUM`）ともヘッダ・Bin 集計の両方に適用** し、最新リテスト結果のみを集計します。片側だけに適用すると、片方の最新行がもう片方の全リテスト行とマッチして fail bin が二重計上され、yield% + Σbin% が 100% を超える不整合が発生します。

### PCM/WAT テーブル（`WAT_MEASURE_DETAIL`）

Report ページの PCM/WAT タブが読む単一テーブル。粒度は 製品 × ロット × ウェハ × サイト × 測定項目で、規格値（`SPEC_LOW` / `SPEC_HIGH`）と単位（`ITEM_UNIT`）を自身が持ちます（`backend/app/services/wat_queries.py`）。`PRODUCT_ID` は `product_config.yaml` の `product_id` と同値です。

この工程は rework 運用が無いため、`SEMI_CP_*` 系で必須の `REWORK_NEW = 0` フィルタや `DEL_FLAG` フィルタは適用しません。

---

## デバッグ

### ログレベルの変更

```env
LOG_LEVEL=DEBUG  # DB クエリ・Bin マッピング読み込みの詳細が表示される
```

### 設定確認エンドポイント

```bash
# product_config.yaml と bin_mappings/ の読み込み状況
curl http://localhost:8000/api/debug/config?nickname=Product-A

# 実 DB クエリを叩いて行数を確認（空データの原因調査に有効）
curl "http://localhost:8000/api/debug/probe?nickname=Product-A&process=FT&start_month=2025-01&end_month=2025-05"
```

### Report が空になるときの切り分けスクリプト

`scripts/slt_probe.py` は Report と同じ経路（`report:` の `values:` を使う）を 1 段ずつ実行し、
どの段で行が消えたかを表示します。SLT 用に作りましたが、label を変えれば CP / FT でも使えます。

```bash
cd backend
USE_MOCK_DATA=false uv run python scripts/slt_probe.py <product_id> [label] [start] [end]

# 例
USE_MOCK_DATA=false uv run python scripts/slt_probe.py SCT101A SLT 2026-03 2026-08
```

出力は上から順に、最初に異常が出た段が原因です。

| 段 | 内容 | 異常時の原因 |
|----|------|--------------|
| 1-2 | product_id → nickname → report unit | label が `report:` に無い |
| 3 | PRODUCT_ID の解決 | `product_id:` の設定 |
| 4 | PROCESS 値の最終決定 | `report:` の `values:` が DB の実値と違う |
| 5 | SQL 実行 | 0 行なら SQL 層（段 6-8 で WHERE を自動で切り分け） |
| 6 | 12 週ウィンドウとの重なり | `なし` ならデータが期間外（SQL は正常） |
| 7-8 | bin グループ適用・集計 | bin マッピング不一致 |

段 5 で 0 行だった場合のみ、WHERE を 1 条件ずつ足した件数・実在する PROCESS / REWORK_NEW の値・
両テーブルの実際の列一覧まで自動で表示します。

> `/api/debug/probe` は PROCESS 値を `processes:` から解決するため Report とは経路が異なります。
> Report の挙動を再現したい場合はこのスクリプトを使ってください。

### CSV キャッシュのリセット

`product_config.yaml` や `bin_mappings/*.csv` を編集した場合は、バックエンドを再起動してください（`lru_cache` でプロセス起動時にのみ読み込まれます）。

---

## テスト

```bash
cd backend
uv run pytest        # モックモード、Oracle 不要

cd ../frontend
npm run lint          # ESLint
```

---

## 社内サーバーへのデプロイ

**Windows 共有マシンへのデプロイ**（リバースプロキシ nginx + Windows サービス化で `http://yieldportal.socionext.com` のように IP:ポート無しでアクセス）が現在の主なデプロイ方法です。手順は **[docs/deploy-windows.md](docs/deploy-windows.md)** を参照してください。

以下は汎用的な代替手段として、Linux 上で systemd を使う場合の手順です。

### Linux (systemd) の場合

1 サーバー構成のため、フロントを事前ビルドし FastAPI から配信します。
nginx / Apache などの静的配信サーバーは不要です。

#### 1. フロントエンドをビルド

```bash
cd frontend
npm install
npm run build   # → frontend/dist/
```

#### 2. バックエンドを systemd で常駐起動

```ini
[Unit]
Description=Yield Trend Report
After=network.target

[Service]
User=appuser
WorkingDirectory=/opt/yield-report/backend
Environment="USE_MOCK_DATA=false"
Environment="LOG_LEVEL=INFO"
EnvironmentFile=/opt/yield-report/backend/.env
ExecStart=/opt/yield-report/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

ブラウザから `http://your-internal-server:8000/` でアクセス可能。UI・API ともに同一サーバーから配信されるため CORS 設定は基本不要です。

---

## ライセンス

社内利用限定。無断配布・外部公開禁止。
