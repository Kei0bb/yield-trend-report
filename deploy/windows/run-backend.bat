@echo off
REM ===========================================================================
REM run-backend.bat — start the Yield Portal FastAPI backend (production)
REM
REM Binds to 127.0.0.1 ONLY: the app is reached through Caddy, never directly
REM from the network. Edit APP_DIR below to match this machine.
REM
REM Used by the NSSM Windows service "YieldBackend" (see docs/deploy-windows.md),
REM or run by hand to test before installing the service.
REM ===========================================================================

REM --- EDIT THIS: full path to the backend folder on this machine -----------
set APP_DIR=C:\apps\Report_gen\backend

REM --- Use the real Oracle DB (not mock). DB creds come from backend\.env ----
set USE_MOCK_DATA=false

cd /d "%APP_DIR%"
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
