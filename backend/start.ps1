# Yield Trend Report — Backend Startup Script (Windows)
# Usage: cd backend; .\start.ps1

# ── 1. Kill any process already using port 8000 ─────────────────────────────
Write-Host "Checking port 8000..."
$lines = netstat -ano | Select-String "TCP\s+[\d.]+:8000\s"
$pids  = $lines | ForEach-Object { ($_ -split "\s+")[-1] } | Select-Object -Unique
foreach ($p in $pids) {
    if ($p -match "^\d+$" -and $p -ne "0") {
        Write-Host "  Stopping PID $p"
        taskkill /PID $p /F 2>$null | Out-Null
    }
}

# ── 2. Start uvicorn ─────────────────────────────────────────────────────────
Write-Host "Starting backend on http://0.0.0.0:8000 ..."
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
