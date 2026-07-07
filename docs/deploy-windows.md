# Yield Portal — Windows デプロイ手順書

社内共有 Windows マシンで Yield Portal を起動し、チームが
**`http://yieldportal.socionext.com`**（IP も `:8000` も無し）でアクセスでき、
再起動後も自動で立ち上がる状態にするための手順です。

このガイドは **ネットワークの予備知識が無い方** を前提にしています。上から順に
進めてください。`<山カッコ>` で囲まれた部分は、お使いの環境の値に置き換えてください。

---

## 1. 全体像

```
  ブラウザ
    │   http://yieldportal.socionext.com   （ポート 80、今のところ平文 HTTP）
    ▼
  nginx            ← リバースプロキシ。Windows サービス "YieldProxy" として動作
    │   127.0.0.1:8000 へ転送
    ▼
  uvicorn（FastAPI アプリ）   ← Windows サービス "YieldBackend" として動作
    │                           127.0.0.1 のみにバインド（LAN には公開されない）
    ▼
  Oracle DB
```

バックグラウンドで動く 2 つのサービス:
- **YieldBackend** — アプリ本体（Python/uvicorn）。localhost のみで待ち受け。
- **YieldProxy** — ポート 80 の入口（nginx）。わかりやすい名前でのアクセスを実現する。

この構成にする理由: アプリ自体は外部に直接公開されず、nginx だけが唯一の公開
ポートになります。将来 HTTPS やログイン機能を追加するときも **nginx 側だけ**
変更すればよく、アプリ本体はそのままで済みます。

---

## 2. 事前に1回だけ必要な準備（IT 部門への依頼）

これらは「このマシン上で自分で設定する作業」ではなく、**社内 IT / ネットワーク
担当への依頼事項**です:

1. **DNS レコード:** `yieldportal.socionext.com` をこのマシンの LAN IP に向けて
   登録してもらう（いわゆる「A レコード」）。登録が完了するまでは、このマシンの
   コンピュータ名（手順 3）や IP アドレスでアクセスできます。
2. **ファイアウォール:** このマシンへの **TCP ポート 80** の受信を許可してもらう
   （コマンド自体は手順 8 に記載していますが、社内ポリシー上 IT 部門による
   実施が必要な場合があります）。

> HTTPS（鍵アイコン表示）は意図的に **後回し** にしています。詳細はセクション 12
> を参照してください。社内 LAN 限定・閲覧専用のツールであれば、まずは社内
> ネットワーク内での平文 HTTP でも問題なく、PC ごとの証明書設定の手間を
> 避けられます。

---

## 3. このマシンの名前と IP を確認する

**コマンドプロンプト** を開いて、以下を実行します。

```bat
hostname
ipconfig
```

- `hostname` はコンピュータ名を表示します（例: `YIELD-PC`）。LAN 内であれば
  既に `http://YIELD-PC:8000` でアプリにアクセスできるはずです — この名前を
  メモしておいてください。
- `ipconfig` は IPv4 アドレス（例: `10.20.30.40`）を表示します — DNS レコード
  登録のため、これを IT 部門に伝えてください。

---

## 4. 事前準備ソフトのインストール

このマシンに 1 回だけインストールします。

1. **uv**（Python ランナー）— 未インストールの場合:
   https://docs.astral.sh/uv/getting-started/installation/
2. **Node.js**（フロントエンドビルド用）: https://nodejs.org/ （LTS 版）
3. **nginx**（リバースプロキシ）: https://nginx.org/en/download.html から
   Windows 版 zip をダウンロードし、`C:\nginx` に展開します
   （実行ファイルは `C:\nginx\nginx.exe`）。
4. **NSSM**（プログラムを Windows サービス化するツール）:
   https://nssm.cc/download からダウンロードして展開し、`nssm.exe` のパスを
   メモしておきます（例: `C:\nssm\win64\nssm.exe`）。

nginx の zip には `logs\` フォルダが最初から含まれているため、フォルダ作成の
準備は不要です。

---

## 5. アプリをマシンに取得してビルドする

```bat
REM クローン（初回）または更新
cd C:\apps
git clone <YOUR_REPO_URL> Report_gen
cd Report_gen

REM フロントエンドをビルド（フロントエンドを変更するたびに再実行）
cd frontend
npm install
npm run build

REM バックエンドの依存関係をインストール
cd ..\backend
uv sync
```

`backend\.env` を作成し、実際の Oracle 接続情報を記載します（このファイルは
git 管理対象外です）。

```ini
USE_MOCK_DATA=false
ORACLE_DSN=<host>:1521/<service_name>
ORACLE_USER=<user>
ORACLE_PASSWORD=<password>
```

---

## 6. nginx を設定する

リポジトリの `deploy/nginx.conf` を、nginx が読み込む場所に上書き配置します。

```bat
copy C:\apps\Report_gen\deploy\nginx.conf C:\nginx\conf\nginx.conf
```

構文を確認します。

```bat
cd C:\nginx
nginx -t
```

このファイルは、**どのホスト名でアクセスされても** ポート 80 → `127.0.0.1:8000`
へ転送するようになっています。そのため FQDN（完全修飾ドメイン名）、コンピュータ
名、IP アドレスのいずれでもそのまま動作します。HTTP のままであれば編集は
不要です。サービスとしての起動は手順 9 で行います。

---

## 7. バックエンド起動スクリプトを調整・テストする

`C:\apps\Report_gen\deploy\windows\run-backend.bat` を編集し、`APP_DIR` を
実際のバックエンドパス（`C:\apps\Report_gen\backend`）に設定します。
手動でテスト実行します。

```bat
C:\apps\Report_gen\deploy\windows\run-backend.bat
```

そのあと `http://localhost:8000` をブラウザで開き、アプリが表示されることを
確認します。確認できたら `Ctrl+C` で停止します。（ポート無しの
`http://localhost` での確認は、手順 9 で nginx をサービス化した後に行います。）

---

## 8. ポート 80 のファイアウォールを開放する

**管理者権限** のコマンドプロンプトで実行します。

```bat
netsh advfirewall firewall add rule name="YieldPortal HTTP 80" dir=in action=allow protocol=TCP localport=80
```

（`127.0.0.1:8000` で待ち受けている uvicorn にはルールは不要です — ループ
バック通信はフィルタされません。）

---

## 9. 2 つの Windows サービスをインストールする（NSSM）

以下は **管理者権限** のコマンドプロンプトで実行します。`C:\nssm\...\nssm.exe`
の部分は実際の NSSM のパスに置き換え、`uv.exe` のパスは `where uv` で確認して
ください。

**バックエンドサービス:**

```bat
C:\nssm\win64\nssm.exe install YieldBackend "C:\apps\Report_gen\deploy\windows\run-backend.bat"
C:\nssm\win64\nssm.exe set YieldBackend AppDirectory "C:\apps\Report_gen\backend"
C:\nssm\win64\nssm.exe set YieldBackend Start SERVICE_AUTO_START
C:\nssm\win64\nssm.exe set YieldBackend AppStdout "C:\apps\Report_gen\backend\logs\service.log"
C:\nssm\win64\nssm.exe set YieldBackend AppStderr "C:\apps\Report_gen\backend\logs\service.log"
```

**nginx サービス:**

```bat
C:\nssm\win64\nssm.exe install YieldProxy "C:\nginx\nginx.exe"
C:\nssm\win64\nssm.exe set YieldProxy AppDirectory "C:\nginx"
C:\nssm\win64\nssm.exe set YieldProxy AppStopMethodConsole 3000
C:\nssm\win64\nssm.exe set YieldProxy Start SERVICE_AUTO_START
```

> nginx は `nginx -s stop` での停止が正式ですが、NSSM 経由のプロセス停止でも
> 実用上問題ありません（`AppStopMethodConsole` はその停止方法の待ち時間設定
> です）。手動で止める場合は `cd C:\nginx && nginx -s stop` を実行してください。

サービスを起動します。

```bat
net start YieldBackend
net start YieldProxy
```

（バックエンドのログフォルダが無ければ先に作成してください:
`mkdir C:\apps\Report_gen\backend\logs`）

---

## 10. 動作確認

共有マシン自身と、チームメンバーの PC の両方から確認します。

まず共有マシン自身のコマンドプロンプトで、nginx 経由の疎通を確認します。

```bat
curl http://localhost/health
```

`{"status":"ok",...}` が返れば、ブラウザ → nginx → uvicorn の経路が
つながっています。

続いてブラウザでも確認します。

- `http://localhost`（マシン自身から）→ アプリが表示される
- 別 PC のブラウザで `http://<コンピュータ名>/` を開く → Dashboard が
  表示される（例: `http://YIELD-PC/`）
- `http://yieldportal.socionext.com` → **IT 部門の DNS レコードが有効になった
  時点で** アプリが表示される

`http://yieldportal.socionext.com/health` が `{"status":"ok",...}` を返すことも
確認してください。

---

## 11. 日常運用

**更新を反映する（新しいコード）:**

```bat
cd C:\apps\Report_gen
git pull
cd frontend && npm install && npm run build
cd ..\backend && uv sync
net stop YieldBackend && net start YieldBackend
REM nginx.conf を変更した場合のみ nginx の再起動が必要です:
REM   copy deploy\nginx.conf C:\nginx\conf\nginx.conf  &&  net stop YieldProxy && net start YieldProxy
```

**再起動 / 停止:**

```bat
net stop YieldBackend & net start YieldBackend
net stop YieldProxy   & net start YieldProxy
```

**ログ:**
- アプリ: `C:\apps\Report_gen\backend\logs\service.log`
- nginx アクセスログ: `C:\nginx\logs\access.log`

**ログローテーション:** nginx は Windows で自動ローテーションしません。
ログが肥大したら以下を実行します（必要ならタスクスケジューラで月次実行に
登録してください）。

```bat
cd C:\nginx
move logs\access.log logs\access.old.log
nginx -s reopen
```

**キャッシュに関する注意:** アプリは Dashboard / Explore の集計結果を
メモリ上に 3 時間キャッシュします。`YieldBackend` を再起動するとこの
キャッシュはクリアされます（DB から再取得されます）。

---

## 12. 後回しにしている項目 — 必要になったら対応する

今は不要です（社内 LAN 限定・閲覧専用・少人数利用のため）が、規模が
大きくなったときに対応する順序は以下の通りです。

1. **HTTPS** — `deploy/nginx.conf` 内の HTTPS `server` ブロックのコメントを
   外し（社内発行の証明書を IT 部門から入手し `C:\nginx\certs\` に配置）、
   `C:\nginx\conf\nginx.conf` にコピーして `YieldProxy` を再起動します。
   ログイン機能を追加する前には必須です（パスワードが平文で送信されない
   ようにするため）。
2. **認証** — まずは nginx の `auth_basic`（共有パスワード 1 つ）から始め、
   ユーザーごとのアクセス制御や製品単位の権限が必要になったら社内 SSO
   （SAML/OIDC）に移行します。
3. **シークレット管理** — Oracle のパスワードを平文の `backend\.env` から
   Windows 資格情報マネージャーやシークレット管理サービスに移します。
4. **共有キャッシュ / マルチプロセス化** — uvicorn のワーカーを複数に
   スケールする場合は、メモリ内キャッシュを Redis に移行し全ワーカーで
   共有します。
5. **監視とバックアップ** — `/health` への死活監視、ログのローテーション・
   保存期間管理、復旧手順の文書化。

---

## 13. トラブルシューティング

| 症状 | 確認すること |
|---|---|
| `http://localhost:8000` は動くが `http://localhost` が動かない | nginx が起動していない、またはポート 80 が別のアプリ（IIS?）に使われている。`net start YieldProxy` を実行し、`C:\nginx\logs` を確認。 |
| チームメンバーが名前/IP でアクセスできない | ポート 80 のファイアウォールルール（手順 8）は設定済みか。DNS レコードは有効か。まず IP 直打ちで確認する。 |
| FQDN だけ失敗し IP / コンピュータ名は動く | `yieldportal.socionext.com` の DNS レコードがまだこのマシンを指していない — IT 部門に確認する。 |
| アプリにデータが出ない / DB エラーになる | `backend\.env` の Oracle 設定を確認し、`service.log` を確認。`USE_MOCK_DATA` は `false` になっている必要あり。 |
| サービスが起動しない | `.bat` を手動実行、または `cd C:\nginx && nginx -t` で設定の構文エラーを確認する。NSSM の設定内のパスを確認する（`nssm edit YieldBackend`）。 |
| ポート 80 が既に使われている | Windows の IIS や「World Wide Web Publishing Service」が使用している可能性 — 停止/無効化するか、nginx 側の `listen 80` を別ポートに変更する。 |
