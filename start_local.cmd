@echo off
setlocal
cd /d "%~dp0backend"
if not exist ".venv314\Scripts\python.exe" (echo Missing Python environment. Run PG gate first.& exit /b 1)
set "DATABASE_URL=postgresql://lab:local_demo_only@localhost:5432/industrial_lab_demo"
set "DEMO_WRITE_ENABLED=1"
echo Workbench: http://127.0.0.1:8000/workbench/
".venv314\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
