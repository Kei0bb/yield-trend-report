# nginx Reverse Proxy Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the planned (not yet deployed) Caddy reverse proxy with nginx: config file, runbook update, Caddyfile removal.

**Architecture:** nginx listens on :80 (any hostname) and proxies everything to uvicorn on 127.0.0.1:8000. App code is untouched. Windows deployment via NSSM service, documented in the runbook.

**Tech Stack:** nginx (Windows build), NSSM, existing FastAPI/uvicorn backend.

## Global Constraints

- Do NOT modify any file under `backend/` or `frontend/`.
- `proxy_read_timeout 300s` is mandatory (first uncached dashboard query can take minutes).
- Spec: `docs/superpowers/specs/2026-07-07-nginx-reverse-proxy-design.md`.

---

### Task 1: nginx.conf

**Files:**
- Create: `deploy/nginx.conf`
- Delete: `deploy/Caddyfile`

**Interfaces:**
- Consumes: nothing.
- Produces: `deploy/nginx.conf` referenced by Task 2's runbook text.

- [ ] **Step 1: Write `deploy/nginx.conf`**

```nginx
# ─────────────────────────────────────────────────────────────────────────
# nginx.conf — Yield Portal reverse proxy (internal LAN, Windows)
#
# Role: take browser requests on port 80 (any hostname: the FQDN
#       yieldportal.socionext.com, the Windows computer name, or the IP)
#       and forward them to the FastAPI app listening on 127.0.0.1:8000.
#
# The app (uvicorn) is bound to 127.0.0.1 so it is NOT reachable from the
# network directly — only nginx is. See docs/deploy-windows.md for setup.
#
# Place at C:\nginx\conf\nginx.conf and validate with:  nginx -t
# ─────────────────────────────────────────────────────────────────────────

worker_processes  1;          # Windows build: 1 worker is the supported mode

events {
    worker_connections  1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;

    access_log  logs/access.log;
    error_log   logs/error.log;

    sendfile      on;
    server_tokens off;

    # Compress API JSON and frontend assets.
    gzip              on;
    gzip_types        application/json application/javascript text/css text/html image/svg+xml;
    gzip_min_length   1024;

    server {
        listen       80;
        server_name  _;      # accept any hostname (FQDN / machine name / IP)

        location / {
            proxy_pass         http://127.0.0.1:8000;
            proxy_set_header   Host              $host;
            proxy_set_header   X-Real-IP         $remote_addr;
            proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_set_header   X-Forwarded-Proto $scheme;

            # First uncached dashboard/report query can take minutes (Oracle).
            proxy_read_timeout 300s;
            proxy_send_timeout 300s;
        }
    }

    # ═════════════════════════════════════════════════════════════════════
    # LATER — HTTPS (https://yieldportal.socionext.com)
    # Ask IT for a cert + key issued by the corporate CA, save them under
    # C:\nginx\certs\, then replace the server block above with:
    # ═════════════════════════════════════════════════════════════════════
    # server {
    #     listen       443 ssl;
    #     server_name  yieldportal.socionext.com;
    #     ssl_certificate      C:/nginx/certs/yieldportal.crt;
    #     ssl_certificate_key  C:/nginx/certs/yieldportal.key;
    #
    #     location / {
    #         proxy_pass         http://127.0.0.1:8000;
    #         proxy_set_header   Host              $host;
    #         proxy_set_header   X-Real-IP         $remote_addr;
    #         proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
    #         proxy_set_header   X-Forwarded-Proto $scheme;
    #         proxy_read_timeout 300s;
    #         proxy_send_timeout 300s;
    #     }
    # }
    # # And redirect HTTP → HTTPS:
    # server {
    #     listen      80;
    #     server_name yieldportal.socionext.com;
    #     return 301 https://$host$request_uri;
    # }

    # ── LATER — simple access control (Basic auth) ──
    # Create the password file (htpasswd format, e.g. via WSL or online tool)
    # at C:\nginx\conf\htpasswd, then add inside `location /`:
    #     auth_basic           "Yield Portal";
    #     auth_basic_user_file htpasswd;
}
```

- [ ] **Step 2: Delete the Caddyfile**

```bash
git rm deploy/Caddyfile
```

- [ ] **Step 3: Validate syntax if nginx is available locally**

Run: `which nginx && nginx -t -c /mnt/disk/projects/Report_gen/deploy/nginx.conf -p /tmp || echo "nginx not installed — config review only"`
Expected: either `syntax is ok` or the fallback message. (The `logs/` relative
paths make `-t` require `-p`; if it errors only on log paths, that is
acceptable — they resolve under C:\nginx in production.)

- [ ] **Step 4: Commit**

```bash
git add -A deploy/
git commit -m "feat(deploy): replace Caddy with nginx reverse-proxy config"
```

---

### Task 2: Runbook update

**Files:**
- Modify: `docs/deploy-windows.md` (every Caddy mention)

**Interfaces:**
- Consumes: `deploy/nginx.conf` from Task 1.
- Produces: updated runbook; no code consumers.

- [ ] **Step 1: Read `docs/deploy-windows.md` fully**

Identify every Caddy reference: architecture diagram, install steps, NSSM
service registration, log paths, HTTPS notes.

- [ ] **Step 2: Rewrite the proxy sections for nginx**

Replace the Caddy install/run/service content with:

````markdown
## リバースプロキシ (nginx)

1. nginx Windows 版を https://nginx.org/en/download.html から取得し、
   `C:\nginx` に展開する。
2. このリポジトリの `deploy/nginx.conf` を `C:\nginx\conf\nginx.conf` に上書き配置。
3. 構文確認:

   ```bat
   cd C:\nginx
   nginx -t
   ```

4. NSSM でサービス登録（管理者コマンドプロンプト）:

   ```bat
   nssm install YieldProxy C:\nginx\nginx.exe
   nssm set YieldProxy AppDirectory C:\nginx
   nssm set YieldProxy AppStopMethodConsole 3000
   nssm start YieldProxy
   ```

   > nginx は `nginx -s stop` での停止が正式だが、NSSM 経由のプロセス停止でも
   > 実用上問題ない。手動で止める場合は `cd C:\nginx && nginx -s stop`。

5. 動作確認: 別 PC のブラウザで `http://<マシン名>/` を開き Dashboard が
   表示されること。`curl http://localhost/api/health` が `{"status":"ok"...}`
   を返すこと。

### ログローテーション

nginx は Windows で自動ローテーションしない。ログが肥大したら:

```bat
cd C:\nginx
move logs\access.log logs\access.old.log
nginx -s reopen
```

（必要ならタスクスケジューラで月次実行に登録する。）
````

Also update the architecture diagram/table: `Caddy` → `nginx`, service name
`YieldCaddy` → `YieldProxy` (or whatever name the doc used), log path
`C:\caddy\logs` → `C:\nginx\logs`. Keep uvicorn sections unchanged.

- [ ] **Step 3: Verify no Caddy references remain**

Run: `grep -ri caddy docs/ deploy/ && echo "LEFTOVERS FOUND" || echo clean`
Expected: `clean` (docs/roadmap.md mentions may remain — update roadmap
lines A-1/A-2 wording from Caddy to nginx too, then re-run).

- [ ] **Step 4: Commit**

```bash
git add docs/deploy-windows.md docs/roadmap.md
git commit -m "docs(deploy): runbook and roadmap switched from Caddy to nginx"
```
