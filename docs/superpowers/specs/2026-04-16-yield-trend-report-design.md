# Yield Trend Report Generator — Design Spec

## Context

半導体プロダクトエンジニアが毎月、顧客提供用のyield trendレポートを作成する必要がある。現状は手動作成で工数がかかるため、Webベースのツールでデータ取得→チャート確認→PDF出力を一元化し、レポート作成の効率化を図る。

## Requirements

- CP / FT / SLT 各工程のLot毎の平均Yield折れ線 + 不良Bin stacked barの複合チャート
- フィルター: 製品名、期間（月指定）、工程選択（CP/FT/SLT）
- Web上でインタラクティブにチャートを確認
- PDFとしてダウンロード（顧客提供用）
- 社内サーバーで複数エンジニアが利用

## Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌───────────┐
│  React            │────▶│  FastAPI           │────▶│ Oracle DB │
│  (react-plotly.js)│◀────│  (Python)          │◀────│           │
│  Port 3000        │     │  Port 8000         │     │           │
└──────────────────┘     └──────────────────┘     └───────────┘
                               │
                               ▼
                         ┌──────────────┐
                         │ PDF Generator │
                         │ (plotly +     │
                         │  kaleido)     │
                         └──────────────┘
```

| Layer | Technology | Role |
|-------|-----------|------|
| Frontend | React + TypeScript + react-plotly.js | UI、インタラクティブチャート |
| Backend | FastAPI + cx_Oracle + pandas | DB接続、データ集計、API |
| PDF | plotly + kaleido + ReportLab | チャート画像生成→PDF組み立て |

Plotlyをフロントエンド・バックエンド共通で使用し、Web表示とPDF出力の見た目を統一する。

## Data Source

- Oracle DB、Wafer単位のテストデータ
- 1行 = 1ウェハーのテスト結果（yield、bin別不良数、gross die数）
- アプリ側でLot単位に集計（Wafer yield平均、bin別不良% = bin不良数 / gross die × 100）

## Directory Structure

```
Report_gen/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # DB接続設定等
│   │   ├── database.py          # Oracle DB接続管理
│   │   ├── routers/
│   │   │   ├── yield_data.py    # /api/yield-data endpoint
│   │   │   └── export.py        # /api/export-pdf endpoint
│   │   ├── services/
│   │   │   ├── yield_service.py # データ取得・集計ロジック
│   │   │   └── pdf_service.py   # Plotly→PDF生成
│   │   └── models/
│   │       └── schemas.py       # Pydantic schemas
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── Sidebar.tsx      # フィルターパネル
│   │   │   ├── YieldChart.tsx   # 複合チャート（1工程分）
│   │   │   └── ReportView.tsx   # CP/FT/SLT チャート一覧
│   │   ├── api/
│   │   │   └── client.ts        # API呼び出し
│   │   └── types/
│   │       └── index.ts         # 型定義
│   ├── package.json
│   └── tsconfig.json
└── README.md
```

## API Design

### GET `/api/products`

製品一覧を返却。

```json
["Product-A", "Product-B", "Product-C"]
```

### POST `/api/yield-data`

Request:
```json
{
  "product": "Product-A",
  "start_month": "2026-01",
  "end_month": "2026-03",
  "processes": ["CP", "FT", "SLT"]
}
```

Response:
```json
{
  "CP": {
    "lots": ["LOT001", "LOT002", "LOT003"],
    "yield_avg": [96.2, 94.8, 97.1],
    "fail_bins": {
      "Bin3": [1.2, 1.8, 0.95],
      "Bin5": [0.8, 0.6, 0.7],
      "Bin7": [0.4, 0.35, 0.2]
    }
  },
  "FT": { "..." : "..." },
  "SLT": { "..." : "..." }
}
```

- `yield_avg`: Lot内Waferの平均Yield (%)
- `fail_bins`: 各bin の不良% (= bin不良数 / gross die × 100)

### POST `/api/export-pdf`

同じリクエストBodyでPDFバイナリを返却。Content-Type: application/pdf。

## Page Layout

サイドバー + メインエリア構成:

- **左サイドバー（固定幅）**: 製品選択ドロップダウン、期間選択（開始月〜終了月）、工程チェックボックス（CP/FT/SLT）、Generate Reportボタン、Export PDFボタン
- **右メインエリア（可変幅）**: 選択した工程のチャートを縦に並べて表示（CP→FT→SLTの順）

## Chart Specification

各工程で同じ形式の複合チャート:

| Element | Spec |
|---------|------|
| X-axis | Lot ID（時系列順） |
| Left Y-axis | 不良Bin % (stacked bar) |
| Right Y-axis | 平均Yield % (line) |
| Stacked Bar | 各不良binを色分けして積み上げ。Gross dieベースの%表示 |
| Line | Lot内Wafer平均Yield。マーカー付き折れ線 |
| Hover | Lot ID、Yield値、各Bin%を表示 |
| Legend | チャート下部に表示 |

## PDF Output Specification

| Element | Spec |
|---------|------|
| Header | 製品名、期間、生成日 |
| Layout | 1ページに1工程。選択工程数分のページ |
| Chart style | Web画面と同じPlotlyスタイル |
| Paper | A4横向き |

## Verification

1. **バックエンド単体**: Oracle DBからデータ取得し、正しくLot集計されることを確認（pytestでモックDB使用）
2. **API動作**: FastAPIのSwagger UI (`/docs`) で各エンドポイントの動作確認
3. **フロントエンド**: ブラウザでフィルター操作→チャート表示を確認
4. **PDF出力**: Export PDFボタンでダウンロードし、チャートの見た目がWeb画面と一致することを確認
5. **E2E**: 製品選択→期間設定→工程選択→Generate→チャート確認→PDF出力の一連のフローを通して動作確認
