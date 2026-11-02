[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path),
    [string]$Container = "industrial-v18-pg16-test",
    [string]$Database = "industrial_ai_v18_e06_acceptance",
    [string]$DbUser = "v18_tester",
    [int]$HostPort = 55432
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Checked {
    param([string]$Label, [scriptblock]$Command)
    Write-Host "`n=== $Label ===" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Label failed (exit=$LASTEXITCODE)" }
}

$Backend = Join-Path $ProjectRoot "backend"
$Evidence = Join-Path $ProjectRoot ("E06_14_REPEATABILITY_EVIDENCE_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
New-Item -ItemType Directory -Path $Evidence -Force | Out-Null

# Refuse unexpected paths or targets. This script never creates/drops databases or tables.
if (-not (Test-Path (Join-Path $Backend "pyproject.toml"))) { throw "backend/pyproject.toml not found; ProjectRoot is incorrect." }
if ($Database -ne "industrial_ai_v18_e06_acceptance" -or $DbUser -ne "v18_tester" -or $HostPort -ne 55432) {
    throw "E06-14 only permits the dedicated acceptance DB, v18_tester, localhost mapped port 55432."
}
$running = docker inspect -f '{{.State.Running}}' $Container
if ($LASTEXITCODE -ne 0 -or $running -ne "true") { throw "Expected Docker container is not running." }
$image = docker inspect -f '{{.Config.Image}}' $Container
if ($LASTEXITCODE -ne 0 -or $image -ne "postgres:16") { throw "Container image mismatch; expected postgres:16." }

# Validate identity using in-container psql. No secret is printed.
$identity = docker exec $Container psql -U $DbUser -d $Database -X -At -F "|" -v ON_ERROR_STOP=1 `
    -c "SELECT current_database(),current_user,current_setting('server_version_num'),pg_is_in_recovery();"
if ($LASTEXITCODE -ne 0) { throw "Cannot connect to the designated acceptance database." }
if ($identity -notmatch '^industrial_ai_v18_e06_acceptance\|v18_tester\|16[0-9]{4}\|f$') {
    throw "Database identity mismatch. Returned identity: $identity"
}
"container=$Container`ndatabase_identity=$identity`nimage=$image" |
    Set-Content (Join-Path $Evidence "identity.txt") -Encoding UTF8

# Capture a read-only table row-count baseline from the dedicated database.
$SnapshotSql = @"
SELECT COALESCE(json_agg(json_build_object(
 'schema', schemaname, 'table', relname, 'rows', n_live_tup
) ORDER BY schemaname,relname),'[]'::json)
FROM pg_stat_user_tables;
"@
$before = docker exec $Container psql -U $DbUser -d $Database -X -At -v ON_ERROR_STOP=1 -c $SnapshotSql
if ($LASTEXITCODE -ne 0) { throw "Pre-test read-only snapshot failed." }
$before | Set-Content (Join-Path $Evidence "table_snapshot_before.json") -Encoding UTF8

# Ask for the existing v18_tester password without echoing it. No credentials are written to evidence.
$secure = Read-Host "Enter the existing v18_tester password for localhost:$HostPort (input hidden)" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }

$env:TEST_DATABASE_URL = "postgresql://$DbUser`:$([uri]::EscapeDataString($plain))@127.0.0.1`:$HostPort/$Database"
$env:V18_ISOLATED_PG16_DSN = $env:TEST_DATABASE_URL
$env:E06_ALLOW_ISOLATED_DB_TESTS = "YES"
$env:V18_ALLOW_ISOLATED_PG16 = "YES"
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:M1_TEST_DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:V15_BUSINESS_DATABASE_URL -ErrorAction SilentlyContinue

Push-Location $Backend
try {
    Invoke-Checked "Python 3.14 identity" { py -3.14 --version }
    Invoke-Checked "Repeatability run 1 (isolated-schema PG16 test)" {
        py -3.14 -m pytest -q tests/test_v18_phase4_live_pg16.py --junitxml (Join-Path $Evidence "run1.junit.xml")
    }
    Invoke-Checked "Read-only schema inventory after run 1" {
        docker exec $Container psql -U $DbUser -d $Database -X -v ON_ERROR_STOP=1 `
          -c "SELECT nspname FROM pg_namespace WHERE nspname LIKE 'v18_gate_%' ORDER BY nspname;"
    }
    Invoke-Checked "Repeatability run 2 (same test, fresh generated schema)" {
        py -3.14 -m pytest -q tests/test_v18_phase4_live_pg16.py --junitxml (Join-Path $Evidence "run2.junit.xml")
    }
    $after = docker exec $Container psql -U $DbUser -d $Database -X -At -v ON_ERROR_STOP=1 -c $SnapshotSql
    if ($LASTEXITCODE -ne 0) { throw "Post-test read-only snapshot failed." }
    $after | Set-Content (Join-Path $Evidence "table_snapshot_after.json") -Encoding UTF8
    if ($before -ne $after) {
        Write-Warning "PostgreSQL statistics snapshot changed. Review before/after evidence; n_live_tup is approximate and may change after ANALYZE/VACUUM."
    } else {
        Write-Host "Read-only table statistics snapshot unchanged." -ForegroundColor Green
    }
    "Run 1 and run 2 completed. See JUnit reports and snapshots in $Evidence" |
        Set-Content (Join-Path $Evidence "RESULT.txt") -Encoding UTF8
    Write-Host "`nE06-14 TARGETED REPEATABILITY TEST PASS. This is not full V1.8 acceptance." -ForegroundColor Green
    Write-Host "Evidence: $Evidence"
}
finally {
    Pop-Location
    $env:TEST_DATABASE_URL = $null
    $env:V18_ISOLATED_PG16_DSN = $null
    $env:E06_ALLOW_ISOLATED_DB_TESTS = $null
    $env:V18_ALLOW_ISOLATED_PG16 = $null
    $plain = $null
}
