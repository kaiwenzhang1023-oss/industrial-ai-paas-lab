$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$dir=Join-Path $root 'acceptance_reports'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$report=Join-Path $dir 'V18_PHASE3_ACCEPTANCE.json'
$result=[ordered]@{version='1.8';phase='3';timestamp=(Get-Date).ToString('o');selected_offline='FAIL';production='NO_GO';pg16_live='NOT_RUN';browser='NOT_RUN';http_protocol='NOT_CERTIFIED';real_adapter_integration='NOT_CERTIFIED'}
try {
 Push-Location (Join-Path $root 'backend')
 try {
  & py -3.14 -m pytest -q tests/test_v18_phase3_secure_bridge.py tests/test_v18_phase2_durable_ledger.py tests/test_v18_network_recovery.py tests/test_v17_transport.py tests/test_v17_network_recovery.py tests/test_v17_final_smoke.py tests/test_mcp_v15_release_contract.py tests/test_v15_portfolio_migration_contract.py tests/test_v16_portfolio_contract.py tests/test_v16_rc4_security.py tests/test_v16_rc5_release_gate.py
  if ($LASTEXITCODE -ne 0) { throw 'V18 PHASE3 SELECTED OFFLINE GATE FAILED' }
  $result.selected_offline='PASS'
  Write-Host 'V1.8 PHASE3 SELECTED OFFLINE GATE PASSED'
  Write-Host 'NOT CERTIFIED: PG16 live, real adapters, browser, OAuth, Streamable HTTP, crash replay.'
 } finally {Pop-Location}
} finally {
 $result | ConvertTo-Json -Depth 4 | Set-Content -Path $report -Encoding utf8
 Write-Host "Report: $report"
}
