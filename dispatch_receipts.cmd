@echo off
setlocal
cd /d "%~dp0backend"
if not exist ".venv314\Scripts\python.exe" (echo Python environment missing.& exit /b 1)
set "DATABASE_URL=postgresql://lab:local_demo_only@localhost:5432/industrial_lab_demo"
".venv314\Scripts\python.exe" -m app.workflow.receipt_dispatcher --confirm --limit 100
