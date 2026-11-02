# V1.6 RC5 - fail-closed, local-only verification. Does not deploy or migrate.
param([switch]$LiveNeon)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$py = if (Get-Command py -ErrorAction SilentlyContinue) { 'py' } elseif (Get-Command python -ErrorAction SilentlyContinue) { 'python' } else { throw 'Python is not installed' }
Push-Location backend
try {
    if ($py -eq 'py') { & py -3.14 -m pytest tests/test_v16_portfolio_contract.py tests/test_v16_rc4_security.py tests/test_v16_rc5_release_gate.py -q }
    else { & python -m pytest tests/test_v16_portfolio_contract.py tests/test_v16_rc4_security.py tests/test_v16_rc5_release_gate.py -q }
    if ($LASTEXITCODE -ne 0) { throw 'RC5 CONTRACT GATE FAILED' }
    if ($LiveNeon) {
        if ($env:V16_DEV_BRANCH_CONFIRMED -ne 'dev-v1-6-backend-pg18') { throw 'Dev branch confirmation required' }
        if (-not $env:PORTFOLIO_READONLY_DATABASE_URL) { throw 'Dedicated reader DSN required; never use owner' }
        if ($py -eq 'py') { & py -3.14 scripts/v16_rc4_neon_live_gate.py }
        else { & python scripts/v16_rc4_neon_live_gate.py }
        if ($LASTEXITCODE -ne 0) { throw 'RC5 LIVE NEON GATE FAILED' }
    } else { Write-Host 'LIVE NEON: NOT RUN (requires isolated dev branch reader credential)' }
    Write-Host 'RC5 SELECTED GATES PASSED; full PG16 regression and browser acceptance still separate.'
} finally { Pop-Location }
