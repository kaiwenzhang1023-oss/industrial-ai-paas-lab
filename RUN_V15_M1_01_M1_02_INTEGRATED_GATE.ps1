param([string]$PythonPath = '')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$container='m2_pg16_gate-postgres-1'
$db='industrial_lab_v15_test'
if (-not $PythonPath) {
 $parent=Split-Path -Parent $root
 $PythonPath=Join-Path $parent 'Industrial_AI_PaaS_Lab_V1.5_M1-01_Full_Source_Candidate\.venv314\Scripts\python.exe'
}
if (-not (Test-Path $PythonPath)) { throw 'Pass -PythonPath pointing to existing Python 3.14 environment. No installation needed.' }
if (-not $env:M1_TEST_DATABASE_URL) { throw 'Set M1_TEST_DATABASE_URL to isolated Docker PG16 TEST database. Never print it.' }
$ver=(docker exec $container psql -X -U lab -d $db -Atqc 'SHOW server_version_num' 2>&1)
if ($LASTEXITCODE -ne 0 -or $ver.Trim() -notmatch '^16\d{4}$') { throw 'Existing Docker PG16 check failed' }
Write-Host 'Target: existing Docker PG16 / industrial_lab_v15_test'
Write-Host 'Applying additive 018 security role migration ONLY (017 remains unchanged)'
Get-Content -Raw (Join-Path $root 'database\018_v15_gateway_security_roles.sql') | docker exec -i $container psql -X -v ON_ERROR_STOP=1 -U lab -d $db
if ($LASTEXITCODE -ne 0) { throw '018 migration FAILED' }
$env:PYTHONPATH=Join-Path $root 'backend'
& $PythonPath -m pytest -q (Join-Path $root 'backend\tests\test_mcp_v15_gateway_unit.py') (Join-Path $root 'backend\tests\test_mcp_v15_final_gate_pg16.py') (Join-Path $root 'backend\tests\test_mcp_v15_security_hardening_pg16.py') (Join-Path $root 'backend\tests\test_mcp_v15_pg16.py') (Join-Path $root 'backend\tests\test_mcp_v15_security_unit.py')
if ($LASTEXITCODE -ne 0) { throw 'Integrated gate FAILED; do not enable MCP tools.' }
Write-Host 'Integrated test gate PASS. Business tools remain disabled.'
