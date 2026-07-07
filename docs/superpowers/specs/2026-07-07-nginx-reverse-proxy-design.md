# nginx リバースプロキシ移行 — 設計

**日付**: 2026-07-07
**ステータス**: 承認待ち
**関連**: `deploy/Caddyfile`（置換対象）, `docs/deploy-windows.md`, roadmap A-1/A-2

## 背景と目的

本番（共有Windowsマシン）は Caddy → uvicorn(127.0.0.1:8000) 構成を計画していたが未稼働。
運用者が nginx に馴れており情報も多いため、稼働前に nginx へ切り替える。
内部LAN・平文HTTP・単一upstreamの本用途では機能差は実質ゼロで、運用者の知見を優先する。

## 成果物

### 1. `deploy/nginx.conf`（新規）
- `listen 80;` `server_name _;`（FQDN / マシン名 / IP いずれでも受ける）
- `location / { proxy_pass http://127.0.0.1:8000; }`
- proxyヘッダ: `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`
- `proxy_read_timeout 300s` — キャッシュ未ヒット時のDashboard初回クエリが分単位になり得るため必須
- gzip有効（json/js/css/html）
- アクセスログ・エラーログを `C:\nginx\logs\` へ（nginx標準のログ出力。ローテーションはWindowsでは自動でないため運用手順に明記）
- 将来のHTTPS用 server block（社内CA証明書パス指定）をコメントで同梱
- 将来のBasic認証もコメントで同梱（roadmap A-2 対応の入口）

### 2. `docs/deploy-windows.md`（更新）
- Caddy節を nginx 節に置換:
  - nginx Windows版の取得・配置（`C:\nginx`）
  - `nginx.conf` の配置と `nginx -t` での構文確認
  - NSSMサービス登録（`nssm install YieldProxy ...`）。nginxはWindowsでは
    フォアグラウンド実行が前提でないため、起動/停止は `nginx.exe` /
    `nginx -s stop` をNSSMのApplication/Stop設定に割り当てる
  - ログローテーション: `nginx -s reopen` を使った手動/タスクスケジューラ手順
- アーキテクチャ図・ポート表の Caddy 表記を nginx に変更

### 3. `deploy/Caddyfile`（削除）
- git履歴に残るため復元可能。二重管理を避ける。

## 変更しないもの
- アプリ本体（backend/frontend）のコードは一切変更しない
- uvicorn の bind（127.0.0.1:8000、単一ワーカー）は現状維持

## 検証
- サンドボックスに nginx があれば `nginx -t -c <abs path>` で構文検証
- 無ければ設定レビューのみ（本番Windows到達不可のため実機検証はユーザー側作業）
- 本番切替時のスモークテスト手順を deploy-windows.md に記載
  （`curl http://localhost/api/health` 相当）

## リスクと対応
- **Windows版nginxの制約**（worker 1推奨・select()ベース）: 閲覧者数人〜十数人の
  社内ツールでは影響なし。runbookに注記のみ。
- **ログ肥大**: ローテーション手順を runbook に明記（放置で数年は無害なサイズ想定）。
