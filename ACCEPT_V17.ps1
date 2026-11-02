# V1.7 one-command local release gate. No migrations, deployments or DB modifications.
param([switch]$LiveNeon)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$reportDir = Join-Path $root 'acceptance_reports'
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$report = Join-Path $reportDir 'V17_ACCEPTANCE.json'
$results = [ordered]@{version='1.7'; timestamp=(Get-Date).ToString('o'); python='3.14'; offline='NOT_RUN'; neon='SKIPPED'; status='FAIL'}
try {
    Push-Location (Join-Path $root 'backend')
    try {
        & py -3.14 -m pytest -q tests/test_v17_transport.py tests/test_v17_network_recovery.py tests/test_mcp_v15_release_contract.py tests/test_v15_portfolio_migration_contract.py tests/test_v16_portfolio_contract.py tests/test_v16_rc4_security.py tests/test_v16_rc5_release_gate.py
        if ($LASTEXITCODE -ne 0) { throw 'V17 OFFLINE CONTRACT GATE FAILED' }
        $results.offline='PASS'
        if ($LiveNeon) {
            if ($env:V16_DEV_BRANCH_CONFIRMED -ne 'dev-v1-6-backend-pg18') { throw 'Explicit dev branch confirmation required' }
            if (-not $env:PORTFOLIO_READONLY_DATABASE_URL) { throw 'Dedicated reader DSN required' }
            & py -3.14 scripts/v16_rc4_neon_live_gate.py
            if ($LASTEXITCODE -ne 0) { throw 'NEON LIVE GATE FAILED' }
            $results.neon='PASS'
        }
        $results.status='PASS'
        Write-Host 'V1.7 SELECTED OFFLINE GATE PASSED (PG16 live and browser gates are separate)'
    } finally { Pop-Location }
} catch {
    $results.error_code='GATE_FAILED'
    Write-Host 'V1.7 GATE FAILED - see test output above' -ForegroundColor Red
    throw
} finally {
    $results | ConvertTo-Json -Depth 4 | Set-Content -Path $report -Encoding utf8
    Write-Host "Report: $report"
}
