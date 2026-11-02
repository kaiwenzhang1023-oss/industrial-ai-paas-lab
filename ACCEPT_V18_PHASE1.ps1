# V1.8 Phase 1 local-only acceptance. No database or production access.
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$reportDir=Join-Path $root 'acceptance_reports'
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$report=Join-Path $reportDir 'V18_PHASE1_ACCEPTANCE.json'
$result=[ordered]@{version='1.8'; phase='1'; timestamp=(Get-Date).ToString('o'); offline='FAIL'; production='NO_GO'}
try {
    Push-Location (Join-Path $root 'backend')
    try {
        & py -3.14 -m pytest -q tests/test_v18_network_recovery.py tests/test_v17_transport.py tests/test_v17_network_recovery.py tests/test_v17_final_smoke.py tests/test_mcp_v15_release_contract.py tests/test_v15_portfolio_migration_contract.py tests/test_v16_portfolio_contract.py tests/test_v16_rc4_security.py tests/test_v16_rc5_release_gate.py
        if ($LASTEXITCODE -ne 0) {throw 'V18 PHASE1 GATE FAILED'}
        $result.offline='PASS'
        Write-Host 'V1.8 PHASE1 LOCAL TRANSPORT + RECOVERY SAFETY GATE PASSED'
        Write-Host 'NOT CERTIFIED: internet MCP, OAuth, persistent sessions, crash replay, PG16, browser.'
    } finally {Pop-Location}
} finally {
    $result | ConvertTo-Json -Depth 4 | Set-Content -Path $report -Encoding utf8
    Write-Host "Report: $report"
}
