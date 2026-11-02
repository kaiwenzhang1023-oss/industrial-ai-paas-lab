$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$reports = Join-Path $root 'acceptance_reports'
New-Item -ItemType Directory -Force -Path $reports | Out-Null
$report = Join-Path $reports 'V18_FINAL_RC_ACCEPTANCE.json'
$result = [ordered]@{version='1.8'; phase='Final RC'; timestamp=(Get-Date).ToString('o'); offline='NOT_RUN'; pg16_live='NOT_RUN'; browser='NOT_RUN'; streamable_http_conformance='NOT_CERTIFIED'; authorized_network_e2e='NOT_CERTIFIED'; production='NO_GO'; overall='INCOMPLETE'}
$failed = $false
try {
  Push-Location (Join-Path $root 'backend')
  try {
    & py -3.14 -m pytest -q tests/test_v18_phase4_http_workbench.py tests/test_v18_phase3_secure_bridge.py tests/test_v18_phase2_durable_ledger.py tests/test_v18_network_recovery.py tests/test_v17_transport.py tests/test_v17_network_recovery.py tests/test_v17_final_smoke.py tests/test_mcp_v15_release_contract.py tests/test_v15_portfolio_migration_contract.py tests/test_v16_portfolio_contract.py tests/test_v16_rc4_security.py tests/test_v16_rc5_release_gate.py
    if ($LASTEXITCODE -ne 0) { throw 'OFFLINE_GATE_FAILED' }
    $result.offline = 'PASS'
    if ($env:V18_ALLOW_ISOLATED_PG16 -eq 'YES') {
      if (-not $env:V18_ISOLATED_PG16_DSN) { throw 'PG16_OPT_IN_REQUIRES_ISOLATED_DSN' }
      & py -3.14 -m pytest -q tests/test_v18_phase4_live_pg16.py
      if ($LASTEXITCODE -ne 0) { throw 'PG16_GATE_FAILED' }
      $result.pg16_live = 'PASS'
    }
    if ($env:V18_RUN_BROWSER -eq 'YES') {
      & py -3.14 -m pytest -q tests/test_v18_final_browser.py
      if ($LASTEXITCODE -ne 0) { throw 'BROWSER_GATE_FAILED' }
      $result.browser = 'PASS_STATIC_PAGE_RENDER_ONLY'
    }
    $result.overall = 'SELECTED_GATES_PASS_WITH_UNCERTIFIED_ITEMS'
    Write-Host 'V1.8 FINAL RC SELECTED GATES PASSED'
    Write-Host 'NOT CERTIFIED: Streamable HTTP conformance, authorized network E2E, production release.'
  } finally { Pop-Location }
} catch {
  $result.overall = 'FAIL'
  $failed = $true
  Write-Host "V1.8 FINAL RC GATE FAILED: $_"
} finally {
  $result | ConvertTo-Json -Depth 5 | Set-Content -Path $report -Encoding UTF8
  Write-Host "Report: $report"
}
if ($failed) { exit 1 }
