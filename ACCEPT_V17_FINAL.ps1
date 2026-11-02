# V1.7 Final local acceptance. Safe by default: no database, Neon, Render or Docker mutations.
param([switch]$LivePG16, [switch]$Browser)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$reportDir = Join-Path $root 'acceptance_reports'
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$report = Join-Path $reportDir 'V17_FINAL_ACCEPTANCE.json'
$result = [ordered]@{
    version='1.7'; candidate='FINAL_RC'; timestamp=(Get-Date).ToString('o')
    offline='NOT_RUN'; http_loopback='NOT_RUN'; recovery='NOT_RUN'
    workbench_static='NOT_RUN'; pg16='NOT_RUN'; browser='NOT_RUN'; status='FAIL'
}
try {
    Push-Location (Join-Path $root 'backend')
    try {
        & py -3.14 -m pytest -q tests/test_v17_transport.py tests/test_v17_network_recovery.py tests/test_v17_final_smoke.py tests/test_mcp_v15_release_contract.py tests/test_v15_portfolio_migration_contract.py tests/test_v16_portfolio_contract.py tests/test_v16_rc4_security.py tests/test_v16_rc5_release_gate.py
        if ($LASTEXITCODE -ne 0) { throw 'V17 FINAL OFFLINE / HTTP SMOKE GATE FAILED' }
        $result.offline='PASS'; $result.http_loopback='PASS'; $result.recovery='PASS'; $result.workbench_static='PASS'
        if ($LivePG16) {
            # Explicit opt-in; never provision or migrate databases from the release gate.
            if (-not $env:M1_TEST_DATABASE_URL -or -not $env:V15_BUSINESS_DATABASE_URL) {
                throw 'LIVE PG16 requires preconfigured isolated TEST database DSNs'
            }
            $env:V15_PORTFOLIO_E2E='1'
            try {
                & py -3.14 -m pytest -q tests/test_v15_portfolio_authorized_e2e_pg16.py
                if ($LASTEXITCODE -ne 0) { throw 'LIVE PG16 GATE FAILED' }
            } finally { Remove-Item Env:V15_PORTFOLIO_E2E -ErrorAction SilentlyContinue }
            $result.pg16='PASS'
        } else { $result.pg16='SKIPPED (requires isolated test DB and explicit -LivePG16)' }
        if ($Browser) {
            # Cannot certify browser behavior from a CLI-only run.
            $result.browser='MANUAL_REQUIRED'
            Write-Host 'Browser gate requires manual Workbench check; not marked PASS.'
        } else { $result.browser='SKIPPED (browser/manual)' }
        $result.status='PASS_WITH_LIMITATIONS'
        Write-Host 'V1.7 FINAL RC LOCAL HTTP + RECOVERY + STATIC WORKBENCH GATE PASSED'
        Write-Host 'NOT CERTIFIED: live PG16 unless opted in, browser UX, production network MCP, crash replay.'
    } finally { Pop-Location }
} catch {
    $result.error_code='GATE_FAILED'
    Write-Host 'V1.7 FINAL RC GATE FAILED' -ForegroundColor Red
    throw
} finally {
    $result | ConvertTo-Json -Depth 4 | Set-Content -Path $report -Encoding utf8
    Write-Host "Report: $report"
}
