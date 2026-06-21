# Yield Portal — Windows Deployment Runbook

How to run the Yield Portal on a shared Windows machine so the team reaches it
at **`http://yieldportal.socionext.com`** (no IP, no `:8000`) and it stays up
across reboots.

This guide assumes **no prior web/networking experience**. Follow it top to
bottom. Anything in `<ANGLE BRACKETS>` is a value you fill in for your machine.

---

## 1. The picture

```
  Browser
    │   http://yieldportal.socionext.com   (port 80, plain HTTP for now)
    ▼
  Caddy            ← reverse proxy, runs as a Windows service "YieldCaddy"
    │   forwards to 127.0.0.1:8000
    ▼
  uvicorn (FastAPI app)   ← runs as a Windows service "YieldBackend"
    │                       bound to 127.0.0.1 only (not exposed to the LAN)
    ▼
  Oracle DB
```

Two background services:
- **YieldBackend** — the app itself (Python/uvicorn), only listens on localhost.
- **YieldCaddy** — the front door on port 80, gives the friendly name.

Why this shape: the app is never exposed directly; Caddy is the single public
port. When you later add HTTPS or a login, you change **only Caddy** — the app
stays the same.

---

## 2. One-time prerequisites (ask IT)

These are **not** things you configure on the machine — they are requests to
your IT/network team:

1. **DNS record:** point `yieldportal.socionext.com` to this machine's LAN IP
   (an "A record"). Until that exists, you can still reach the app by the
   machine's computer name (Step 3) or its IP.
2. **Firewall:** allow inbound **TCP port 80** to this machine (Step 8 shows the
   command, but corporate policy may require IT to do it).

> HTTPS (the padlock) is intentionally **deferred** — see Section 12. For a
> LAN-only, view-only tool, plain HTTP over the corporate network is acceptable
> as a first step, and avoids the per-PC certificate setup.

---

## 3. Find this machine's name and IP

Open **Command Prompt** and run:

```bat
hostname
ipconfig
```

- `hostname` prints the computer name, e.g. `YIELD-PC`. On the LAN you can
  already reach the app at `http://YIELD-PC:8000` today — write this name down.
- `ipconfig` shows the IPv4 address (e.g. `10.20.30.40`) — give this to IT for
  the DNS record.

---

## 4. Install the prerequisites

Install once on the machine:

1. **uv** (Python runner) — if not already installed:
   https://docs.astral.sh/uv/getting-started/installation/
2. **Node.js** (to build the frontend): https://nodejs.org/ (LTS)
3. **Caddy** (the reverse proxy): https://caddyserver.com/download — download
   `caddy.exe` and put it at `C:\caddy\caddy.exe`.
4. **NSSM** (runs programs as Windows services): https://nssm.cc/download —
   unzip and note the path to `nssm.exe` (e.g. `C:\nssm\win64\nssm.exe`).

Create folders Caddy will use:

```bat
mkdir C:\caddy\logs
```

---

## 5. Get the app onto the machine and build it

```bat
REM Clone (first time) or update
cd C:\apps
git clone <YOUR_REPO_URL> Report_gen
cd Report_gen

REM Build the frontend (re-run this after every frontend change)
cd frontend
npm install
npm run build

REM Backend dependencies
cd ..\backend
uv sync
```

Create `backend\.env` with the real Oracle settings (this file is NOT in git):

```ini
USE_MOCK_DATA=false
ORACLE_DSN=<host>:1521/<service_name>
ORACLE_USER=<user>
ORACLE_PASSWORD=<password>
```

---

## 6. Configure Caddy

Copy the repo's Caddyfile to where the service will read it:

```bat
copy C:\apps\Report_gen\deploy\Caddyfile C:\caddy\Caddyfile
```

The file already forwards port 80 → `127.0.0.1:8000` for **any** hostname, so it
works for the FQDN, the computer name, and the IP. No edits needed for HTTP.

Test it once by hand (leave it running, open another Command Prompt for the next
steps):

```bat
C:\caddy\caddy.exe run --config C:\caddy\Caddyfile
```

---

## 7. Adjust and test the backend launcher

Edit `C:\apps\Report_gen\deploy\windows\run-backend.bat` and set `APP_DIR` to the
real backend path (`C:\apps\Report_gen\backend`). Test it by hand:

```bat
C:\apps\Report_gen\deploy\windows\run-backend.bat
```

Then browse to `http://localhost:8000` — you should see the app. Stop it with
`Ctrl+C` once confirmed. (If you also left Caddy running, `http://localhost` —
no port — should work too.)

---

## 8. Open the firewall for port 80

In an **Administrator** Command Prompt:

```bat
netsh advfirewall firewall add rule name="YieldPortal HTTP 80" dir=in action=allow protocol=TCP localport=80
```

(uvicorn on `127.0.0.1:8000` needs no rule — loopback isn't filtered.)

---

## 9. Install the two Windows services (NSSM)

Run these in an **Administrator** Command Prompt. Replace `C:\nssm\...\nssm.exe`
with your actual NSSM path, and find your `uv.exe` path with `where uv`.

**Backend service:**

```bat
C:\nssm\win64\nssm.exe install YieldBackend "C:\apps\Report_gen\deploy\windows\run-backend.bat"
C:\nssm\win64\nssm.exe set YieldBackend AppDirectory "C:\apps\Report_gen\backend"
C:\nssm\win64\nssm.exe set YieldBackend Start SERVICE_AUTO_START
C:\nssm\win64\nssm.exe set YieldBackend AppStdout "C:\apps\Report_gen\backend\logs\service.log"
C:\nssm\win64\nssm.exe set YieldBackend AppStderr "C:\apps\Report_gen\backend\logs\service.log"
```

**Caddy service:**

```bat
C:\nssm\win64\nssm.exe install YieldCaddy "C:\caddy\caddy.exe" "run --config C:\caddy\Caddyfile"
C:\nssm\win64\nssm.exe set YieldCaddy AppDirectory "C:\caddy"
C:\nssm\win64\nssm.exe set YieldCaddy Start SERVICE_AUTO_START
```

Start them:

```bat
net start YieldBackend
net start YieldCaddy
```

(Create the backend log folder first if needed: `mkdir C:\apps\Report_gen\backend\logs`.)

---

## 10. Verify

From the shared machine and from a teammate's PC:

- `http://localhost` (on the machine itself) → app loads
- `http://<COMPUTER-NAME>` → app loads (e.g. `http://YIELD-PC`)
- `http://yieldportal.socionext.com` → app loads **once IT's DNS record is live**

Also check `http://yieldportal.socionext.com/health` returns `{"status":"ok",...}`.

---

## 11. Day-to-day operations

**Deploy an update (new code):**

```bat
cd C:\apps\Report_gen
git pull
cd frontend && npm install && npm run build
cd ..\backend && uv sync
net stop YieldBackend && net start YieldBackend
REM Caddy only needs a restart if you changed the Caddyfile:
REM   copy deploy\Caddyfile C:\caddy\Caddyfile  &&  net stop YieldCaddy && net start YieldCaddy
```

**Restart / stop:**

```bat
net stop YieldBackend & net start YieldBackend
net stop YieldCaddy   & net start YieldCaddy
```

**Logs:**
- App: `C:\apps\Report_gen\backend\logs\service.log`
- Caddy access: `C:\caddy\logs\access.log`

**Note on caching:** the app caches dashboard/explore results in memory for
3 hours. Restarting `YieldBackend` clears that cache (forces fresh DB reads).

---

## 12. Deferred — do these when the time comes

Not needed now (LAN-only, view-only, few users), but here's the order when you
outgrow that:

1. **HTTPS** — uncomment one HTTPS block in `deploy/Caddyfile` (Caddy internal CA
   for LAN-only, or a corporate-issued cert), copy it to `C:\caddy\Caddyfile`,
   restart `YieldCaddy`. Required before adding any login (so passwords aren't
   sent in clear).
2. **Authentication** — start with Caddy `basicauth` (one shared password), then
   move to corporate SSO (SAML/OIDC) when you need per-user access or product-
   level permissions.
3. **Secrets** — move the Oracle password out of plain `backend\.env` into the
   Windows Credential Manager or a secrets vault.
4. **Shared cache / multi-process** — if you scale beyond one uvicorn worker,
   move the in-memory cache to Redis so all workers share it.
5. **Monitoring & backups** — uptime check on `/health`, log rotation/retention,
   and a documented restore procedure.

---

## 13. Troubleshooting

| Symptom | Check |
|---|---|
| `http://localhost:8000` works but `http://localhost` doesn't | Caddy not running, or port 80 used by another app (IIS?). `net start YieldCaddy`; check `C:\caddy\logs`. |
| Teammates can't reach it by name/IP | Firewall rule for port 80 (Step 8); DNS record live? Try the IP directly first. |
| FQDN fails but IP/computer-name works | DNS record for `yieldportal.socionext.com` not yet pointing here — follow up with IT. |
| App shows no data / DB errors | `backend\.env` Oracle settings; see `service.log`. `USE_MOCK_DATA` must be `false`. |
| Service won't start | Run the `.bat` / `caddy run` by hand to see the real error; verify paths in the NSSM config (`nssm edit YieldBackend`). |
| Port 80 already taken | Windows IIS or "World Wide Web Publishing Service" may own it — stop/disable it, or change Caddy's `:80` to another port. |
