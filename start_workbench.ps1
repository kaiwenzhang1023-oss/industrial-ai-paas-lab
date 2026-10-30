$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$Python=Join-Path $Root 'backend\.venv314\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'Python 3.14 environment missing. Run .\run_pg16_gate.ps1 first.' }
$Version=& $Python --version
if ($Version -notmatch '^Python 3\.14\.') { throw "Expected Python 3.14, got $Version" }
if (-not $env:DATABASE_URL) { $env:DATABASE_URL='postgresql://lab:local_demo_only@localhost:5432/industrial_lab_demo' }
$env:DEMO_WRITE_ENABLED='1'
Write-Host 'Workbench: http://127.0.0.1:8000/workbench/' -ForegroundColor Green
Write-Host "Database: $($env:DATABASE_URL -replace '://[^@]+@','://***@')"
Push-Location (Join-Path $Root 'backend')
try { & $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 }
finally { Pop-Location }
