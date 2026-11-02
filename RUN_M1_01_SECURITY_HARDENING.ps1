$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$container = 'm2_pg16_gate-postgres-1'
$db = 'industrial_lab_v15_test'
$python = Join-Path $root '.venv314\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Existing .venv314 is required. Do not copy a venv.' }
if (-not $env:M1_TEST_DATABASE_URL) { throw 'M1_TEST_DATABASE_URL missing. Set locally; never print it.' }
$ver = (docker exec $container psql -X -U lab -d $db -Atqc 'SHOW server_version_num' 2>&1)
if ($LASTEXITCODE -ne 0 -or $ver.Trim() -notmatch '^16\d{4}$') { throw 'Existing Docker PG16 verification failed' }
Write-Host "Existing Docker PG16 verified: $container / $db / $ver"
$env:PYTHONPATH = Join-Path $root 'backend'
& $python -m pytest -q (Join-Path $root 'backend\tests\test_mcp_v15_security_hardening_pg16.py')
if ($LASTEXITCODE -ne 0) { throw 'M1-01 security hardening FAILED' }
Write-Host 'Security hardening test suite passed. This does not authorize MCP business tools.'
