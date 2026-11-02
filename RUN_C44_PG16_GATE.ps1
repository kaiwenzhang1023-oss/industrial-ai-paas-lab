$ErrorActionPreference = "Stop"
$Container = if ($env:PG16_CONTAINER) { $env:PG16_CONTAINER } else { "m2_pg16_gate-postgres-1" }
$Database = "industrial_lab_v15_test"
$Migration = Join-Path $PSScriptRoot "database\025_v15_request_ledger_security_api_TEST_ONLY.sql"
$Acceptance = Join-Path $PSScriptRoot "database\025_v15_request_ledger_security_api_ACCEPTANCE_TEST_ONLY.sql"

$pythonVersion = (& python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
if ($pythonVersion -ne "3.14") { throw "PYTHON_314_REQUIRED; found $pythonVersion" }
foreach ($name in @("M1_TEST_DATABASE_URL", "V15_BUSINESS_DATABASE_URL", "V18_ISOLATED_PG16_DSN")) {
    if (-not [Environment]::GetEnvironmentVariable($name)) { throw "$name is required for the PG16 integration gate" }
}
$env:V18_ALLOW_ISOLATED_PG16 = "YES"

Write-Host "=== C4.4 APPLY FORWARD-ONLY TEST MIGRATION ===" -ForegroundColor Cyan
$MigrationTarget = "/tmp/c44_ledger_security_migration.sql"
$AcceptanceTarget = "/tmp/c44_ledger_security_acceptance.sql"
docker cp $Migration "${Container}:$MigrationTarget"
if ($LASTEXITCODE -ne 0) { throw "C4.4 MIGRATION COPY FAILED" }
docker exec $Container psql -X -v ON_ERROR_STOP=1 -U lab -d $Database -f $MigrationTarget
if ($LASTEXITCODE -ne 0) { throw "C4.4 MIGRATION FAILED" }

Write-Host "=== C4.4 PG16 SQL SECURITY / IDEMPOTENCY ACCEPTANCE ===" -ForegroundColor Cyan
docker cp $Acceptance "${Container}:$AcceptanceTarget"
if ($LASTEXITCODE -ne 0) { throw "C4.4 ACCEPTANCE COPY FAILED" }
docker exec $Container psql -X -v ON_ERROR_STOP=1 -U lab -d $Database -f $AcceptanceTarget
if ($LASTEXITCODE -ne 0) { throw "C4.4 PG16 SQL ACCEPTANCE FAILED" }

Push-Location (Join-Path $PSScriptRoot "backend")
try {
    Write-Host "=== C4.4 BROAD OFFLINE REGRESSION ===" -ForegroundColor Cyan
    python -m pytest -q `
        --ignore=tests/test_integrated_postgres.py `
        --ignore=tests/test_mes_v13_postgres_rc2.py `
        --ignore=tests/test_pg_contract_v02.py `
        --ignore=tests/test_v12_wms_mrp_postgres.py `
        --ignore=tests/test_workflow_postgres.py `
        --ignore=tests/test_workflow_v03_postgres.py `
        --ignore=tests/test_workflow_worker_postgres.py `
        --ignore=tests/test_agent_atomic_v03.py `
        --ignore=tests/test_mcp_v15_full_batch_pg16.py `
        --ignore=tests/test_v18_final_browser.py
    if ($LASTEXITCODE -ne 0) { throw "C4.4 OFFLINE REGRESSION FAILED" }

    Write-Host "=== C4.4 LIVE PG16 INTEGRATION REGRESSION ===" -ForegroundColor Cyan
    python -m pytest -q `
        tests/test_mcp_v15_final_gate_pg16.py `
        tests/test_mcp_v15_security_hardening_pg16.py `
        tests/test_mcp_v15_pg16.py `
        tests/test_mcp_v15_full_batch_pg16.py `
        tests/test_v15_ledger_security_api_pg16.py `
        tests/test_v18_phase4_live_pg16.py
    if ($LASTEXITCODE -ne 0) { throw "C4.4 LIVE PG16 INTEGRATION FAILED" }
}
finally { Pop-Location }
Write-Host "C44_PG16_GATE_AND_FULL_REGRESSION_PASSED" -ForegroundColor Green
