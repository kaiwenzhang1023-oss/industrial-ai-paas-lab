[CmdletBinding()]
param(
    [string]$ProjectRoot = $PSScriptRoot,
    [string]$Container = 'industrial-v18-pg16-test',
    [string]$Database = 'industrial_ai_v18_e06_migration_replay',
    [string]$DbUser = 'v18_tester',
    [int]$HostPort = 55432
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Fixed allowlist: this gate cannot target acceptance, production, Neon, or Render.
if ($Container -ne 'industrial-v18-pg16-test' -or
    $Database -ne 'industrial_ai_v18_e06_migration_replay' -or
    $DbUser -ne 'v18_tester' -or $HostPort -ne 55432) {
    throw 'REFUSED: target differs from the explicitly approved E06-15 replay target.'
}
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$Evidence = Join-Path $ProjectRoot ("E06_15_FINAL_EVIDENCE_" + (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Path $Evidence | Out-Null
$envBackup = @{}
$envNames = @('DATABASE_URL','TEST_DATABASE_URL','M1_TEST_DATABASE_URL','V15_BUSINESS_DATABASE_URL',
              'E06_ALLOW_ISOLATED_DB_TESTS','V18_ALLOW_ISOLATED_PG16','V18_ISOLATED_PG16_DSN')
foreach ($n in $envNames) { $envBackup[$n] = [Environment]::GetEnvironmentVariable($n,'Process') }

function Invoke-DockerChecked {
    param([string]$Label, [string[]]$DockerArgs, [string]$LogName)
    Write-Host "`n=== $Label ===" -ForegroundColor Cyan
    $old = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & docker @DockerArgs 2>&1
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $old }
    $lines = @($output | ForEach-Object { "$_" })
    if ($LogName) { $lines | Set-Content -LiteralPath (Join-Path $Evidence $LogName) -Encoding UTF8 }
    foreach ($line in $lines) { Write-Host $line }
    if ($code -ne 0) { throw "$Label failed (exit=$code). See evidence/$LogName" }
    return $lines
}
function Invoke-Query {
    param([string]$Label, [string]$Sql, [string]$LogName)
    $lines = Invoke-DockerChecked $Label @(
        'exec',$Container,'psql','-U',$DbUser,'-d',$Database,'-X','-A','-t',
        '-v','ON_ERROR_STOP=1','-c',$Sql
    ) $LogName
    return (($lines -join "`n").Trim())
}
function Get-ObjectSnapshot {
    param([string]$Name)
    $sql = @'
SELECT
  'SCHEMA|' || nspname
FROM pg_namespace
WHERE nspname NOT IN ('pg_catalog','information_schema')
  AND nspname NOT LIKE 'pg_toast%'
UNION ALL
SELECT
  'REL|' || n.nspname || '|' || c.relname || '|' || c.relkind::text
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname IN ('mock_erp','mock_wms','mock_mes','platform','audit')
  AND c.relkind IN ('r','p','v','m','S','f')
UNION ALL
SELECT
  'COL|' || n.nspname || '|' || c.relname || '|' || a.attnum::text || '|' ||
  a.attname || '|' || format_type(a.atttypid,a.atttypmod) || '|' ||
  a.attnotnull::text || '|' || COALESCE(pg_get_expr(d.adbin,d.adrelid),'')
FROM pg_attribute a
JOIN pg_class c ON c.oid=a.attrelid
JOIN pg_namespace n ON n.oid=c.relnamespace
LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
WHERE n.nspname IN ('mock_erp','mock_wms','mock_mes','platform','audit')
  AND a.attnum>0 AND NOT a.attisdropped
UNION ALL
SELECT
  'CON|' || n.nspname || '|' || t.relname || '|' || c.conname || '|' ||
  c.contype::text || '|' || c.convalidated::text || '|' || pg_get_constraintdef(c.oid,true)
FROM pg_constraint c
JOIN pg_class t ON t.oid=c.conrelid
JOIN pg_namespace n ON n.oid=t.relnamespace
WHERE n.nspname IN ('mock_erp','mock_wms','mock_mes','platform','audit')
UNION ALL
SELECT
  'IDX|' || n.nspname || '|' || t.relname || '|' || i.relname || '|' ||
  x.indisunique::text || '|' || x.indisvalid::text || '|' || pg_get_indexdef(i.oid)
FROM pg_index x
JOIN pg_class i ON i.oid=x.indexrelid
JOIN pg_class t ON t.oid=x.indrelid
JOIN pg_namespace n ON n.oid=t.relnamespace
WHERE n.nspname IN ('mock_erp','mock_wms','mock_mes','platform','audit')
UNION ALL
SELECT
  'TRG|' || n.nspname || '|' || t.relname || '|' || g.tgname || '|' ||
  pg_get_triggerdef(g.oid,true)
FROM pg_trigger g
JOIN pg_class t ON t.oid=g.tgrelid
JOIN pg_namespace n ON n.oid=t.relnamespace
WHERE NOT g.tgisinternal
  AND n.nspname IN ('mock_erp','mock_wms','mock_mes','platform','audit')
ORDER BY 1;
'@
    $snapshot = Invoke-Query "Capture $Name catalog snapshot" $sql "$Name.txt"
    $snapshot | Set-Content -LiteralPath (Join-Path $Evidence $Name) -Encoding UTF8
    $bytes = [Text.Encoding]::UTF8.GetBytes(($snapshot -replace "`r`n","`n"))
    $sha = [BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($bytes)).Replace('-','').ToLowerInvariant()
    return $sha
}

try {
    Write-Host 'E06-15 FINAL ONE-SHOT GATE' -ForegroundColor Green
    # Toolchain checks
    $py = Get-Command py -ErrorAction SilentlyContinue
    if (-not $py) { throw 'Python launcher (py.exe) not found.' }
    $pyver = & py -3.14 --version 2>&1
    if ($LASTEXITCODE -ne 0 -or "$pyver" -notmatch 'Python 3\.14') { throw "Python 3.14 required; got $pyver" }
    $pyver | Set-Content (Join-Path $Evidence 'python314.txt')
    $psver = $PSVersionTable.PSVersion.ToString()
    if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) {
        throw "Windows PowerShell 5.1 required; current=$psver"
    }
    "Windows PowerShell $psver" | Set-Content (Join-Path $Evidence 'powershell.txt')
    $dockerVersion = Invoke-DockerChecked 'Docker version' @('version','--format','{{.Server.Version}}') 'docker_version.txt'
    $running = Invoke-DockerChecked 'Container running state' @('inspect','-f','{{.State.Running}}',$Container) 'container_running.txt'
    if (($running -join '').Trim() -ne 'true') { throw 'Approved PG16 container is not running.' }
    $image = Invoke-DockerChecked 'Container image' @('inspect','-f','{{.Config.Image}}',$Container) 'container_image.txt'
    if (($image -join '').Trim() -ne 'postgres:16') { throw 'Approved container image must be postgres:16.' }
    $portsRaw = Invoke-DockerChecked 'Container port mapping' @('inspect','-f','{{json .NetworkSettings.Ports}}',$Container) 'container_ports.json'
    $ports = (($portsRaw -join "`n") | ConvertFrom-Json)
    $published = @($ports.'5432/tcp' | ForEach-Object { [int]$_.HostPort })
    if ($published -notcontains 55432) { throw 'Expected 55432 -> 5432 mapping not found.' }

    # Verify existing acceptance DB and replay DB. Do not touch acceptance DB.
    $acceptId = Invoke-DockerChecked 'Read-only existing acceptance DB identity' @(
      'exec',$Container,'psql','-U',$DbUser,'-d','industrial_ai_v18_e06_acceptance','-X','-A','-t',
      '-v','ON_ERROR_STOP=1','-c',"SELECT current_database()||'|'||current_user||'|'||current_setting('server_version_num')||'|'||pg_is_in_recovery();"
    ) 'acceptance_identity.txt'
    if (($acceptId -join '').Trim() -notmatch '^industrial_ai_v18_e06_acceptance\|v18_tester\|16[0-9]{4}\|false$') {
        throw 'Existing acceptance database identity check failed.'
    }
    $identity = Invoke-Query 'Replay DB identity' "SELECT current_database()||'|'||current_user||'|'||current_setting('server_version_num')||'|'||pg_is_in_recovery();" 'replay_identity.txt'
    if ($identity -notmatch '^industrial_ai_v18_e06_migration_replay\|v18_tester\|16[0-9]{4}\|false$') {
        throw "Replay database identity mismatch: $identity"
    }
    $initialCount = Invoke-Query 'Replay DB initial state' "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%' AND c.relkind IN ('r','p','v','m','S','f');" 'initial_object_count.txt'
    if ($initialCount -ne '0') {
        # Idempotent resume is permitted only when our migration ledger is present.
        $ledgerExists = Invoke-Query 'Check migration ledger presence' "SELECT count(*) FROM information_schema.tables WHERE table_schema='platform' AND table_name='e06_schema_migrations';" 'ledger_presence.txt'
        if ($ledgerExists -ne '1') { throw "Replay DB is not empty and has no E06 migration ledger (objects=$initialCount). Refusing to modify it." }
    }

    # Full offline Python 3.14 regression; database variables are withheld to prevent accidental writes.
    foreach ($n in $envNames) { [Environment]::SetEnvironmentVariable($n,$null,'Process') }
    $backend = Join-Path $ProjectRoot 'backend'
    if (-not (Test-Path -LiteralPath (Join-Path $backend 'pyproject.toml'))) { throw 'backend/pyproject.toml missing.' }
    Push-Location $backend
    try {
        $pytestOutput = & py -3.14 -m pytest -q 2>&1
        $pytestCode = $LASTEXITCODE
        $pytestOutput | ForEach-Object { "$_" } | Set-Content (Join-Path $Evidence 'python314_full_pytest.txt') -Encoding UTF8
        $pytestOutput | ForEach-Object { Write-Host "$_" }
        if ($pytestCode -ne 0) { throw "Python 3.14 full offline pytest failed (exit=$pytestCode)." }
    } finally { Pop-Location }

    # Only the explicitly approved core migration chain is considered.
    $migrationNames = @('schema.sql','003_v03.sql','004_snapshot_fence.sql','005_effective_bom.sql',
      '006_m2_integration.sql','007_normalized_pegging.sql','008_workflow_runtime.sql',
      '009_workflow_worker.sql','010_agent_harness.sql','011_agent_governance.sql','012_outbox_receipts.sql')
    foreach ($m in $migrationNames) {
        if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot "database\$m"))) { throw "Missing core migration: $m" }
    }

    # Create the ledger once in the approved replay DB. Each migration and its
    # checksum record are committed in one psql session; raw SQL is not blindly
    # re-run on pass two. A checksum drift is a hard stop.
    $ledgerSql = @'
CREATE SCHEMA IF NOT EXISTS platform;
CREATE TABLE IF NOT EXISTS platform.e06_schema_migrations (
  version TEXT PRIMARY KEY,
  sha256 CHAR(64) NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
'@
    $ledgerPath = Join-Path $Evidence 'create_ledger.sql'
    $ledgerSql | Set-Content -LiteralPath $ledgerPath -Encoding UTF8
    Invoke-DockerChecked 'Create migration ledger' @('cp',$ledgerPath,"${Container}:/tmp/e06_15_create_ledger.sql") $null | Out-Null
    Invoke-DockerChecked 'Apply migration ledger bootstrap' @('exec',$Container,'psql','-U',$DbUser,'-d',$Database,'-X','-v','ON_ERROR_STOP=1','-f','/tmp/e06_15_create_ledger.sql') 'ledger_bootstrap.log' | Out-Null

    $firstPassApplied = 0
    $secondPassSkipped = 0
    for ($pass = 1; $pass -le 2; $pass++) {
        Write-Host "`n========== MIGRATION PASS $pass ==========" -ForegroundColor Yellow
        $index = 0
        foreach ($m in $migrationNames) {
            $index++
            $path = Join-Path $ProjectRoot "database\$m"
            $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
            $escaped = $m.Replace("'","''")
            $check = Invoke-Query "Ledger lookup $m pass $pass" "SELECT sha256 FROM platform.e06_schema_migrations WHERE version='$escaped';" ("ledger_{0}_{1:D2}.txt" -f $pass,$index)
            if ($check) {
                if ($check.Trim() -ne $hash) { throw "Checksum drift for already-applied migration $m. Refusing replay." }
                if ($pass -eq 2) { $secondPassSkipped++ }
                Write-Host "SKIP (checksum verified): $m"
                continue
            }
            if ($pass -eq 2) { throw "Pass 2 found unapplied migration $m; pass 1 incomplete." }

            $remote = "/tmp/e06_15_migration_{0:D2}.sql" -f $index
            Invoke-DockerChecked "Copy $m" @('cp',$path,"${Container}:$remote") $null | Out-Null
            # SQL file and ledger insert are in a single psql process. For files
            # with their own BEGIN/COMMIT, psql continues only if all commands succeed.
            $recordSql = "INSERT INTO platform.e06_schema_migrations(version,sha256) VALUES ('$escaped','$hash');"
            $recordPath = Join-Path $Evidence ("record_{0:D2}.sql" -f $index)
            $recordSql | Set-Content -LiteralPath $recordPath -Encoding UTF8
            Invoke-DockerChecked "Apply core migration $m" @(
                'exec',$Container,'psql','-U',$DbUser,'-d',$Database,'-X',
                '-v','ON_ERROR_STOP=1','-f',$remote,'-c',$recordSql
            ) ("migration_{0:D2}_{1}.log" -f $index,$m) | Out-Null
            $firstPassApplied++
            Write-Host "APPLIED: $m" -ForegroundColor Green
        }
        if ($pass -eq 1) {
            $script:SnapshotPass1 = Get-ObjectSnapshot 'catalog_snapshot_after_pass1.txt'
            $ledger1 = Invoke-Query 'Migration ledger after pass 1' "SELECT count(*) FROM platform.e06_schema_migrations;" 'ledger_count_pass1.txt'
            if ($ledger1 -ne "$($migrationNames.Count)") { throw "Expected $($migrationNames.Count) ledger rows after pass 1; got $ledger1." }
        } else {
            $script:SnapshotPass2 = Get-ObjectSnapshot 'catalog_snapshot_after_pass2.txt'
            if ($script:SnapshotPass1 -ne $script:SnapshotPass2) {
                $diff = Compare-Object (Get-Content (Join-Path $Evidence 'catalog_snapshot_after_pass1.txt')) (Get-Content (Join-Path $Evidence 'catalog_snapshot_after_pass2.txt'))
                $diff | Out-File (Join-Path $Evidence 'catalog_snapshot_diff.txt') -Encoding UTF8
                throw 'Catalog structure changed between migration pass 1 and pass 2.'
            }
        }
    }

    # Integrity assertions: expected schemas/tables, no invalid indexes, no unvalidated constraints, no broken FK targets.
    $schemaCount = Invoke-Query 'Required schema count' "SELECT count(*) FROM pg_namespace WHERE nspname IN ('mock_erp','mock_wms','mock_mes','platform','audit');" 'required_schema_count.txt'
    if ($schemaCount -ne '5') { throw "Expected five application schemas; got $schemaCount." }
    $tableCount = Invoke-Query 'Business table count' "SELECT count(*) FROM pg_tables WHERE schemaname IN ('mock_erp','mock_wms','mock_mes','platform','audit');" 'business_table_count.txt'
    if ([int]$tableCount -lt 31) { throw "Expected at least 31 business tables; got $tableCount." }
    $invalidIndexes = Invoke-Query 'Invalid index count' "SELECT count(*) FROM pg_index x JOIN pg_class t ON t.oid=x.indrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname IN ('mock_erp','mock_wms','mock_mes','platform','audit') AND NOT x.indisvalid;" 'invalid_index_count.txt'
    if ($invalidIndexes -ne '0') { throw "Invalid indexes found: $invalidIndexes." }
    $unvalidated = Invoke-Query 'Unvalidated constraint count' "SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname IN ('mock_erp','mock_wms','mock_mes','platform','audit') AND NOT c.convalidated;" 'unvalidated_constraint_count.txt'
    if ($unvalidated -ne '0') { throw "Unvalidated constraints found: $unvalidated." }
    $brokenFk = Invoke-Query 'Broken FK count' "SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname IN ('mock_erp','mock_wms','mock_mes','platform','audit') AND c.contype='f' AND (c.confrelid=0 OR NOT EXISTS (SELECT 1 FROM pg_class r WHERE r.oid=c.confrelid));" 'broken_fk_count.txt'
    if ($brokenFk -ne '0') { throw "Broken foreign keys found: $brokenFk." }
    $ledgerCount = Invoke-Query 'Final migration ledger count' "SELECT count(*) FROM platform.e06_schema_migrations;" 'final_ledger_count.txt'
    if ($ledgerCount -ne "$($migrationNames.Count)") { throw 'Final migration ledger count mismatch.' }

    @"
E06-15 FINAL CONSOLIDATED GATE: PASS
PowerShell: $psver
Python: $pyver
Docker server: $($dockerVersion -join '')
Container: $Container (postgres:16; localhost port 55432)
Database: $Database / user $DbUser
Core migrations: $($migrationNames.Count)
First pass newly applied in this run: $firstPassApplied
Second pass checksum-verified and skipped: $secondPassSkipped
Pass 1 catalog SHA256: $($script:SnapshotPass1)
Pass 2 catalog SHA256: $($script:SnapshotPass2)
Business tables: $tableCount
Invalid indexes: $invalidIndexes
Unvalidated constraints: $unvalidated
Broken foreign keys: $brokenFk
Python 3.14 full offline pytest: PASS (see python314_full_pytest.txt)

IMPORTANT:
- The migration runner provides ledger-based repeatability. It does not blindly re-execute non-idempotent DDL on pass 2.
- The existing industrial_ai_v18_e06_acceptance database was identity-checked only and not modified.
- No Neon/Render/production connections were made.
- No database, schema, table, role, or historical data was deleted.
- The replay database is retained. No cleanup was performed.
"@ | Set-Content (Join-Path $Evidence 'FINAL_RESULT.txt') -Encoding UTF8
    Write-Host "`nE06-15 FINAL CONSOLIDATED GATE PASS" -ForegroundColor Green
    Write-Host "Evidence: $Evidence"
}
catch {
    $_ | Out-String | Set-Content (Join-Path $Evidence 'FAILURE.txt') -Encoding UTF8
    Write-Host "`nE06-15 FINAL GATE FAILED/CHECKPOINTED. Review evidence; replay DB is retained." -ForegroundColor Red
    Write-Host "Evidence: $Evidence"
    throw
}
finally {
    foreach ($n in $envNames) { [Environment]::SetEnvironmentVariable($n,$envBackup[$n],'Process') }
}
