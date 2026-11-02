$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$backend = Join-Path $root 'backend'
$reports = Join-Path $root 'acceptance_reports'
New-Item -ItemType Directory -Force -Path $reports | Out-Null
$reportPath = Join-Path $reports 'C43_OFFLINE_ACCEPTANCE.json'
$result = [ordered]@{
    version = '1.8-C4.3'
    timestamp = (Get-Date).ToString('o')
    python = 'NOT_CHECKED'
    compileall = 'NOT_RUN'
    c43_focused = 'NOT_RUN'
    broad_offline = 'NOT_RUN'
    pg16_live = 'NOT_RUN'
    browser = 'NOT_RUN'
    production = 'NO_GO'
    overall = 'INCOMPLETE'
}
$failed = $false
try {
    Push-Location $backend
    try {
        $py = (& py -3.14 --version 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or $py -notmatch '^Python 3\.14\.') {
            throw "PYTHON_314_REQUIRED: $py"
        }
        $result.python = $py

        & py -3.14 -m compileall -q app tests
        if ($LASTEXITCODE -ne 0) { throw 'COMPILEALL_FAILED' }
        $result.compileall = 'PASS'

        & py -3.14 -m pytest -q `
            tests/test_v18_c43_identity_isolation.py `
            tests/test_v18_phase2_durable_ledger.py `
            tests/test_v18_phase3_secure_bridge.py `
            tests/test_v18_network_recovery.py `
            tests/test_v18_phase4_http_workbench.py `
            tests/test_mcp_v15_release_contract.py
        if ($LASTEXITCODE -ne 0) { throw 'C43_FOCUSED_GATE_FAILED' }
        $result.c43_focused = 'PASS'

        & py -3.14 -m pytest -q -m 'not integration' `
            --ignore=tests/test_integrated_postgres.py `
            --ignore=tests/test_mes_v13_postgres_rc2.py `
            --ignore=tests/test_pg_contract_v02.py `
            --ignore=tests/test_v12_wms_mrp_postgres.py `
            --ignore=tests/test_workflow_postgres.py `
            --ignore=tests/test_workflow_v03_postgres.py `
            --ignore=tests/test_workflow_worker_postgres.py `
            --ignore=tests/test_erp_v11_stage3_postgres.py `
            --ignore=tests/test_mcp_v15_full_batch_pg16.py `
            --ignore=tests/test_v18_phase4_live_pg16.py `
            --ignore=tests/test_v18_final_browser.py
        if ($LASTEXITCODE -ne 0) { throw 'BROAD_OFFLINE_GATE_FAILED' }
        $result.broad_offline = 'PASS'
        $result.overall = 'OFFLINE_GATES_PASS_PG16_BROWSER_PENDING'
        Write-Host 'C4.3 OFFLINE GATES: PASS' -ForegroundColor Green
        Write-Host 'PG16 live and real-browser gates remain pending.' -ForegroundColor Yellow
    } finally { Pop-Location }
} catch {
    $result.overall = 'FAIL'
    $failed = $true
    Write-Host "C4.3 GATE FAILED: $_" -ForegroundColor Red
} finally {
    $result | ConvertTo-Json -Depth 5 | Set-Content -Path $reportPath -Encoding UTF8
    Write-Host "Report: $reportPath"
}
if ($failed) { exit 1 }
