param([string]$PythonPath = '')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$parent=Split-Path -Parent $root
$container='m2_pg16_gate-postgres-1'
if (-not $PythonPath) {
 $PythonPath=Join-Path $root '.venv314\Scripts\python.exe'
 if (-not (Test-Path $PythonPath)) {
  $legacy=Join-Path $parent 'Industrial_AI_PaaS_Lab_V1.5_M1-01_Full_Source_Candidate\.venv314'
  if (Test-Path (Join-Path $legacy 'Scripts\python.exe')) {
   Write-Host 'One-time copying existing Python 3.14.6 environment into standalone V1.5 directory.'
   Copy-Item -LiteralPath $legacy -Destination (Join-Path $root '.venv314') -Recurse -Force
  } else {
   throw 'Standalone Python environment missing. Keep old M1-01 folder until first successful run; use -PythonPath if venv is elsewhere.'
  }
 }
}
if (-not (Test-Path $PythonPath)) { throw 'Existing Python 3.14.6 venv missing; use -PythonPath. No installation performed.' }
$ver=(& $PythonPath -V 2>&1 | Out-String).Trim()
if ($ver -ne 'Python 3.14.6') { throw "Python 3.14.6 required: $ver" }
$running=docker ps --filter "name=^${container}$" --format '{{.Names}}'
if ($LASTEXITCODE -ne 0 -or $running -ne $container) { throw 'Docker PG16 container unavailable' }
$dbUser=(docker exec $container printenv POSTGRES_USER).Trim()
$dbPassword=(docker exec $container printenv POSTGRES_PASSWORD).Trim()
$portLine=docker port $container 5432/tcp | Select-Object -First 1
$port=[int](($portLine -split ':')[-1]); $u=[uri]::EscapeDataString($dbUser); $pw=[uri]::EscapeDataString($dbPassword)
$env:M1_TEST_DATABASE_URL="postgresql://${u}:${pw}@127.0.0.1:${port}/industrial_lab_v15_test"
$env:V15_BUSINESS_DATABASE_URL="postgresql://${u}:${pw}@127.0.0.1:${port}/industrial_lab_v14_test"
$env:PYTHONPATH=Join-Path $root 'backend'
$preflight=@'
import os,psycopg
for env,expected in [('M1_TEST_DATABASE_URL','industrial_lab_v15_test'),('V15_BUSINESS_DATABASE_URL','industrial_lab_v14_test')]:
 with psycopg.connect(os.environ[env]) as c:
  db,ver=c.execute('SELECT current_database(),current_setting(%s)',('server_version_num',)).fetchone()
  assert db==expected and int(ver)//10000==16, (db,ver)
  required= ['mcp_v15.tool_call_state','mcp_v15.tool_call_audit','mcp_v15.resource_registry'] if 'M1_' in env else ['platform.integrated_mrp_payloads','mock_wms.inventory_balances','mes_v13.work_orders','srm_v14.purchase_requisitions','mock_erp.materials']
  missing=[x for x in required if not c.execute('SELECT to_regclass(%s)',(x,)).fetchone()[0]]
  assert not missing,(db,missing)
print('DUAL DATABASE IDENTITY AND SCHEMA: PASS')
'@
$preflight | & $PythonPath -
if ($LASTEXITCODE -ne 0) { throw 'Preflight FAILED; no migrations applied.' }
# 019 is an additive test-only migration. Apply only when the expected role/function is absent.
$hasRole=(docker exec $container psql -X -U $dbUser -d industrial_lab_v14_test -Atqc "SELECT EXISTS(SELECT FROM pg_roles WHERE rolname='mcp_v15_business_reader_test') AND COALESCE(has_column_privilege('mcp_v15_business_reader_test','platform.integrated_mrp_payloads','result_json','SELECT'),false)")
if ($LASTEXITCODE -ne 0) { throw 'Business role check FAILED' }
if ($hasRole.Trim() -ne 't') {
 Write-Host 'Applying TEST-only business read role migration 019 once'
 Get-Content -Raw (Join-Path $root 'database\019_v15_business_readonly_test.sql') | docker exec -i $container psql -X -v ON_ERROR_STOP=1 -U $dbUser -d industrial_lab_v14_test
 if ($LASTEXITCODE -ne 0) { throw 'Business role migration FAILED' }
}
$hasRecovery=(docker exec $container psql -X -U $dbUser -d industrial_lab_v15_test -Atqc "SELECT to_regprocedure('mcp_v15.runtime_stale_running(integer)') IS NOT NULL")
if ($LASTEXITCODE -ne 0) { throw 'Recovery function check FAILED' }
if ($hasRecovery.Trim() -ne 't') {
 Write-Host 'Applying TEST-only runtime recovery migration 019 once'
 Get-Content -Raw (Join-Path $root 'database\019_v15_runtime_recovery_test.sql') | docker exec -i $container psql -X -v ON_ERROR_STOP=1 -U $dbUser -d industrial_lab_v15_test
 if ($LASTEXITCODE -ne 0) { throw 'Runtime recovery migration FAILED' }
}
$hasLedger=(docker exec $container psql -X -U $dbUser -d industrial_lab_v15_test -Atqc "SELECT to_regclass('mcp_v15.request_ledger') IS NOT NULL")
if ($LASTEXITCODE -ne 0) { throw 'Ledger preflight FAILED' }
if ($hasLedger.Trim() -ne 't') {
 Write-Host 'Applying TEST-only idempotency migration 020 once'
 Get-Content -Raw (Join-Path $root 'database\020_v15_request_ledger_test.sql') | docker exec -i $container psql -X -v ON_ERROR_STOP=1 -U $dbUser -d industrial_lab_v15_test
 if ($LASTEXITCODE -ne 0) { throw 'Idempotency migration FAILED' }
}
$tests=@('test_mcp_v15_gateway_unit.py','test_mcp_v15_final_gate_pg16.py','test_mcp_v15_security_hardening_pg16.py','test_mcp_v15_pg16.py','test_mcp_v15_security_unit.py','test_mcp_v15_full_batch_unit.py','test_mcp_v15_full_batch_pg16.py','test_mcp_v15_release_contract.py')
$paths=@($tests | ForEach-Object {Join-Path $root ('backend\tests\'+$_)})
Write-Host 'Running all V1.5 regression tests; no pip, venv creation or 017/018 replay.'
& $PythonPath -m pytest -q @paths
if ($LASTEXITCODE -ne 0) { throw 'FULL GATE FAILED. MCP tools remain disabled.' }
Write-Host 'V1.5 TEST GATE PASS; 44 deterministic golden contract cases included; real authorized E2E and production release are NOT certified.'
