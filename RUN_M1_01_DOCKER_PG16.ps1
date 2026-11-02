param([switch]$ApplyMigration,[switch]$RunTests)
$ErrorActionPreference='Stop'
$container='m2_pg16_gate-postgres-1'
$db='industrial_lab_v15_test'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$source=Join-Path $root 'database\017_v15_mcp_security.sql'
$ver=(docker exec $container psql -U lab -d $db -Atqc 'SHOW server_version_num' 2>&1)
if ($LASTEXITCODE -ne 0 -or -not ($ver -match '^16\d{4}$')) { throw "Docker PG16 gate failed: $ver" }
Write-Host "Docker PG16 PASS: $container / $db / $ver"
if ($ApplyMigration) {
  $sql=[IO.File]::ReadAllText($source)
  $sql | docker exec -i $container psql -X -v ON_ERROR_STOP=1 -U lab -d $db
  if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
  Write-Host 'M1-01 migration applied to isolated TEST database only.'
}
if ($RunTests) {
  $python=Join-Path $root '.venv314\Scripts\python.exe'
  if (-not (Test-Path $python)) { throw 'Place or create a Python 3.14 virtualenv at .venv314; do not copy another venv.' }
  if (-not $env:M1_TEST_DATABASE_URL) { throw 'M1_TEST_DATABASE_URL required for integration tests (not printed).' }
  $env:PYTHONPATH=Join-Path $root "backend"
  & $python -m pytest -q (Join-Path $root 'backend\tests\test_mcp_v15_security_unit.py') (Join-Path $root 'backend\tests\test_mcp_v15_pg16.py')
  if ($LASTEXITCODE -ne 0) { throw 'M1-01 tests failed' }
}
