$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Require-Command([string]$Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Required command '$Name' was not found. Install it and reopen PowerShell."
  }
}

Require-Command 'docker'
Require-Command 'py'

docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Docker is installed but the Docker Engine is not running. Start Docker Desktop and retry.' }

Write-Host '== Start PostgreSQL 16 ==' -ForegroundColor Cyan
docker compose up -d postgres
if ($LASTEXITCODE -ne 0) { throw 'docker compose up failed.' }

$Ready = $false
for ($i = 0; $i -lt 40; $i++) {
  docker compose exec -T postgres pg_isready -U lab -d industrial_lab *> $null
  if ($LASTEXITCODE -eq 0) { $Ready = $true; break }
  Start-Sleep -Seconds 2
}
if (-not $Ready) { throw 'PostgreSQL did not become ready within 80 seconds.' }

Write-Host '== Recreate isolated test database ==' -ForegroundColor Cyan
docker compose exec -T postgres psql -U lab -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS industrial_lab_test WITH (FORCE)"
if ($LASTEXITCODE -ne 0) { throw 'Could not drop the disposable test database.' }
docker compose exec -T postgres psql -U lab -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE industrial_lab_test"
if ($LASTEXITCODE -ne 0) { throw 'Could not create the disposable test database.' }

$MigrationFiles = @('schema.sql','003_v03.sql','004_snapshot_fence.sql','005_effective_bom.sql','006_m2_integration.sql','007_normalized_pegging.sql','008_workflow_runtime.sql','009_workflow_worker.sql','010_agent_harness.sql','011_agent_governance.sql','012_outbox_receipts.sql')
foreach ($FileName in $MigrationFiles) {
  $LocalFile = Join-Path $Root (Join-Path 'database' $FileName)
  if (-not (Test-Path $LocalFile)) { throw "Migration file missing: $LocalFile" }
  Write-Host "== Apply $FileName ==" -ForegroundColor Cyan
  docker compose cp $LocalFile "postgres:/tmp/$FileName"
  if ($LASTEXITCODE -ne 0) { throw "Failed to copy migration $FileName into PostgreSQL container." }
  docker compose exec -T postgres psql -U lab -d industrial_lab_test -v ON_ERROR_STOP=1 -f "/tmp/$FileName"
  if ($LASTEXITCODE -ne 0) { throw "Migration failed: $FileName" }
}

$env:TEST_DATABASE_URL = 'postgresql://lab:local_demo_only@localhost:5432/industrial_lab_test'
$Backend = Join-Path $Root 'backend'
$PythonExe = Join-Path $Backend '.venv314\Scripts\python.exe'
if (-not (Test-Path $PythonExe)) {
  Write-Host '== Create Python 3.14 virtual environment ==' -ForegroundColor Cyan
  & py -3.14 -m venv (Join-Path $Backend '.venv314')
  if ($LASTEXITCODE -ne 0) { throw 'Failed to create Python 3.14 environment.' }
}
if (-not (Test-Path $PythonExe)) { throw 'Python 3.14 environment was not created.' }
$PythonVersion = & $PythonExe --version
if ($PythonVersion -notmatch '^Python 3\.14\.') { throw "Expected Python 3.14, got $PythonVersion" }
Write-Host "Using $PythonVersion"
Set-Location $Backend

Write-Host '== Install backend test dependencies ==' -ForegroundColor Cyan
$env:PIP_INDEX_URL = 'https://pypi.org/simple'
& $PythonExe -m pip install -e '.[test]'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }

$IntegrationLog = Join-Path $Root 'pg16_integration.log'
$RegressionLog = Join-Path $Root 'pg16_full_regression.log'

Write-Host '== Run marked PostgreSQL integration tests ==' -ForegroundColor Cyan
& $PythonExe -m pytest -v -m integration 2>&1 | Tee-Object -FilePath $IntegrationLog
$IntegrationExit = $LASTEXITCODE

Write-Host '== Run full regression suite with PostgreSQL enabled ==' -ForegroundColor Cyan
& $PythonExe -m pytest -v 2>&1 | Tee-Object -FilePath $RegressionLog
$RegressionExit = $LASTEXITCODE

Write-Host "Integration exit code: $IntegrationExit"
Write-Host "Full regression exit code: $RegressionExit"
Write-Host "Logs saved: $IntegrationLog and $RegressionLog"
if ($IntegrationExit -ne 0 -or $RegressionExit -ne 0) {
  Write-Error 'TEST GATE FAILED. Upload both log files for diagnosis; do not sign off M4 V0.2.'
  exit 1
}
if ((Select-String -Path $IntegrationLog,$RegressionLog -Pattern '\b[1-9][0-9]* skipped\b' -Quiet)) { throw 'TEST GATE FAILED: skipped tests detected in logs.' }
# Contract gate: enforce collection counts, not merely process exit codes.
$IntegrationSummary = (Get-Content $IntegrationLog -Tail 25 | Select-String -Pattern '=+\s*(\d+) passed, (\d+) deselected' | Select-Object -Last 1)
$RegressionSummary = (Get-Content $RegressionLog -Tail 25 | Select-String -Pattern '=+\s*(\d+) passed' | Select-Object -Last 1)
if (-not $IntegrationSummary -or [int]$IntegrationSummary.Matches[0].Groups[1].Value -ne 27) {
  throw 'TEST GATE FAILED: expected exactly 27 PostgreSQL integration tests passed.'
}
if (-not $RegressionSummary -or [int]$RegressionSummary.Matches[0].Groups[1].Value -ne 166) {
  throw 'TEST GATE FAILED: expected exactly 166 full regression tests passed.'
}
Write-Host 'TEST COMMANDS PASSED. Expected 27 PG integration / 166 full regression passed; inspect logs before signoff.' -ForegroundColor Green
exit 0
