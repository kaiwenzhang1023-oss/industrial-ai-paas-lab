$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$reports = Join-Path $root 'acceptance_reports'
New-Item -ItemType Directory -Force -Path $reports | Out-Null
$report = Join-Path $reports 'V18_PHASE4_ACCEPTANCE.json'
$result = [ordered]@{ version='1.8'; phase='4'; timestamp=(Get-Date).ToString('o'); selected_offline='FAIL'; pg16_live='NOT_RUN'; browser_ux='NOT_CERTIFIED'; mcp_streamable_http='NOT_CERTIFIED'; production='NO_GO' }
try {
  Push-Location (Join-Path $root 'backend')
  try {
    & py -3.14 -m pytest -q tests/test_v18_phase4_http_workbench.py tests/test_v18_phase3_secure_bridge.py tests/test_v18_phase2_durable_ledger.py tests/test_v18_network_recovery.py tests/test_v17_transport.py tests/test_v17_network_recovery.py tests/test_v17_final_smoke.py tests/test_mcp_v15_release_contract.py tests/test_v15_portfolio_migration_contract.py tests/test_v16_portfolio_contract.py tests/test_v16_rc4_security.py tests/test_v16_rc5_release_gate.py
    if ($LASTEXITCODE -ne 0) { throw 'V18 PHASE4 OFFLINE GATE FAILED' }
    $result.selected_offline = 'PASS'
    if ($env:V18_ALLOW_ISOLATED_PG16 -eq 'YES' -and $env:V18_ISOLATED_PG16_DSN) {
      & py -3.14 -m pytest -q tests/test_v18_phase4_live_pg16.py
      if ($LASTEXITCODE -ne 0) { throw 'V18 ISOLATED PG16 GATE FAILED' }
      $result.pg16_live = 'PASS'
    }
    Write-Host 'V1.8 PHASE4 SELECTED GATE PASSED'
    Write-Host 'NOT CERTIFIED: browser UX, full MCP Streamable HTTP, production authentication, crash replay.'
  } finally { Pop-Location }
} catch {
  Write-Host "GATE FAILED: $_"
  throw
} finally {
  $result | ConvertTo-Json -Depth 4 | Set-Content -Path $report -Encoding utf8
  Write-Host "Report: $report"
}
