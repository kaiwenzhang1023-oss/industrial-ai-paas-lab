# RC2 Final Gate: run only in a fresh PowerShell from this package root.
$ErrorActionPreference = 'Stop'
$backend = Join-Path $PSScriptRoot 'backend'
if (-not (Test-Path $backend)) { throw 'Missing backend' }
if (-not $env:TEST_DATABASE_URL) { throw 'TEST_DATABASE_URL missing' }
$u = [uri]$env:TEST_DATABASE_URL
if ($u.Host -ne '127.0.0.1' -or $u.Port -ne 5432 -or $u.AbsolutePath.TrimStart('/') -ne 'industrial_lab_v13_test' -or $u.UserInfo.Split(':')[0] -ne 'lab') { throw 'REFUSE: wrong database target' }
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:V11_ISOLATED_BRANCH_ACK -ErrorAction SilentlyContinue
Push-Location $backend
try {
  py -3.14 -m pytest -q -s tests/test_mes_v13_postgres_rc2.py
  if ($LASTEXITCODE -ne 0) { throw 'RC2 FINAL GATE FAILED' }
  Write-Host 'RC2 PG16 AUTOMATED GATE PASSED. Browser manual gate remains required.'
} finally { Pop-Location }
