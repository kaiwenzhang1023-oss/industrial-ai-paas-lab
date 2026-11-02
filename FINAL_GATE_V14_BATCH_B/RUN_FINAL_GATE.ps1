# Run from this directory using Windows PowerShell and Python 3.14.
# Deliberately does NOT apply migrations, create/drop databases, or seed data.
$ErrorActionPreference = 'Stop'
$backend = (Resolve-Path (Join-Path $PSScriptRoot '..\backend')).Path
$dsn = $env:TEST_DATABASE_URL
if ([string]::IsNullOrWhiteSpace($dsn)) { throw 'TEST_DATABASE_URL is required' }
if ($dsn -notmatch '/industrial_lab_v14_test(\?|$)') { throw 'Only industrial_lab_v14_test is allowed' }
if ($env:DATABASE_URL) { throw 'Unset DATABASE_URL to prevent production access' }
$version = & python --version 2>&1
if ($LASTEXITCODE -ne 0 -or -not $version.Trim().StartsWith('Python 3.14.')) { throw 'Python 3.14 required' }
Push-Location $backend
try {
  & python -c 'import psycopg; print("psycopg OK")'
  if ($LASTEXITCODE -ne 0) { throw 'psycopg is required' }
  & python -c 'import os,psycopg; c=psycopg.connect(os.environ["TEST_DATABASE_URL"]); r=c.execute("SELECT current_database(), to_regclass(%s)", ("mapping_v14.execution_runs",)).fetchone(); print(r); assert r[0]=="industrial_lab_v14_test" and r[1] is not None; c.close()'
  if ($LASTEXITCODE -ne 0) { throw 'PG16 schema or DB gate failed. Review migration 016 manually after backup and approval.' }
  & python -m pytest -q -rs tests/mapping/test_m103_pg16.py
  if ($LASTEXITCODE -ne 0) { throw 'PG16 integration failed' }
  # A skip is NOT a pass. This test requires existing completed MRP BUY source data.
  & python -m pytest -q -rs tests/mapping tests/test_srm_v14_batch_a.py tests/test_integrated_m2.py tests/test_mes_v13_batch_a.py tests/test_mes_v13_batch_b_contract.py tests/test_mes_v13_batch_c_gate.py tests/test_workflow_unit.py tests/test_workflow_v03_unit.py tests/test_workflow_worker_unit.py
  if ($LASTEXITCODE -ne 0) { throw 'Unit regression failed' }
  Write-Host 'These commands do not constitute full signoff: inspect skip counts, run dedicated SRM/MES/Workflow PG16 suites on their own isolated DBs, and verify read-only role privileges.'
} finally { Pop-Location }



